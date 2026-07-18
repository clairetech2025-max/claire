# Cleanup Manifest

Generated during CLAIRE Core completion. No production cleanup has been executed.

## Classification Policy

- `CANONICAL`: selected runtime source.
- `ACTIVE DEPENDENCY`: used by a canonical module or startup path.
- `LEGACY - PRESERVE`: historical or compatibility material.
- `DUPLICATE - MIGRATION PENDING`: likely duplicate, not yet safe to delete.
- `TEST OR FIXTURE`: test support.
- `GENERATED ARTIFACT`: reproducible output.
- `CACHE OR TEMPORARY`: removable build/runtime cache.
- `SENSITIVE DATA - DO NOT COMMIT`: secrets, private evidence, databases, logs.
- `UNKNOWN - DO NOT TOUCH`: unresolved caller or provenance.

## Current Actions

- `claire_core/`: `CANONICAL`, new public wrapper and governance adapters.
- `deploy/huggingface/`: `ACTIVE DEPENDENCY`, deployment manifests.
- `scripts/deploy/`: `ACTIVE DEPENDENCY`, sanitized deployment tree builder.
- `claire_state/`: `SENSITIVE DATA - DO NOT COMMIT`, runtime state.
- `models`: `SENSITIVE DATA - DO NOT COMMIT`, model storage link/path.
- `__pycache__/`: `CACHE OR TEMPORARY`, removable.

Deletion remains blocked until import searches, runtime route checks, tests, and
human approval confirm a path is truly dead.
