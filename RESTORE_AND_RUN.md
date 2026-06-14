# Restore And Run

## Repository

- Repo root: `/home/LuciusPrime/claire`
- Branch: `codex/huggingface-portable-demo`
- Validated runtime fix checkpoint: `51effd836372e6c37b7013dc92472afea75e58a6`

After clone or checkout:

```bash
git status --short
git branch --show-current
git log --oneline -5
```

## Environment

Use Python venv locally:

```bash
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
```

If `requirements.txt` is not current, install only the minimum packages needed by the failing command. Do not install GPU/model stacks without approval.

## Environment Variables

Use placeholders only in docs and commits:

```bash
NVIDIA_API_KEY=<set locally, never commit>
NVIDIA_NIM_BASE_URL=<optional>
NVIDIA_NIM_MODEL=<optional>
COURTLISTENER_API_KEY=<set locally, never commit>
ELEVENLABS_API_KEY=<optional voice key, never commit>
ELEVENLABS_VOICE_ID=<optional>
CLAIRE_ADMIN_ACTION_TOKEN=<set locally, never commit>
```

Do not commit `.env`, `*.env`, key files, logs, trace DBs, data ledgers, backups, caches, or private payloads.

## Run CLAIRE

```bash
venv/bin/python claire_gui.py
```

If running through uvicorn directly:

```bash
venv/bin/python -m uvicorn claire_gui:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Validate

```bash
venv/bin/python -m py_compile claire_runtime.py lane_classifier.py claire_gui.py main.py original_are_bridge.py veritas_adapter.py claire_courtlistener.py current_truth_loader.py validate_claire_runtime.py test_memory_routing.py
venv/bin/python validate_claire_runtime.py
venv/bin/python test_memory_routing.py
```

If `pytest` is installed:

```bash
venv/bin/python -m pytest
```

If `pytest` is missing, do not block the demo sprint; run the built-in validation scripts above.

## Demo

Use `DEMO_SCRIPT.md`.

For API checks:

```bash
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"input":"Claire can you help me find a horse hoof molding kit or other solution to make exact impression of a horse foot?"}'
```

For debug diagnostics only:

```bash
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"input":"Show debug lane for this request: check Veritas status","metadata":{"debug":true}}'
```

## Git Hygiene

Before committing:

```bash
git status --short
git diff --stat
git diff --cached --stat
```

Never commit:

- `.env`, `*.env`, `claire_keys.env`
- `keys/`
- `*.db`, `*.sqlite`
- `*.log`
- `data/`
- `logs/`
- `backups/`
- `private_payloads/`
- `claire_state/claire_runtime_traces.db`
