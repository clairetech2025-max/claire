# Hugging Face Deployment Status

Generated: 2026-07-19T04:13:44Z

## GitHub Source

- Repository: `https://github.com/clairetech2025-max/claire`
- Branch: `codex/claire-core-completion-20260718`
- Last package source SHA verified: `d7e4bff092585b8224d6724dd67db73fcdcdc566`
- Preservation branch: `backup/pre-core-completion-20260718`
- Preservation SHA: `3d5a431df96394e369f81929055e323bd13cb749`

## Verified Local Deployment Packages

CLAIRE package:

- Manifest: `deploy/huggingface/claire.manifest.json`
- Build tree: `/tmp/claire-hf-build-clean`
- Archive: `/tmp/claire-hf-build-clean.tar.gz`
- SHA-256: `7b0d826874d0d93f5ffbafb241a4a3f741886ae78b5ca6ae6b69d3717b50d614`
- Validation: passed
- Import smoke: `app.app` imports and `claire_core.runtime.health.core_health()` reports `AVAILABLE`

Veritas package:

- Manifest: `deploy/huggingface/veritas.manifest.json`
- Build tree: `/tmp/veritas-hf-build-clean`
- Archive: `/tmp/veritas-hf-build-clean.tar.gz`
- SHA-256: `13f393ce6896a9717d35070c7fa950270c57cd8bca103c95bcdb9676049a5138`
- Validation: passed
- Import smoke: FastAPI `/health` returns HTTP 200

## Existing Spaces

Confirmed CLAIRE Space:

- Space ID: `Blackstormhorse/CLAIRE_Control_Interface`
- URL: `https://blackstormhorse-claire-control-interface.hf.space`
- Current Space SHA observed before deployment: `e6afa6e2f7c0e6ded54d738b6135029f8de3d0b9`
- Current Space SDK observed by Hub API: Gradio
- SDK in deployment package manifest: Docker
- Runtime state observed by Hub API: `SLEEPING`
- Hardware requested by Hub API: `cpu-basic`
- Note: deploying the full FastAPI runtime package would convert or replace the current lightweight Gradio Space contents inside the same existing Space. Do not run this upload without explicit approval of that Space-mode transition.

Veritas Space:

- Space ID: unresolved
- Public searches did not find a matching existing Veritas Legal Space.
- `deploy/huggingface/veritas.manifest.json` intentionally keeps `space_id` blank until the exact existing Space ID is confirmed.
- The upload helper refuses to deploy a blank Space ID.

## Current Deployment Blockers

1. Local Hugging Face CLI is not authenticated: `venv/bin/hf auth whoami` returns `Error: Not logged in`.
2. The existing CLAIRE Space is currently a Gradio Space, while the full runtime package is Docker. The transition is technically packaged but should be explicitly approved before upload.
3. The available Hugging Face connector can inspect repos and search Spaces, but does not expose a file upload/deploy command.
4. The existing Veritas Hugging Face Space ID has not been confirmed.

## Upload Commands

CLAIRE:

```bash
PATH="$PWD/venv/bin:$PATH" scripts/deploy/upload_hf_space.sh \
  deploy/huggingface/claire.manifest.json \
  /tmp/claire-hf-build-clean \
  "Deploy CLAIRE mirror from GitHub $(git rev-parse --short HEAD)"
```

Veritas, after filling `space_id` in `deploy/huggingface/veritas.manifest.json`:

```bash
PATH="$PWD/venv/bin:$PATH" scripts/deploy/upload_hf_space.sh \
  deploy/huggingface/veritas.manifest.json \
  /tmp/veritas-hf-build-clean \
  "Deploy Veritas mirror from GitHub $(git rev-parse --short HEAD)"
```

## GitHub Actions Deployment

Workflows:

- `.github/workflows/deploy-claire-hf.yml`
- `.github/workflows/deploy-veritas-hf.yml`

Required GitHub secret:

- `HF_TOKEN`

The Veritas workflow additionally requires the exact existing Veritas Space ID
as a manual workflow input. This avoids committing an unverified or private
Space ID to source.

## Validation Commands

```bash
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/claire-hf-build

venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/veritas-hf-build
```

## Guardrails

- Do not upload private evidence, runtime databases, logs, model files, live `.env` files, credentials, or Azure-only configuration.
- Do not replace Azure. Azure remains untouched while the Hugging Face mirrors are prepared.
- Do not create a new Veritas Space unless the existing Space is proven unusable or unavailable.
