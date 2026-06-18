
import asyncio
import json
import logging
import os
from typing import Dict, Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from aiokafka import AIOKafkaProducer
except Exception:
    AIOKafkaProducer = None

try:
    import aioredis
except Exception:
    aioredis = None

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("inventory-service")

app = FastAPI(
    title="Inventory Management API",
    description="Simple inventory management system for t-shirts and pants",
    version="1.0.0"
)

# In memory storage : Dictionary to hold inventory counts and some random values to start with.
inventory_store: Dict[str, int] = {
    "tshirts": 20,
    "pants": 15
}

# Simple in-memory cache fallback when Redis isn't configured
_local_cache: Dict[str, Dict] = {}

# Clients (initialized on startup)
kafka_producer: Optional[object] = None
redis_client: Optional[object] = None

# Environment-driven configuration
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "inventory-updates")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
REDIS_URL = os.environ.get("REDIS_URL")
CACHE_TTL = int(os.environ.get("CACHE_TTL_SEC", "30"))


# Pydantic models: Used for request and response validation
class InventoryResponse(BaseModel):
    tshirts: int = Field(ge=0, description="Number of t-shirts in stock")
    pants: int = Field(ge=0, description="Number of pants in stock")


class InventoryUpdateRequest(BaseModel):
    item: Literal["tshirts", "pants"] = Field(description="Item to update")
    change: int = Field(description="Change in quantity (positive for add, negative for remove)")


class ErrorResponse(BaseModel):
    error: str
    message: str


async def _publish_kafka_message(message: dict):
    global kafka_producer
    if not KAFKA_BOOTSTRAP or not AIOKafkaProducer:
        logger.debug("Kafka disabled or aiokafka not installed; skipping publish")
        return
    if kafka_producer is None:
        logger.warning("Kafka producer not initialized; skipping publish")
        return
    payload = json.dumps(message).encode("utf-8")
    try:
        await kafka_producer.send_and_wait(KAFKA_TOPIC, payload)
        logger.info("Published inventory event to Kafka topic %s", KAFKA_TOPIC)
    except Exception as exc:
        logger.exception("Failed to publish Kafka message: %s", exc)


async def _cache_get(key: str) -> Optional[dict]:
    global redis_client, _local_cache
    if redis_client is not None:
        try:
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            logger.exception("Redis get failed; falling back to local cache")
    entry = _local_cache.get(key)
    if not entry:
        return None
    # entry: {"value":..., "expires_at": epoch}
    if entry["expires_at"] < asyncio.get_event_loop().time():
        _local_cache.pop(key, None)
        return None
    return entry["value"]


async def _cache_set(key: str, value: dict, ttl: int = CACHE_TTL):
    global redis_client, _local_cache
    if redis_client is not None:
        try:
            await redis_client.set(key, json.dumps(value), ex=ttl)
            return
        except Exception:
            logger.exception("Redis set failed; falling back to local cache")
    _local_cache[key] = {"value": value, "expires_at": asyncio.get_event_loop().time() + ttl}


@app.on_event("startup")
async def startup_event():
    global kafka_producer, redis_client
    # Initialize Kafka producer if configured
    if KAFKA_BOOTSTRAP and AIOKafkaProducer:
        try:
            kafka_producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
            await kafka_producer.start()
            logger.info("Kafka producer started")
        except Exception:
            logger.exception("Failed to start Kafka producer; continuing without Kafka")
            kafka_producer = None
    else:
        logger.debug("Kafka not configured or aiokafka missing")

    # Initialize Redis if configured
    if REDIS_URL and aioredis:
        try:
            redis_client = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=False)
            # quick ping
            await redis_client.ping()
            logger.info("Connected to Redis")
        except Exception:
            logger.exception("Failed to connect to Redis; continuing without Redis")
            redis_client = None
    else:
        logger.debug("Redis not configured or aioredis missing")


@app.on_event("shutdown")
async def shutdown_event():
    global kafka_producer, redis_client
    if kafka_producer is not None:
        try:
            await kafka_producer.stop()
            logger.info("Kafka producer stopped")
        except Exception:
            logger.exception("Error stopping Kafka producer")
    if redis_client is not None:
        try:
            await redis_client.close()
            logger.info("Redis client closed")
        except Exception:
            logger.exception("Error closing Redis client")


@app.get("/")
async def root():
    """Root endpoint with basic service info"""
    return {
        "service": "Inventory Management API",
        "version": "1.0.0",
        "endpoints": {
            "inventory": "/inventory",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/inventory", response_model=InventoryResponse)
async def get_inventory():
    """Get current inventory counts for all items (cached)"""
    cache_key = "inventory:all"
    cached = await _cache_get(cache_key)
    if cached is not None:
        return InventoryResponse(**cached)
    payload = {"tshirts": inventory_store["tshirts"], "pants": inventory_store["pants"]}
    await _cache_set(cache_key, payload)
    return InventoryResponse(**payload)


@app.post("/inventory", response_model=InventoryResponse)
async def update_inventory(request: InventoryUpdateRequest):
    """Update inventory count for a specific item"""

    # Check
    if request.item not in inventory_store:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid item: {request.item}. Must be 'tshirts' or 'pants'"
        )

    # new quantity
    current_quantity = inventory_store[request.item]
    new_quantity = current_quantity + request.change

    # Validate that quantity doesn't go negative
    if new_quantity < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reduce {request.item} by {abs(request.change)}. Only {current_quantity} available."
        )

    # Update inventory
    inventory_store[request.item] = new_quantity

    # Invalidate cache and publish event
    cache_key = "inventory:all"
    # remove local cache entry if present
    _local_cache.pop(cache_key, None)
    if redis_client is not None:
        try:
            await redis_client.delete(cache_key)
        except Exception:
            logger.exception("Redis delete failed during cache invalidation")

    # Publish event to Kafka (best-effort)
    event = {
        "item": request.item,
        "change": request.change,
        "new_quantity": new_quantity
    }
    asyncio.create_task(_publish_kafka_message(event))

    # Return updated inventory
    return InventoryResponse(
        tshirts=inventory_store["tshirts"],
        pants=inventory_store["pants"]
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    status = {"status": "healthy", "inventory_items": len(inventory_store)}
    status["kafka"] = bool(KAFKA_BOOTSTRAP and kafka_producer is not None)
    status["redis"] = bool(REDIS_URL and redis_client is not None)
    return status


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)


