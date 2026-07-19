# Hugging Face Deployment Status

Generated: 2026-07-19

## GitHub Source

- Repository: `https://github.com/clairetech2025-max/claire`
- Working branch: `codex/claire-core-completion-20260718`
- Merged upstream baseline: `origin/main` at `1c5022ec7e6ccde694f8f60a4e61e4b6b6fa3a6f`
- Last package source SHA verified before merge refresh: `8ff33fc370c5fb2f8443cd13c4a582a61bfacc77`
- Prior main merge SHA: `7e724c8752218672a3238f14d83019c1717efc2e`
- Preservation branch: `backup/pre-core-completion-20260718`
- Preservation SHA: `3d5a431df96394e369f81929055e323bd13cb749`

## Verified Local Deployment Packages

CLAIRE package:

- Manifest: `deploy/huggingface/claire.manifest.json`
- Build tree: `/tmp/claire-hf-build-clean`
- Archive: `/tmp/claire-hf-build-clean.tar.gz`
- SHA-256: pending refresh after the current merge commit is finalized
- Validation: passed before merge refresh; rerun required after merge resolution
- Import smoke: `app.app` imports and `claire_core.runtime.health.core_health()` reports `AVAILABLE` before merge refresh

Veritas package:

- Manifest: `deploy/huggingface/veritas.manifest.json`
- Build tree: `/tmp/veritas-hf-build-clean`
- Archive: `/tmp/veritas-hf-build-clean.tar.gz`
- SHA-256: pending refresh after the current merge commit is finalized
- Validation: passed before merge refresh; rerun required after merge resolution
- Import smoke: FastAPI `/health` returns HTTP 200 before merge refresh

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
2. GitHub repository secret `HF_TOKEN` is not confirmed/configured for upload completion.
3. The existing CLAIRE Space is currently a Gradio Space, while the full runtime package is Docker. The transition is technically packaged but requires explicit approval before upload.
4. The available Hugging Face connector can inspect repos and search Spaces, but does not expose a file upload/deploy command.
5. The existing Veritas Hugging Face Space ID has not been confirmed.

## Upload Preflight

The upload helper runs `scripts/deploy/preflight_hf_space.py` before `hf upload`.

Verified local package preflight commands:

```bash
venv/bin/python scripts/deploy/preflight_hf_space.py \
  deploy/huggingface/claire.manifest.json \
  /tmp/claire-hf-build-clean \
  --skip-remote

HF_SPACE_ID=Blackstormhorse/VERITAS_PLACEHOLDER \
  venv/bin/python scripts/deploy/preflight_hf_space.py \
  deploy/huggingface/veritas.manifest.json \
  /tmp/veritas-hf-build-clean \
  --skip-remote
```

The full remote preflight intentionally fails in the current local environment with:

```text
Hugging Face authentication unavailable; set HF_TOKEN or run `hf auth login`.
```

When authenticated, the preflight also inspects the existing Space and refuses
SDK/runtime-mode transitions unless `HF_APPROVE_SDK_TRANSITION=true` is set.
For GitHub Actions, this is exposed as the manual `approve_sdk_transition`
workflow-dispatch input on `.github/workflows/deploy-claire-hf.yml`. This is
currently relevant because `Blackstormhorse/CLAIRE_Control_Interface` is a
Gradio Space and the prepared full-runtime package is Docker.

## Post-Merge Verification History

- PR #3 was merged into `main` before this branch's latest preflight work.
- Main validation from a clean worktree passed: `117 passed, 1 skipped`.
- Main CLAIRE Hugging Face package validation passed.
- Main Veritas Hugging Face package validation passed.
- GitHub Actions workflows are active on `main`.
- `Validate Hugging Face Packages` passed for both CLAIRE and Veritas.
- `Deploy CLAIRE Hugging Face Space` was manually dispatched from `main`; it passed checkout, build, package validation, and smoke import, then stopped at the explicit `HF_TOKEN secret is required` gate.

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

The CLAIRE workflow additionally requires the manual `approve_sdk_transition`
input before replacing the existing Gradio Space with the packaged Docker runtime.
The Veritas workflow additionally requires the exact existing Veritas Space ID
as a manual workflow input. This avoids committing an unverified or private
Space ID to source.

## Validation Commands

```bash
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build-clean
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/claire-hf-build-clean
venv/bin/python scripts/deploy/preflight_hf_space.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build-clean --skip-remote

venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build-clean
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/veritas-hf-build-clean
HF_SPACE_ID=<existing-veritas-space-id> venv/bin/python scripts/deploy/preflight_hf_space.py deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build-clean --skip-remote
```

## Guardrails

- Do not upload private evidence, runtime databases, logs, model files, live `.env` files, credentials, or Azure-only configuration.
- Do not replace Azure. Azure remains untouched while the Hugging Face mirrors are prepared.
- Do not create a new Veritas Space unless the existing Space is proven unusable or unavailable.
