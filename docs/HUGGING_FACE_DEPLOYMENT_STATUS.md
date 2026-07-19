# Hugging Face Deployment Status

Generated: 2026-07-19T05:15:00Z

## GitHub Source

- Repository: `https://github.com/clairetech2025-max/claire`
- Branch: `main`
- Current main SHA: `2d9afc999d46f7ab18be2fd0f085fd4b15f7aaed`
- Last package source SHA verified by GitHub Actions: `2d9afc999d46f7ab18be2fd0f085fd4b15f7aaed`
- Last Veritas source SHA verified in package: `abf568ce0b1b28631775278e164b5edc5a109626`
- Prior main merge SHA: `da56a2ac46d1d513b33d3694d8288fedd233e10e`
- Last package source SHA verified after PR #4 merge: `9dded264deb1b6b3b77dfe025ae1c2b0d3986280`
- Prior Veritas source SHA verified in package: `fb8dc7620fe25735d6c7521481df9febff485e7f`
- Prior main merge SHA: `7e724c8752218672a3238f14d83019c1717efc2e`
- Preservation branch: `backup/pre-core-completion-20260718`
- Preservation SHA: `3d5a431df96394e369f81929055e323bd13cb749`

## Verified Local Deployment Packages

CLAIRE package:

- Manifest: `deploy/huggingface/claire.manifest.json`
- Build tree: `/tmp/claire-hf-main-build-clean`
- Archive: `/tmp/claire-hf-main-build-clean.tar.gz`
- SHA-256: `235cbb1ef369679785fea10e31d4f06723063e8f79891fd7b3db8f1b427563f5`
- Validation: passed after PR #4 merge
- Local preflight: passed with `--skip-remote`

Veritas package:

- Manifest: `deploy/huggingface/veritas.manifest.json`
- Build tree: `/tmp/veritas-hf-main-build-clean`
- Archive: `/tmp/veritas-hf-main-build-clean.tar.gz`
- SHA-256: `b5c9a80ecfdfaa78560394efc5472f692fa61fa9f2b5c45fa40cb82d127b45f1`
- Validation: passed after PR #4 merge
- Local preflight: passed with `--skip-remote`

## Existing Spaces

Confirmed CLAIRE Space:

- Space ID: `Blackstormhorse/CLAIRE_Control_Interface`
- URL: `https://blackstormhorse-claire-control-interface.hf.space`
- Current Space SHA observed before deployment: `e6afa6e2f7c0e6ded54d738b6135029f8de3d0b9`
- Current Space SDK observed by Hub API: Gradio
- SDK in deployment package manifest: Docker
- Runtime state observed by Hub API: `RUNNING`
- Hardware requested by Hub API: `cpu-basic`
- Note: deploying the full FastAPI runtime package would convert or replace the current lightweight Gradio Space contents inside the same existing Space. Do not run this upload without explicit approval of that Space-mode transition.

Veritas Space:

- Space ID: unresolved
- Public listing for `Blackstormhorse` shows only `Blackstormhorse/ARE_Memory_Module` and `Blackstormhorse/CLAIRE_Control_Interface`.
- Public searches did not find a matching existing Veritas Legal Space under `Blackstormhorse`.
- `deploy/huggingface/veritas.manifest.json` intentionally keeps `space_id` blank until the exact existing Space ID is confirmed.
- The upload helper refuses to deploy a blank Space ID.

## Current Deployment Blockers

1. Local Hugging Face CLI is not authenticated: `venv/bin/hf auth whoami` returns `Error: Not logged in`.
2. GitHub repository secret `HF_TOKEN` is not confirmed/configured for upload completion.
3. The existing CLAIRE Space is currently a Gradio Space, while the full runtime package is Docker. The transition is technically packaged but requires explicit approval before upload.
4. The available Hugging Face connector can inspect repos and search Spaces, but does not expose a file upload/deploy command.
5. The existing Veritas Hugging Face Space ID has not been confirmed.

## Deployed Source Identity Gate

CLAIRE and Veritas deployment packages include `deployment.identity.json`.
The application health endpoints expose that identity as a safe `deployment`
object. The deployment workflows pass only when `scripts/deploy/hf_wait_for_space.py`
confirms the running Space reports the expected approved source.

Required post-deploy checks:

- CLAIRE: `/health` must report `deployment.source_git_sha` matching the
  checked-out CLAIRE source SHA and `deployment.source_git_ref` matching the
  checked-out CLAIRE source ref.
- Veritas: `/health` must report the same CLAIRE wrapper SHA/ref and must also
  include the checked-out Veritas app SHA in
  `deployment.included_sources[*].source_git_sha`.

This prevents a stale Space from passing merely because its health endpoint
returns HTTP 200.

## Upload Preflight

The upload helper runs `scripts/deploy/preflight_hf_space.py` before `hf upload`.
Use `scripts/deploy/hf_deploy_status.py` for a non-destructive readiness report
across CLAIRE and Veritas before attempting either upload.

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
- `Validate Hugging Face Packages` passed automatically on push for source-identity deployment gating on `2d9afc999d46f7ab18be2fd0f085fd4b15f7aaed`.
- Validation run: `https://github.com/clairetech2025-max/claire/actions/runs/29674350823`
- `Validate Hugging Face Packages` passed automatically on push for both CLAIRE and Veritas on `9dded264deb1b6b3b77dfe025ae1c2b0d3986280`.
- Validation run: `https://github.com/clairetech2025-max/claire/actions/runs/29674009409`
- Prior failed validation on `1c3ecfaaec23c018618e41a73e0d7acf224eefd1` exposed an invalid CLAIRE smoke-test dependency assumption; fixed by `9dded264deb1b6b3b77dfe025ae1c2b0d3986280`.
- Prior validation run on `b3f9195427ce8a9d62f55175c2fdbebf7013c68a`: `https://github.com/clairetech2025-max/claire/actions/runs/29673818267`
- Prior validation run on `7aaf17bf360c35eb81ed68aad7a6a06ef52178f0`: `https://github.com/clairetech2025-max/claire/actions/runs/29673720507`
- Prior validation run on `fc6f54b834b90a6e12a2c827939fae9444bddd17`: `https://github.com/clairetech2025-max/claire/actions/runs/29673614128`
- Prior validation run on `d43cecfcefa11875b184a461ad1e8fd3c8d5de49`: `https://github.com/clairetech2025-max/claire/actions/runs/29673485653`
- Prior validation run on `81f61d3dc929c23f7029b03c429960f64866ff4b`: `https://github.com/clairetech2025-max/claire/actions/runs/29673393293`
- Prior validation run on `04acbf4f4729784f3327ccab7fb65706eb934a8f`: `https://github.com/clairetech2025-max/claire/actions/runs/29673302302`
- An earlier `Deploy CLAIRE Hugging Face Space` run on `7e724c8752218672a3238f14d83019c1717efc2e` passed checkout, build, package validation, and smoke import, then stopped at the explicit `HF_TOKEN secret is required` gate.
- Earlier guarded deploy run: `https://github.com/clairetech2025-max/claire/actions/runs/29661032040`

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

Readiness report:

```bash
PATH="$PWD/venv/bin:$PATH" venv/bin/python scripts/deploy/hf_deploy_status.py \
  --target deploy/huggingface/claire.manifest.json /tmp/claire-hf-build-clean \
  --target deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build-clean \
  --space-id veritas.manifest.json=<existing-veritas-space-id>
```

## Guardrails

- Do not upload private evidence, runtime databases, logs, model files, live `.env` files, credentials, or Azure-only configuration.
- Do not replace Azure. Azure remains untouched while the Hugging Face mirrors are prepared.
- Do not create a new Veritas Space unless the existing Space is proven unusable or unavailable.
