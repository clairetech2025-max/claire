# GREEN Clean-Base Rebuild Plan

Date: 2026-07-11

## Objective

Prove CLAIRE can be recreated from preserved source artifacts and the pushed GREEN branch without copying Azure BLUE runtime directories, memory, databases, Docker volumes, caches, or private state.

## Source

- Repository: `https://github.com/clairetech2025-max/claire.git`
- Branch: `codex/huggingface-portable-demo`
- Commit: `57687656cd55ca27b6b9c2a16b933b4e535d2f40`
- Hugging Face target: `Blackstormhorse/CLAIRE_Runtime_Full`

## Clean Base Rules

- Fresh clone only.
- Fresh Python virtual environment only.
- Empty runtime data directory.
- No Azure memory restored in this phase.
- No Azure database restored in this phase.
- No Azure Docker volume reused.
- BLUE remains live and unchanged.

## Empty-State Runtime Components

1. ARE server
2. Ingest bridge
3. GO backend
4. CLAIRE FastAPI runtime via Hugging Face adapter
5. Veritas Legal route inside CLAIRE GUI/runtime

## Runtime Data Isolation

For local clean-base testing, runtime paths must point to an isolated directory such as:

`/tmp/green-clean-base/runtime_data`

For Hugging Face deployment, runtime paths should point to:

`/data/claire_runtime`

Only after empty-state validation passes should Lane A/Lane B data restoration be attempted.

## Commands Used In Clean-Base Validation

```bash
git clone --depth 1 --branch codex/huggingface-portable-demo \
  https://github.com/clairetech2025-max/claire.git /tmp/green-clean-base/claire

python3 -m venv /tmp/green-clean-base/venv
/tmp/green-clean-base/venv/bin/pip install --upgrade pip
/tmp/green-clean-base/venv/bin/pip install -r /tmp/green-clean-base/claire/hf_claire_runtime_full/requirements.txt

cd /tmp/green-clean-base/claire
/tmp/green-clean-base/venv/bin/python -m py_compile claire_gui.py ARE_SERVER.py claire_ingest_bridge.py hf_claire_runtime_full/app.py
go build -o /tmp/green-clean-base/claire-go-clean main.go
```
