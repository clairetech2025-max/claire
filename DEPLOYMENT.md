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

Check local package readiness without contacting Hugging Face:

```bash
PATH="$PWD/venv/bin:$PATH" venv/bin/python scripts/deploy/hf_deploy_status.py \
  --target deploy/huggingface/claire.manifest.json /tmp/claire-hf-build \
  --target deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build \
  --space-id veritas.manifest.json=<existing-veritas-space-id> \
  --skip-remote
```

Before upload, run the same command without `--skip-remote`. It must pass with
Hugging Face authentication available and with the exact Veritas Space ID.

## GitHub Actions Deployment

Use GitHub Actions for the normal mirror deployment path. Do not upload directly
from an unreviewed local worktree.

Set the repository secret without printing the token:

```bash
gh secret set HF_TOKEN --repo clairetech2025-max/claire
```

Validate the package builders from `main`:

```bash
gh workflow run "Validate Hugging Face Packages" \
  --repo clairetech2025-max/claire \
  --ref main
```

Deploy CLAIRE to the existing CLAIRE Space only after approving the current
Gradio-to-Docker transition:

```bash
gh workflow run "Deploy CLAIRE Hugging Face Space" \
  --repo clairetech2025-max/claire \
  --ref main \
  -f ref=main \
  -f approve_sdk_transition=true
```

Deploy Veritas only after the exact existing Veritas Space ID is known:

```bash
gh workflow run "Deploy Veritas Hugging Face Space" \
  --repo clairetech2025-max/claire \
  --ref main \
  -f ref=main \
  -f veritas_ref=main \
  -f space_id=<existing-veritas-space-id>
```

After either deployment, inspect the run and the Space health endpoint before
calling the mirror operational.

## Required Secret And Variable Names

Repository deployment secret:

- `HF_TOKEN`

CLAIRE Space runtime variables and secrets are declared in
`deploy/huggingface/claire.manifest.json`.

Veritas Space runtime variables are declared in
`deploy/huggingface/veritas.manifest.json`.

Set secret values only in the hosting platform:

- `CLAIRE_MODEL_ENDPOINT`
- `CLAIRE_MODEL_NAME`
- `COURTLISTENER_API_TOKEN` when CourtListener authenticated API access is used

Do not expose or print secret values in health endpoints, logs, or UI output.

## Deployment Rule

Deploy CLAIRE and Veritas independently. A failed Hugging Face deployment must not
change Azure.

Do not create a new Veritas Space unless the existing Space is proven unusable or
unavailable. Public discovery currently confirms
`Blackstormhorse/CLAIRE_Control_Interface`; the Veritas Space ID remains a
deployment input until authenticated discovery or user confirmation provides it.
