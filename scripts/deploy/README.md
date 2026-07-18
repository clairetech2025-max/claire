# Hugging Face Deployment

Build a Space-specific deployment tree from a manifest:

```bash
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build
venv/bin/python scripts/deploy/validate_hf_tree.py /tmp/claire-hf-build
```

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

Do not deploy private databases, uploaded legal evidence, model files, live `.env`
files, or Azure-only configuration.
