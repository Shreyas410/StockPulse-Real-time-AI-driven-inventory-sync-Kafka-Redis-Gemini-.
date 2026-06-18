# StockPulse

Real-time AI-driven inventory sync (Kafka, Redis, FastAPI, Gemini)

## Overview

StockPulse is a lightweight inventory management service that demonstrates an event-driven architecture with AI-driven control plane integration. The service exposes a simple FastAPI HTTP API to read and update inventory, publishes inventory-change events to Kafka (optional), and uses Redis for caching frequently-read inventory state. A companion MCP (Model Control Plane) service accepts natural-language commands and converts them into inventory actions using the Gemini API.

Key goals:
- Decouple write operations from downstream consumers via Kafka events
- Improve read performance with Redis caching and in-memory fallback
- Enable natural-language control via Gemini for demo and testing
- Provide automated tests and clear local development steps

## Tech stack

- Python 3.10+ with FastAPI for the HTTP API
- Uvicorn ASGI server
- aiokafka for Kafka producer (optional)
- aioredis for Redis caching (optional)
- Gemini (via google.generativeai) for natural-language to API conversions (MCP)
- Pytest + pytest-asyncio + httpx for tests

## Repository layout

- `inventory-service.py` — main FastAPI application
- `mcp_server.py` — Model Control Plane service that converts NL to inventory API calls
- `app.py` — import wrapper for tests and tooling
- `tests/` — pytest async tests for the API
- `requirements.txt` — pinned dependencies
- `secrets.json.sample` — sample secrets file (copy to `secrets.json` locally)

## Quick start (local)

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate    # Unix/macOS
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

2. (Optional) Configure secrets and environment variables:

- Copy `secrets.json.sample` to `secrets.json` and add your `GOOGLE_API_KEY` for Gemini.
- Or export `GOOGLE_API_KEY` as an environment variable.
- To enable Kafka/Redis, set `KAFKA_BOOTSTRAP_SERVERS` and/or `REDIS_URL`.

Example environment variables (Unix/macOS):

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export REDIS_URL=redis://localhost:6379/0
export CACHE_TTL_SEC=30
export GOOGLE_API_KEY="your_key_here"
```

3. Run the inventory API:

```bash
uvicorn inventory-service:app --reload
```

4. Run the MCP server (optional, requires Gemini key):

```bash
uvicorn mcp_server:app --reload --port 8001
```

5. Run tests:

```bash
pytest -q
```

## Endpoints

- `GET /inventory` — returns current inventory for `tshirts` and `pants` (cached)
- `POST /inventory` — update an item: payload `{ "item": "tshirts", "change": -3 }`
- `GET /health` — basic health and integration status
