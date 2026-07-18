# Deployment

This repository is the authoritative source for CLAIRE runtime code. Azure remains
operational and must not be shut down by deployment scripts.

## Local Runtime

```bash
python -m venv venv
venv/bin/python -m pip install -e .
venv/bin/python claire_gui.py
```

Use `.env.example`, `config.example.yaml`, and `deployment.example.json` as
templates. Do not commit live `.env` files or private runtime data.

## Hugging Face Mirrors

Space-specific manifests live in `deploy/huggingface/`.

Build a sanitized CLAIRE deployment tree:

```bash
venv/bin/python scripts/deploy/build_hf_tree.py \
  deploy/huggingface/claire.manifest.json \
  /tmp/claire-hf-build
```

Build a sanitized Veritas deployment tree after the Veritas Space ID is confirmed:

```bash
venv/bin/python scripts/deploy/build_hf_tree.py \
  deploy/huggingface/veritas.manifest.json \
  /tmp/veritas-hf-build
```

The build script excludes credentials, databases, uploads, logs, model weights,
indexes, caches, and private evidence by default.

## Required Secret Names

Set secret values only in the hosting platform:

- `CLAIRE_MODEL_ENDPOINT`
- `CLAIRE_MODEL_NAME`
- `COURTLISTENER_API_TOKEN` when CourtListener authenticated API access is used

Do not expose or print secret values in health endpoints, logs, or UI output.

## Deployment Rule

Deploy CLAIRE and Veritas independently. A failed Hugging Face deployment must not
change Azure.
