# CLAIRE / VERITAS Emergency Preservation Archive

Date: 2026-07-21
Author: Claude (Claude Code), acting on the Azure VM `clairetemp` at the direction of the CLAIRE Systems operator.

## What this document is

A record of the Phase 2 GitHub preservation pass performed on the live Azure
deployment ahead of building Hugging Face twins of CLAIRE and VERITAS. It
explains what was preserved, where, what's production, what's valuable-but-inactive,
what was deliberately excluded, and how to get any of it back.

## What was preserved, and where

| Repo | Branch | Commit SHA | Verified against remote |
|---|---|---|---|
| `clairetech2025-max/claire` | `emergency-rescue-20260721` | `adf0d0a65acd02dd8fcdf6a7a2dcff4c4763f543` | Yes, via `git ls-remote` |
| `clairetech2025-max/claire-veritas-legal` | `emergency-rescue-20260721` | `55bb949bc2c7142e29d7862d3c781423773e0240` | Yes, via `git ls-remote` |
| `clairetech2025-max/claire` (category B focus) | `azure-code-archive-2026-07-20` | branched from the rescue commit above | Yes |

Both `emergency-rescue-20260721` branches are pushed to GitHub and independently
verified: the local commit SHA was compared against `git ls-remote origin` output
after pushing, not just trusted from the push confirmation text.

**Important finding from this pass:** most of the CLAIRE repo's directory structure
(`claire_are/`, `claire_core/`, `claire_sentinel/`, `sentinel_core/`, `apex/`,
`are_hf_demo/`, `gumroad_builds/`, `claire_control_interface/`, `experiments/`,
`configs/`, `hf_space/`, `hf_claire_runtime_full/`, `claire_continuity/`,
`veritas_legal/`) was **already tracked on `main` before this rescue pass** — it was
not actually at risk. What genuinely needed rescuing and is new as of this branch:
the Truth Spine timeout fix, the `claire_vde` venture-subsystem files, the
`veritas/` trading-engine Python source, session audit documentation, and (in the
separate Veritas repo) the paused teacher-mode module. See `CODE_INVENTORY.csv`
column `already_on_github_main_before_rescue` for the exact breakdown.

## Methodology and granularity (read this before trusting a "yes/no" in the CSV)

`CODE_INVENTORY.csv` classifies at **directory level for most of the repo**, with
**individual rows for every root-level Python module confirmed by direct import
grep against `claire_gui.py` and `claire_runtime.py`** (21 confirmed this way,
matching everything independently traced deeply earlier in this investigation).
It is not a literal file-by-file audit of all ~186 root-level files or the full
`tests/`/`docs/` trees — that would be several hundred additional rows of
low-information "test file, untraced" entries. Where a classification is based on
a quick surface check rather than a full trace (e.g. `apex/`, `sentinel_core/`,
`configs/`), the CSV's `recommended_future_use` column says so explicitly and
flags it as needing a follow-up read. Treat directory-level rows as "this bucket
needs a look," not as a guarantee that every file inside shares one uniform fate.

## Category definitions (as used in CODE_INVENTORY.csv)

- **A — ACTIVE_PRODUCTION**: confirmed this session, either by direct import-grep
  against the live `claire_gui.py`/`claire_runtime.py` call graph, or by a running
  systemd service / Docker container command line pointing directly at it.
- **B — INACTIVE_BUT_VALUABLE**: real, non-trivial code not currently wired into
  a live process. Preserved, not deleted, regardless of activity status.
- **C — DUPLICATE_OR_OBSOLETE**: generated output, caches, or content that
  duplicates something already preserved elsewhere (e.g. `github_cleanup_audit/`
  duplicates repos that already have their own GitHub history). Not deleted —
  excluded from this commit via `.gitignore`, pending independent verification.
- **D — SENSITIVE_OR_RUNTIME_DATA**: secrets, databases, logs, uploaded evidence,
  model weights, user data. Never committed. Excluded via `.gitignore`.

## Most significant B-category (inactive but valuable) findings

- **The true original 70-line `AREStore` class** lives entirely outside this repo
  at `/home/LuciusPrime/original_are.pyiginal_are.py/are.py` and is imported by
  nothing. It is not part of either GitHub rescue branch. This needs a separate,
  explicit preservation action if it matters — it's called out here so it isn't
  silently lost.
- **Three more divergent `AREStore`-named implementations** exist inside the repo
  (`claire_are/core.py`, `veritas/veritas_trader_engine.py`), plus a fourth
  concept (`are_memory_store.py`) that IS imported but not instantiated by
  default. None of the four agree on method signatures or storage format.
- **At least three separate "Sentinel" implementations**: the live one
  (`claire_core/adapters/sentinel.py`, confirmed wired into `claire_runtime.py`),
  and two unrelated packages (`claire_sentinel/`, `sentinel_core/`) that are not
  wired into anything live.
- **At least four separate Hugging Face demo/deployment scaffolds**:
  `are_hf_demo/`, `claire_are/hf_demo_app.py`, `hf_space/`, and
  `hf_claire_runtime_full/` — plus `claire_control_interface/`, which is
  confirmed (via a live Hugging Face lookup this session) to be the actual
  current source of the `Blackstormhorse/CLAIRE_Control_Interface` Space, and
  whose own docstring says *"This is not production CLAIRE. It is a controlled
  demo."* Of the deployment scaffolds, `hf_claire_runtime_full/app.py` is the
  one that actually re-exports the real `claire_gui:app` rather than
  reimplementing a substitute — it's the strongest candidate for the Phase 3 twin.
- **`Lycanthrope`** (`claire_core/adapters/lycanthrope.py`) — a static
  permission-matrix class with no threads, async loop, or detection logic,
  confirmed to have zero references anywhere in `claire_runtime.py`. Preserved
  as-is; not currently doing the overwatch job its name implies.
- **The Veritas paused teacher-mode module** (`_paused_global_claire_teacher_mode/`
  in the `claire-veritas-legal` repo) — six real source files for a
  correction-learning feature, previously entirely untracked in git.

## What was excluded, and why

| Excluded | Reason | Where it still lives |
|---|---|---|
| `/models` (GGUF weights, ~30GB) | Binary model weights, explicitly out of scope for source preservation | Symlink target: `/mnt/inspect_nvme0n2p1/.../CLAIRE_SAFE_STORAGE/claire_backup_20260616_163412/models` — a backup mechanism that appears to already exist independently; **not verified by this session**, flagged for separate confirmation |
| `github_cleanup_audit/` | Contains full clones of other GitHub repos, some with broken embedded git state that `git add` itself refused | Each cloned repo has its own GitHub history already |
| `veritas/veritas_system_ledger.db`, `veritas/paper_state*/`, `veritas/are_data/`, `veritas/public_candles/`, `veritas/run_logs/` | Runtime databases and trading state, not source | Live on disk at `/home/LuciusPrime/claire/veritas/`, untouched |
| `claire_state/sentinel/` | Generated runtime action log | Live on disk, untouched |
| `benchmark_results/` | Generated benchmark output, regenerable from `benchmarks/are_truth_spine_sustained_load.py` | Live on disk, untouched |
| All `.log`, `.db`, `.sqlite` files; `.env`/secrets/keys | Runtime data and credentials | Untouched on disk; never entered git |

Nothing was deleted from Azure. All exclusions are `.gitignore` additions only —
the underlying files remain exactly where they were.

## Google Drive backup — verified this session

`EVACUATION_MANIFEST.txt`'s own planned folder name (`CLAIRE_SYSTEMS_BACKUP/`)
was **not found** — that specific structure was never created; the manifest's
own text confirms it was planning-only. However, three separate, real backup
efforts **do** exist in the same Drive account (`clairetech2025@gmail.com`),
found via direct search and confirmed via file metadata and content, not assumed:

| Folder | Created | Contents (verified) | Currency vs. today (2026-07-21) |
|---|---|---|---|
| `claire_source/` | 2026-04-21 | Single stale snapshot of `claire_gui.py` (227,455 bytes, dated 2026-04-20) + README | **Badly stale** — the live file is now 693,317 bytes; this snapshot predates 3 months of development |
| `CLAIRE_AZURE_EVACUATION_20260701/bundles/` | 2026-07-01 | One 149,804,717-byte (~143MB) `claire_azure_redeploy_bundle_20260701_051144.tar.gz` | Not opened/decompressed this session; existence, size, and creation date confirmed via Drive metadata only |
| `CLAIRE_FULL_PRESERVATION_2026/` | 2026-07-11 | See below — the most rigorous of the three | **10 days stale** relative to today; does not include this session's work (Truth Spine fix, `claire_vde` additions, this inventory) |

`CLAIRE_FULL_PRESERVATION_2026/02_source_snapshots/` is genuinely well-built:
7 source-only tarballs covering `claire`, `claire-veritas-legal`,
`analog-recall-engine`, `veritas-legal-evidence-engine-public`,
`are-spectacle-v2`, `odyssey-claire-build`, and `historical-claire-engine-source`,
each paired with a `git status`/`git log` snapshot at backup time, plus a full
`claire_git_head_20260711T004059Z.tar.gz` git bundle (777,738 bytes) of the main
repo, a worktree patch, and — critically — a `SOURCE_ONLY_BUNDLE_MANIFEST.json`
and `SOURCE_ONLY_BUNDLE_CHECKSUMS.sha256` recording SHA256 hashes and exact
source paths for every bundle. That manifest's own exclusion policy ("excludes
venvs/caches/raw data/databases/jsonl/model weights/secrets/env files/keys/
tokens/private runtime state") matches this session's Category D reasoning
independently.

`CLAIRE_FULL_PRESERVATION_2026/04_read_only_disk_inventory/` **independently
confirms the model-weights backup** flagged as unverified elsewhere in this
document: it documents a checksummed backup at
`CLAIRE_SAFE_STORAGE/claire_backup_20260616_163412/` on the separate mounted
disk `/mnt/inspect_nvme0n2p1` (170,426 files, 31.5GB scanned), with its own
`VERIFY.log`, `SHA256SOURCE_*`/`SHA256DEST_*` hash files, and a `MANIFEST_files.txt`
— a real, checksummed backup, not an assumption. The same inventory flags that a
separate 440GB disk (`/dev/nvme1n1`) is attached but unmounted and unidentified,
and explicitly recommends Azure portal confirmation before any use — carrying
that caution forward here rather than re-verifying it independently this session.

**What this session did NOT do**: download and decompress any of these bundles
to do a byte-level diff or checksum re-verification against the live Azure
source. Verification here is based on Drive-side metadata, the bundle manifest's
own recorded checksums, and content snippets — strong evidence that real,
structured backups exist and are recent, but not an independent re-hash of
their contents against disk. If that stronger guarantee is needed, it's the
next concrete step, not something to assume from this pass.

**Bottom line**: a Google Drive backup is confirmed to exist and is real, but
the newest one is 10 days behind the current GitHub rescue branches produced
this session — **the GitHub rescue branches, not Drive, are the most current
preserved source right now.**

## How to restore each component

- **Category A (production)**: already running; no restore needed. If ever
  reverted, `git checkout main` in `/home/LuciusPrime/claire` or
  `/home/LuciusPrime/claire_repos/claire-veritas-legal` returns to the
  pre-rescue state; `git checkout emergency-rescue-20260721` returns the
  preserved state including the Truth Spine timeout fix.
- **Category B (inactive but valuable)**: present in the working tree on both
  `emergency-rescue-20260721` and `azure-code-archive-2026-07-20`. To use any
  of it, check it out from either branch — nothing needs to be "recovered" from
  a separate archive location; it's sitting in the normal repo tree, just not
  imported by the live entry points.
- **Category C (excluded, not deleted)**: still present on local disk at its
  original path; add it back to git explicitly (`git add -f <path>`) if a
  future decision reverses the exclusion.
- **Category D (sensitive/runtime data)**: intentionally never in git. Restore
  from whatever operational backup mechanism governs the live databases/logs —
  not from this archive.

## Next steps flagged by this pass (not yet done)

1. Independently verify the Google Drive backup claim per the instructions
   (folder identity, file counts, size, openability, creation date, manifest
   comparison) rather than relying on the planning-only manifest.
2. Resolve the AREStore/Sentinel/HF-demo-scaffold duplication clusters —
   decide which implementation is canonical in each case and document it.
3. Confirm whether `CLAIRE_NEMO_GUARDRAILS=1` (set on `claire-gui.service`)
   actually loads anything from `experiments/nemo_guardrails_claire/`.
4. Decide the fate of `veritas/veritas_trader_engine.py` and its Kraken/Coinbase
   integrations — substantial, tested-looking code with no live service running it.
