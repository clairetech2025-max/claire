# Hugging Face Deployment Status

Generated: 2026-07-18

## GitHub Source

- Repository: `https://github.com/clairetech2025-max/claire`
- Branch: `codex/claire-core-completion-20260718`
- Current SHA: `d568c11f8d6e55dd0cd18befea450e4dac640ffd`
- Preservation branch: `backup/pre-core-completion-20260718`
- Preservation SHA: `3d5a431df96394e369f81929055e323bd13cb749`

## Verified Local Deployment Packages

CLAIRE package:

- Manifest: `deploy/huggingface/claire.manifest.json`
- Build tree: `/tmp/claire-hf-build`
- Archive: `/tmp/claire-hf-build.tar.gz`
- SHA-256: `e3ab0d9ae457d712abcea1a4bfb548ae53ee56034d9f3da6d3e2d9d7457ec54e`
- Validation: passed
- Import smoke: `app.app` imports and `claire_core.runtime.health.core_health()` reports `AVAILABLE`

Veritas package:

- Manifest: `deploy/huggingface/veritas.manifest.json`
- Build tree: `/tmp/veritas-hf-build`
- Archive: `/tmp/veritas-hf-build.tar.gz`
- SHA-256: `5ba0e9cf4a5b1288ba6be14fe5b0195df26e1e928b4373f65355284a1e3f8618`
- Validation: passed
- Import smoke: FastAPI `/health` returns HTTP 200

## Existing Spaces

Confirmed CLAIRE Space:

- Space ID: `Blackstormhorse/CLAIRE_Control_Interface`
- URL: `https://blackstormhorse-claire-control-interface.hf.space`
- Previous Space SHA observed before deployment: `e6afa6e2f7c0e6ded54d738b6135029f8de3d0b9`
- SDK in manifest: Docker

Veritas Space:

- Space ID: unresolved
- Public searches did not find a matching existing Veritas Legal Space.
- `deploy/huggingface/veritas.manifest.json` intentionally keeps `space_id` blank until the exact existing Space ID is confirmed.
- The upload helper refuses to deploy a blank Space ID.

## Current Deployment Blockers

1. Local Hugging Face CLI is not authenticated: `hf auth whoami` returns `Error: Not logged in`.
2. The available Hugging Face connector can inspect repos and search Spaces, but does not expose a file upload/deploy command.
3. The existing Veritas Hugging Face Space ID has not been confirmed.

## Upload Commands

CLAIRE:

```bash
PATH="$PWD/venv/bin:$PATH" scripts/deploy/upload_hf_space.sh \
  deploy/huggingface/claire.manifest.json \
  /tmp/claire-hf-build \
  "Deploy CLAIRE mirror from GitHub d568c11"
```

Veritas, after filling `space_id` in `deploy/huggingface/veritas.manifest.json`:

```bash
PATH="$PWD/venv/bin:$PATH" scripts/deploy/upload_hf_space.sh \
  deploy/huggingface/veritas.manifest.json \
  /tmp/veritas-hf-build \
  "Deploy Veritas mirror from GitHub d568c11"
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
