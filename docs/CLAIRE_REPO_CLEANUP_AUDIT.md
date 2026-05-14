# Claire Repository Cleanup Audit

## Purpose

This file explains what "messy" means in the Claire workspace and how to clean it without breaking the live demo.

## Current State

The private GitHub branch is controlled and reviewable. The active git status was clean after removing a stray untracked `package-lock.json`.

The local VM workspace still contains many ignored backup, log, archive, cache, and runtime files. That clutter is normal for a fast-moving prototype, but it should not be confused with the curated repository state.

Observed local clutter categories:

- many `*.bak*` point-in-time backups
- runtime logs such as `gui.log`, `server.log`, `are.log`, and related service logs
- local archives and bundles
- Python cache and virtual environment directories
- private runtime data directories ignored by `.gitignore`

These are intentionally not pushed unless explicitly tracked.

## What Is Already Better

- Private GitHub repository verified.
- Documentation package created under `docs/`.
- Private draft PR opened for review.
- Response-layer tests passing.
- Browser voice fallback added when ElevenLabs TTS is unauthorized/offline.
- Stray untracked `package-lock.json` removed.
- README added as a private repo entry point.

## What Should Not Be Cleaned Blindly

Do not delete these without an explicit archival decision:

- production memory data
- uploaded documents
- secrets/env files
- Gumroad/private product material
- benchmark source artifacts
- service configs
- deployment scripts
- old backups that may contain recovery context

## Recommended Cleanup Phases

### Phase 1: Repository Presentation

- Keep `README.md` current.
- Keep `docs/` focused and conservative.
- Keep `.gitignore` strict around secrets, logs, data, caches, archives, and local builds.
- Keep regression tests passing.

### Phase 2: Local Workspace Archival

- Create a dated local archive folder outside the repo for old `*.bak*` files.
- Move old logs and large archives out of the working tree.
- Preserve only the latest known-good backups needed for recovery.

### Phase 3: Source Consolidation

- Identify active runtime entrypoints.
- Mark old prototype files as archived, deprecated, or active.
- Avoid deleting old prototypes until current live behavior has test coverage.

### Phase 4: Public Package Split

- Create a separate public repo only after review.
- Include sanitized docs, benchmark summaries, reproducible scripts, and safe diagrams.
- Exclude secrets, logs, private memories, Gumroad build material, and live runtime internals.

## Definition of Cleaner

Claire is cleaner when:

- a new developer can start with `README.md`
- claims live in `docs/`
- behavior is covered by tests
- private/runtime material is not mixed with public material
- old prototypes are labeled or archived
- live GUI, voice visualizer, ARE, Sentinel, trace, and demo behavior remain stable
