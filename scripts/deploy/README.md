# Hugging Face Deployment

Build a Space-specific deployment tree from a manifest:

```bash
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/claire-hf-build
venv/bin/python scripts/deploy/preflight_hf_space.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build --skip-remote
```

Check readiness without uploading:

```bash
PATH="$PWD/venv/bin:$PATH" venv/bin/python scripts/deploy/hf_deploy_status.py \
  --target deploy/huggingface/claire.manifest.json /tmp/claire-hf-build \
  --target deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build \
  --space-id veritas.manifest.json=<existing-veritas-space-id>
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

GitHub Actions workflows are also available:

- `.github/workflows/deploy-claire-hf.yml`
- `.github/workflows/deploy-veritas-hf.yml`

Both workflows require the repository secret `HF_TOKEN`. The Veritas workflow
also requires the existing Veritas Space ID as a manual workflow input.

Do not deploy private databases, uploaded legal evidence, model files, live `.env`
files, or Azure-only configuration.
