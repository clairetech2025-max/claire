# GREEN Restore Order

Date: 2026-07-11

## Restore Sequence

1. Source repository or source bundle.
2. Configuration templates.
3. Secrets through secret manager.
4. Provider/model health.
5. ARE empty-state boot.
6. Ingest bridge empty-state boot.
7. GO backend boot.
8. CLAIRE public/runtime API boot.
9. Veritas Legal route and synthetic ingest validation.
10. Restore Lane A memory and DBs only after empty-state validation.
11. Restore Lane B historical archives only after encrypted backup validation.
12. Rebuild indexes from preserved source/evidence where possible.

## Lane A Restore Validation

Lane A contains live runtime data and must be restored only into isolated GREEN storage.

Required validation:

- JSONL line counts match snapshot manifests.
- ARE recall returns known records.
- SQLite integrity checks pass.
- trace replay works for known trace IDs.
- Sentinel runtime state loads and enforces policy.
- n8n workflows can be listed or restored with secrets handled separately.

## Lane B Restore Validation

Lane B contains historical archives.

Required validation:

- encrypted archive checksum verifies before restore.
- restored file count and byte count match manifest.
- sample JSONL records parse.
- sample models/adapters are readable or registered.
- parser/historical data can be opened without exposing content publicly.

## Lane C Restore Validation

Lane C is rebuildable.

Required validation:

- package install scripts reproduce dependencies.
- vector indexes are rebuilt from preserved source/evidence when possible.
- Docker images are rebuilt from Dockerfiles rather than copied from Azure.
