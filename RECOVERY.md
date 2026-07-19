# Recovery

## Preservation Point

Before CLAIRE Core completion work began, a preservation branch and verified Git
bundle were created.

- Preservation branch: `backup/pre-core-completion-20260718`
- Starting commit: `3d5a431df96394e369f81929055e323bd13cb749`
- Local bundle: `/home/LuciusPrime/claire_preservation_20260718/claire-full-backup.bundle`

Verify the bundle:

```bash
git bundle verify /home/LuciusPrime/claire_preservation_20260718/claire-full-backup.bundle
```

Clone from the bundle:

```bash
git clone /home/LuciusPrime/claire_preservation_20260718/claire-full-backup.bundle claire-recovered
```

## Runtime Data

Do not commit private runtime state. Back up sensitive material through an
approved private channel:

- ARE stores
- Truth Spine JSONL files
- Ember handoffs
- SQLite databases
- indexes
- uploaded evidence
- deployment secrets

## Rollback

Rollback source to the preservation branch:

```bash
git switch backup/pre-core-completion-20260718
```

Rollback Hugging Face by redeploying the previous known-good Space commit shown
in the Space commit history. CLAIRE and Veritas roll back independently.

Azure is not managed by this repository-level rollback and should be left online
while it remains available.

## Hugging Face Mirror Recovery

If Azure disappears, recover from GitHub plus the Hugging Face Spaces rather than
from Azure-local state.

1. Clone the authoritative source:

```bash
git clone https://github.com/clairetech2025-max/claire.git
cd claire
```

2. Install deployment tooling:

```bash
python -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install "huggingface_hub[cli]" pytest
```

3. Build and check sanitized Space trees:

```bash
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/claire.manifest.json /tmp/claire-hf-build
venv/bin/python scripts/deploy/build_hf_tree.py deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build
PATH="$PWD/venv/bin:$PATH" venv/bin/python scripts/deploy/hf_deploy_status.py \
  --target deploy/huggingface/claire.manifest.json /tmp/claire-hf-build \
  --target deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-build \
  --space-id veritas.manifest.json=<existing-veritas-space-id>
```

4. Redeploy through GitHub Actions from an approved commit or tag. Keep CLAIRE
and Veritas rollback separate.

```bash
gh workflow run "Deploy CLAIRE Hugging Face Space" \
  --repo clairetech2025-max/claire \
  --ref main \
  -f ref=<approved-git-ref> \
  -f approve_sdk_transition=true

gh workflow run "Deploy Veritas Hugging Face Space" \
  --repo clairetech2025-max/claire \
  --ref main \
  -f ref=<approved-git-ref> \
  -f veritas_ref=main \
  -f space_id=<existing-veritas-space-id>
```

5. Verify health, smoke behavior, and the deployed GitHub SHA from each Space.

Do not restore private legal evidence, live databases, uploaded documents, or
runtime logs into a public Space. Use sanitized demo data unless a private
persistent storage plan has been approved.
