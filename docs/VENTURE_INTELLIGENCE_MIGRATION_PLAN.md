# Venture Intelligence Migration Plan

## Phase 1: Local Authority Validation

1. Start a GREEN-only ARE Truth Spine root with `CLAIRE_ARE_ROOT`.
2. Start Venture API with `uvicorn claire_vde.api:app`.
3. Admit synthetic and JSONL-normalized evidence.
4. Verify every evidence record has a Truth Spine hash.
5. Verify metadata can be deleted and rebuilt from admitted evidence records.

## Phase 2: Production Metadata Store

1. Provision PostgreSQL.
2. Apply `migrations/venture_intelligence_postgres.sql`.
3. Configure metadata repository adapter for PostgreSQL.
4. Run parity tests against SQLite local behavior.

## Phase 3: Raw Evidence Archive

1. Provision object storage.
2. Store raw source captures by content hash.
3. Admit only normalized evidence summaries and source manifests into Truth Spine.
4. Keep raw data immutable.

## Phase 4: Background Workers

1. Add Redis.
2. Add collector jobs by source.
3. Store collector cursors in `collector_state`.
4. Require idempotent collector runs.

## Phase 5: Recognition Indexes

1. Build vector and graph indexes from Truth Spine references.
2. Record index build manifests.
3. Prove indexes can be deleted and rebuilt.

## Rollback

Do not cut over BLUE. Disable only the GREEN Venture API, preserve Truth Spine segments, and restore the previous GREEN branch.
