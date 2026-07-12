# Venture Intelligence Architecture Decisions

## Authority

ARE Truth Spine remains the only memory authority. Venture Intelligence metadata, Recognition Rail matches, Q Insight orientation, FARE projections, and Opportunity Ledger events must reference Truth Spine hashes.

## Current Implementation Slice

Implemented now:

- Modular collector boundary with explicit unsupported external collectors.
- Incremental JSONL collector for normalized public-source evidence snapshots.
- First live public collector: Federal Register regulatory-pressure ingestion.
- Admission Gate with checksum dedupe before downstream orientation.
- ARE-backed evidence admission.
- SQLite local metadata repository for deterministic tests and local development.
- PostgreSQL migration schema for production metadata.
- Q Insight orientation from admitted evidence only.
- Recognition Rail historical analog matching from Q Insight only.
- FARE projections from Q Insight and Recognition Rail only.
- Sentinel recommendation validation.
- Append-only Opportunity Ledger with Truth Spine event references.
- FastAPI REST API under `claire_vde.api`.

Deferred until source credentials and deployment approval:

- Live SEC, USPTO, GitHub, arXiv, NIH, NSF, contracts, hiring, funding, acquisition, regulatory, and standards collectors.
- Redis-backed queue workers.
- Object storage writes for large raw source captures.
- Vector database and knowledge graph services.
- Authentication enforcement.

## Why SQLite Exists

SQLite is used only for local metadata tests and development. It is not memory authority. Production metadata is expected to use the PostgreSQL schema in `migrations/venture_intelligence_postgres.sql`.

## Rebuild Doctrine

Recognition Rail, vector indexes, graph indexes, and dashboard state must be rebuildable from:

1. ARE Truth Spine envelopes.
2. Immutable raw evidence archive manifests.
3. Downstream metadata rows referencing Truth Spine hashes.

Nothing downstream may become authority.
