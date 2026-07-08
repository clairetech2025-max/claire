# Full CLAIRE Hugging Face Migration Plan

## Current Azure Trunk

- Repo: `/home/LuciusPrime/claire`
- Main public runtime entrypoint: `claire_gui:app`
- Framework: FastAPI + uvicorn
- Azure public service port: `8000`
- Hugging Face port: `7860` via `PORT`

## Runtime Flow To Preserve

Input -> Q/Gyro orientation -> lane routing/C3RP-style classification -> Sentinel/policy checks -> ARE/Truth Spine recall -> source/document evidence -> optional relevance search -> model reasoning -> output validation -> trace/ledger -> governed memory commit.

## Recommended Hugging Face Mode

Use a Docker Space. The runtime is not a Gradio-only demo. It has FastAPI routes, local state, parser bridges, optional model/provider integrations, and service-style startup requirements.

## Storage Policy

Do not migrate Azure private data. Start with empty persistent storage under `/data/claire_runtime` if HF persistent storage is enabled.

Recommended paths:

- ARE JSONL: `/data/claire_runtime/are/are_mem.jsonl`
- Traces JSONL: `/data/claire_runtime/traces/claire_runtime_traces.jsonl`
- Trace DB: `/data/claire_runtime/traces/claire_runtime_traces.db`
- Uploads: `/data/claire_runtime/uploads`
- Veritas GUI temp state: `/data/claire_runtime/veritas_legal_gui`

## Excluded From Migration

- `/home/LuciusPrime/claire/.env`
- `/home/LuciusPrime/claire/claire_keys.env`
- `/home/LuciusPrime/claire/data/`
- `/home/LuciusPrime/claire/claire_state/*.db`
- `/home/LuciusPrime/claire/*.log`
- `/home/LuciusPrime/claire/models`
- `/home/LuciusPrime/claire/private_repo_payloads`
- generated FAISS indexes
- private Veritas/legal evidence
- Azure/cloudflared/nginx tokens

## Provider Plan

Initial full-runtime Space should use provider secrets by name only. Suggested first provider mode is NVIDIA NIM if approved. Local model hosting should be a later hardware test because model files and llama.cpp build increase cost and complexity.

## Validation Before Deployment

Run locally before pushing:

```bash
python -m py_compile claire_gui.py claire_runtime.py trace_logger.py original_are_bridge.py
python validate_claire_runtime.py
```

Then test the Docker container with empty local state and placeholder secrets before creating the paid HF Space.

## Deployment Gate

Do not create or upgrade `Blackstormhorse/CLAIRE_Runtime_Full` until Steve approves:

- branch/ref
- provider mode
- HF hardware
- persistent storage
- exact secrets list
