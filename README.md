(Minimal Inventory Management API with optional Kafka & Redis integrations)

Run locally:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the app:

```bash
uvicorn inventory-service:app --reload
```

Environment variables:

- `KAFKA_BOOTSTRAP_SERVERS` - bootstrap servers for Kafka (optional)
- `KAFKA_TOPIC` - topic to publish inventory events (default: `inventory-updates`)
- `REDIS_URL` - Redis connection string (optional)
- `CACHE_TTL_SEC` - cache TTL for inventory GET (default: 30)

Testing:

```bash
pytest -q
```

# StockPulse-Real-time-AI-driven-inventory-sync-Kafka-Redis-Gemini-.  
