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
