# Hugging Face Deployment

Build a Space-specific deployment tree from a manifest:

```bash
export CLAIRE_SOURCE_SHA="$(git rev-parse HEAD)"
export CLAIRE_SOURCE_REF="$(git branch --show-current)"
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/claire-hf-build
venv/bin/python scripts/deploy/preflight_hf_space.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build --skip-remote
```

Check readiness without uploading:

```bash
PATH="$PWD/venv/bin:$PATH" venv/bin/python scripts/deploy/hf_deploy_status.py \
  --target deploy/huggingface/claire.manifest.json /tmp/claire-hf-build \
  --target deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build \
  --space-id veritas.manifest.json=<existing-veritas-space-id> \
  --github-repo clairetech2025-max/claire \
  --require-github-secret HF_TOKEN
```

Use `--skip-remote` only for local package checks. A real upload should first
pass the remote status check with Hugging Face authentication available.

Upload requires Hugging Face authentication:

```bash
venv/bin/hf auth login
venv/bin/hf upload Blackstormhorse/CLAIRE_Control_Interface /tmp/claire-hf-build . --type space --commit-message "Deploy CLAIRE mirror from approved GitHub revision"
```

Build Veritas after the existing Veritas Space ID is filled into
`deploy/huggingface/veritas.manifest.json`:

```bash
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/veritas-hf-build
```

The upload helper refuses to deploy when `space_id` is blank:

```bash
PATH="$PWD/venv/bin:$PATH" scripts/deploy/upload_hf_space.sh \
  deploy/huggingface/claire.manifest.json \
  /tmp/claire-hf-build \
  "Deploy CLAIRE mirror from approved GitHub revision"
```

Before upload, the helper also runs `preflight_hf_space.py` without
`--skip-remote`. That gate requires Hugging Face authentication, confirms the
existing Space can be inspected, and refuses SDK/runtime-mode transitions unless
`HF_APPROVE_SDK_TRANSITION=true` is set intentionally. This prevents accidentally
replacing a lightweight Gradio Space with a Docker runtime package.

After upload, wait for runtime and health:

```bash
PATH="$PWD/venv/bin:$PATH" venv/bin/python scripts/deploy/hf_wait_for_space.py \
  deploy/huggingface/claire.manifest.json \
  --expected-source-sha "$CLAIRE_SOURCE_SHA" \
  --expected-source-ref "$CLAIRE_SOURCE_REF"

PATH="$PWD/venv/bin:$PATH" HF_SPACE_ID=<existing-veritas-space-id> \
  venv/bin/python scripts/deploy/hf_wait_for_space.py \
  deploy/huggingface/veritas.manifest.json \
  --expected-source-sha "$CLAIRE_SOURCE_SHA" \
  --expected-source-ref "$CLAIRE_SOURCE_REF" \
  --expected-included-source-sha <veritas-source-sha>
```

The wait script treats a stale deployment as a failure. The Space must expose a
`deployment` object from `/health` whose `source_git_sha` and `source_git_ref`
match the approved CLAIRE checkout. Veritas must also expose the included
Veritas app SHA in `deployment.included_sources`.

GitHub Actions workflows are also available:

- `.github/workflows/security-source-scan.yml`
- `.github/workflows/hf-deployment-readiness.yml`
- `.github/workflows/deploy-claire-hf.yml`
- `.github/workflows/deploy-veritas-hf.yml`

Run the security source scan before deployment readiness. It scans tracked
source for token-shaped values, private keys, Azure connection strings, and
private runtime artifacts.

Run the readiness workflow first. It builds both packages, checks local package
validity, checks the `HF_TOKEN` repository secret name, optionally inspects the
live Spaces when credentials and the Veritas Space ID are available, and never
uploads.

Both deploy workflows require the repository secret `HF_TOKEN`. The Veritas
workflow also requires the existing Veritas Space ID as a manual workflow input.
The deploy workflows capture the actual checked-out source SHAs, upload those
packaged trees, then require the Space health endpoint to report the same SHAs.

Do not deploy private databases, uploaded legal evidence, model files, live `.env`
files, or Azure-only configuration.
