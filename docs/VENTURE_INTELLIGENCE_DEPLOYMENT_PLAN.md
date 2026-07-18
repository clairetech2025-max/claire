# Venture Intelligence Production Deployment Plan

## Services

- FastAPI: `uvicorn claire_vde.api:app --host 0.0.0.0 --port 8030`
- Background worker: `python -m claire_vde.worker`
- PostgreSQL: metadata, collector state, opportunity events
- Redis: queue broker and worker coordination
- Object storage: raw evidence archive
- Vector database: rebuildable semantic search
- Knowledge graph: rebuildable entity/event graph

Local compose file:

```bash
docker compose -f docker-compose.venture.yml up --build
```

## Environment

- `CLAIRE_ARE_ROOT`
- `CLAIRE_ARE_HMAC_KEY`
- `CLAIRE_ARE_MAX_SEGMENT_RECORDS`
- `CLAIRE_VDE_DB_PATH` for local SQLite
- Future production: `CLAIRE_VDE_DATABASE_URL`
- Source-specific API keys by provider name only; never commit secrets.

## Authentication Hooks

The API is intentionally separated from auth enforcement in this slice. Production deployment must put it behind the existing CLAIRE auth/proxy boundary or add a FastAPI dependency that validates service/user tokens before non-health endpoints.

## Object Storage Rule

Raw evidence belongs in object storage. Truth Spine stores hashes, summaries, source manifests, and source object references.

## Message Queue Rule

Collector jobs must be idempotent. A failed collector run must record an error and cursor state without admitting unsupported evidence.
