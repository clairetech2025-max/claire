# Continuity / Sentiment / ARE Current State

Date: 2026-07-15 UTC

Mode: project-manager check-in only. No further implementation after this report.

## 1. Current Continuity / Sentiment / Session Capsule Files

| File | Purpose | Complete | Runs | Tested | Committed | Pushed |
|---|---|---:|---:|---:|---:|---:|
| `/home/LuciusPrime/claire/claire_sentiment_continuity.py` | Uploaded source file from Steve. Standalone prototype defining `SentimentState`, `CollaborationProfile`, `SessionCapsule`, `SentimentMonitor`, bootstrap rendering, capsule save, and auto-checkpoint behavior. | PARTIAL as standalone prototype | Likely yes as standalone script, but not executed in this check-in | Not directly tested | NO | NO |
| `/home/LuciusPrime/claire/session_continuity.py` | Existing CLAIRE continuity module. I merged the useful uploaded concepts into this live module: `SessionCapsule`, `CollaborationProfile`, `SentimentState`, `SentimentMonitor`, `render_session_capsule_bootstrap()`, `save_session_capsule()`, and `auto_checkpoint_session_capsule()`. | PARTIAL but usable | YES: `py_compile` passes | YES: `test_session_continuity.py` passes | NO | NO |
| `/home/LuciusPrime/claire/test_session_continuity.py` | Focused tests for session recovery, cross-session continuity, bootstrap rendering, drift detection, and auto-checkpoint file creation. | YES for current slice | YES | YES: `10 passed` | NO | NO |
| `/home/LuciusPrime/claire/CLAIRE_CONTINUITY_SENTIMENT_BOOTSTRAP.md` | Portable Markdown bootstrap intended to give to another AI. It explains the continuity contract, sentiment/drift rules, restore-point behavior, and first-response behavior. | YES as a first usable bootstrap | N/A, static document | Indirectly covered by tests for the renderer, not by file-content snapshot test | NO in `claire` repo | YES in separate private repo `Claire-Systems/sentiment` |
| `/home/LuciusPrime/claire/data/uploads/CLAIRE_CONTINUITY_SENTIMENT_BOOTSTRAP.md` | Copy of the bootstrap placed in app uploads/data area for easier VM access. | YES as a copied artifact | N/A | NO | NO | NO |
| `/tmp/sentiment_repo/README.md` | Minimal README for standalone GitHub repo. | YES | N/A | NO | YES in `Claire-Systems/sentiment` | YES |
| `/tmp/sentiment_repo/CLAIRE_CONTINUITY_SENTIMENT_BOOTSTRAP.md` | Standalone repo copy of the portable bootstrap. | YES | N/A | NO | YES in `Claire-Systems/sentiment` | YES |
| `/home/LuciusPrime/claire/data/claire_are/manifest.json` and `/home/LuciusPrime/claire/data/claire_are/segments/segment_000000.jsonl` | Canonical local `claire_are` Truth Spine data. The bootstrap and uploaded source were admitted as architecture-lane ARE records. | YES as current local ARE data | YES through `AREStore.verify()` | YES: verify returned valid | Not tracked in Git status, likely ignored runtime data | NO |

Focused test command and result:

```text
venv/bin/python -m pytest -q test_session_continuity.py
..........                                                               [100%]
10 passed in 0.05s
```

Compile command:

```text
venv/bin/python -m py_compile session_continuity.py test_session_continuity.py
```

Result: passed with no output.

Separate GitHub repo already created:

```text
Repository: Claire-Systems/sentiment
Visibility: PRIVATE
URL: https://github.com/Claire-Systems/sentiment
Commit: 713cd378866f512e4e48cee9c4243301fab35980
Files: README.md, CLAIRE_CONTINUITY_SENTIMENT_BOOTSTRAP.md
```

## 2. Route / Runtime State

### `claire_gui.py`

Current state:

- `claire_gui.py` is modified, but the diff I inspected is mobile UI work, not the `/sentiment` routes.
- I have not added `/sentiment`, `/sentiment/raw`, `/sentiment/are`, or `/continuity` to `claire_gui.py`.
- The previous turn was interrupted while I was preparing to add those routes.
- No route code for this sentiment page has been applied.

Route grep result:

```text
No @app route found for /sentiment, /sentiment/raw, /sentiment/are, or /continuity in claire_gui.py.
```

### nginx

Current state:

- I inspected `sudo nginx -T`.
- I did not edit nginx.
- nginx currently has no `/sentiment` location.
- `https://clairesystems.ai/sentiment` returned `404 Not Found`.
- The main domain only proxies specific paths to `127.0.0.1:8000`, then ends with `location / { return 404; }`.

Observed public route state:

```text
https://clairesystems.ai/sentiment -> 404 Not Found
```

No `/continuity` route exists.

Unfinished/interrupted work:

- The plan was to add a simple app route and a matching nginx `location = /sentiment`.
- That work was not started in code.
- Nothing was deployed for `/sentiment`.

## 3. Current Product Design

Plain-English product:

This is a portable continuity and drift-control layer for working with many AIs. The goal is not to preserve an AI. The goal is to preserve the accumulated intelligence created by long-term human-AI collaboration: what we know, why we believe it, how we work together, and what we learned together.

The user gives another AI a short URL or Markdown bootstrap. The receiving AI reads it before work begins and uses it as the session contract: how to preserve state, how to communicate, what not to repeat, when to pause, and how to create the next handoff.

Problem it solves:

- AIs lose context across sessions.
- Long sessions drift, repeat, or restart from first principles.
- Different AIs receive inconsistent project instructions.
- Ordinary chat transcripts are too long, noisy, and not structured as an operating contract.

What the user gives another AI:

- Ideally one public URL, for example `https://clairesystems.ai/sentiment`.
- Current available artifact is Markdown: `CLAIRE_CONTINUITY_SENTIMENT_BOOTSTRAP.md`.

What the receiving AI reads:

- The continuity/sentiment bootstrap.
- It tells the AI how to restore the working contract, not private hidden memory.

Information preserved:

- what the collaboration knows;
- why the collaboration believes it;
- how Steve and the AI work together;
- what the collaboration learned together;
- user identity and preferred working style;
- communication rules;
- shared vocabulary;
- restore-point behavior;
- next-safe-step discipline;
- failure/drift signals;
- what not to repeat;
- Session Capsule model and expected handoff behavior.

Information not preserved:

- hidden model state;
- actual prior AI consciousness;
- private secrets;
- full chat history unless explicitly included;
- Steve's private legal corpus;
- external accounts or credentials;
- authority to take real-world actions.

How `CollaborationProfile` fits:

- It stores the human working contract: Steve's role expectations, communication style, preferences, and shared vocabulary.
- It is not memory authority. It is a structured preference/profile object that can be rendered into a bootstrap.

How `SessionCapsule` fits:

- It is the portable state package: scope, current state, changes, failures, restore point, next safe step, do-not-repeat list, active tasks, blocked tasks, important files, deadlines, spoken handoff, collaboration profile, and sentiment state.
- It should export to Markdown and JSON.

How drift detection fits:

- `SentimentMonitor` watches for correction/reorientation signals, repetition, overload, contradiction, and topic drift.
- It returns a `SentimentState`.
- `auto_checkpoint_session_capsule()` saves a replacement capsule when drift crosses threshold.

## 4. ARE Implementations Found On This VM

This is based on actual code inspection, not README claims.

### A. Current `claire_are` package

- Repository: `/home/LuciusPrime/claire`
- Files:
  - `/home/LuciusPrime/claire/claire_are/core.py`
  - `/home/LuciusPrime/claire/claire_are/truth_spine.py`
  - `/home/LuciusPrime/claire/claire_are/config.py`
  - `/home/LuciusPrime/claire/claire_are/api.py`
  - `/home/LuciusPrime/claire/claire_are/diode_guard.py`
- Primary classes / entry points:
  - `AREStore`
  - `TruthSpine`
  - `TruthRecord`
  - FastAPI app in `claire_are/api.py`
- Storage format:
  - segmented append-first JSONL under `data/claire_are/segments/`
  - manifest at `data/claire_are/manifest.json`
  - HMAC signatures and previous-hash chain verification
- Runs:
  - Python API runs; I used `AREStore()` directly.
  - No separate `claire_are.api` uvicorn process was observed in `pgrep`.
- CLAIRE uses it:
  - Directly used by Venture and tests.
  - I used it to admit this bootstrap/source into Truth Spine.
- Veritas uses it:
  - Veritas Legal has ARE event adapters, but current live Veritas path also has its own evidence engine. It is not safe to claim all Veritas operations use this package without a separate trace.
- Librarian:
  - No. This appears to be the current canonical hardened ARE/Truth Spine package, not the Librarian sidecar.
- Public/private:
  - In current `clairetech2025-max/claire` repo, currently public per previous GitHub audit.
- Safe to integrate now:
  - YES for optional provenance admission and verification.
  - NO for making continuity depend on it as the only storage path.

### B. Legacy/live fast vault `ARE_SERVER.py`

- Repository: `/home/LuciusPrime/claire`
- File: `/home/LuciusPrime/claire/ARE_SERVER.py`
- Primary entry point:
  - FastAPI app
  - `POST /ingest`
  - `POST /query`
  - `GET /are/raw`
  - `GET /health`
- Storage format:
  - append JSONL at `CLAIRE_MEMORY_VAULT_PATH`, currently `/home/LuciusPrime/claire/data/memory_vault.jsonl`
  - in-memory token/exact indexes rebuilt from JSONL
  - per-record `_verify_hash`, but not the same segmented HMAC Truth Spine as `claire_are`
- Runs:
  - YES, observed at `127.0.0.1:8002`.
  - Health returned:
    `{"status":"online","mode":"ARE_FAST_INDEXED","vault_records":8463,"vault_path":"/home/LuciusPrime/claire/data/memory_vault.jsonl"}`
- CLAIRE uses it:
  - YES, current runtime and ingest bridge use it for fast vault recall/upload memory.
- Veritas uses it:
  - Not directly proven in this check-in.
- Librarian:
  - No. It is an older CLAIRE fast vault server.
- Public/private:
  - Part of current `claire` repo.
- Safe to integrate now:
  - NO as canonical continuity authority.
  - It is useful for fast search, but not ideal for provenance authority.

### C. SQLite runtime memory store

- Repository: `/home/LuciusPrime/claire`
- File: `/home/LuciusPrime/claire/are_memory_store.py`
- Primary classes:
  - `AREMemoryStore`
  - `MemoryEvent`
- Storage format:
  - SQLite tables: `memory_events`, `memory_entities`, `memory_links`, `session_trace`, `memory_audit_log`
- Runs:
  - YES; used by runtime tests and `ClaireRuntime`.
- CLAIRE uses it:
  - YES, for governed runtime memory and cross-session continuity recall.
- Veritas uses it:
  - Not directly proven.
- Librarian:
  - No.
- Public/private:
  - Part of current `claire` repo.
- Safe to integrate now:
  - YES for local runtime memory and trace support.
  - Not enough alone for public portable bootstrap provenance.

### D. `EnhancedGovernedAREStore`

- Repository: `/home/LuciusPrime/claire`
- File: `/home/LuciusPrime/claire/enhanced_governed_are.py`
- Primary classes:
  - `EnhancedGovernedAREStore`
  - `ARERecord`
  - `SentinelAdmissionGate`
  - `DeterministicIndex`
- Storage format:
  - segmented JSONL with manifest, previous hash, HMAC-like signing pattern
  - deterministic rebuildable index
- Runs:
  - Tests exist: `/home/LuciusPrime/claire/tests/test_enhanced_governed_are.py`
  - Not observed as live service.
- CLAIRE uses it:
  - Not proven as current live path.
- Veritas uses it:
  - Not proven.
- Librarian:
  - No.
- Public/private:
  - Part of current `claire` repo.
- Safe to integrate now:
  - NO as first choice. It overlaps with `claire_are` and should not become another duplicate path.

### E. `GovernedARE`

- Repository: `/home/LuciusPrime/claire`
- File: `/home/LuciusPrime/claire/governed_are.py`
- Primary class:
  - `GovernedARE`
- Storage format:
  - Coordinates original ARE JSONL, SQLite `AREMemoryStore`, and optional FAISS relevance index.
- Runs:
  - Likely importable, but not tested in this check-in.
- CLAIRE uses it:
  - Not proven as current live primary path.
- Veritas uses it:
  - Not proven.
- Librarian:
  - No.
- Public/private:
  - Part of current `claire` repo.
- Safe to integrate now:
  - NO for the MVP. It is a coordinator and increases coupling.

### F. Original ARE bridge and original ARE

- Repository/location:
  - `/home/LuciusPrime/claire/original_are_bridge.py`
  - `/home/LuciusPrime/original_are.pyiginal_are.py/are.py`
- Primary class / entry point:
  - Original `AREStore` in `are.py`
  - bridge helpers `append_original_are_memory()`, `read_original_are_history()`
- Storage format:
  - simple chronological JSONL: `{"ts": ..., "sha": ..., "text": ...}`
- Runs:
  - Bridge is importable; not separately tested here.
- CLAIRE uses it:
  - As legacy/original ARE compatibility.
- Veritas uses it:
  - Not proven.
- Librarian:
  - Could be original ARE lineage, but not the Librarian repo itself.
- Public/private:
  - Local path outside current repo plus bridge in current repo.
- Safe to integrate now:
  - NO as canonical; useful only for compatibility/import.

### G. ARE Librarian sidecar

- Repository:
  - `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__ARE-Librarian`
  - GitHub: `clairetech2025-max/ARE-Librarian`, private
- File:
  - `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__ARE-Librarian/src/are_sidecar.py`
- Primary entry point:
  - FastAPI app titled `Original ARE Librarian Sidecar`
  - `GET /health`, `POST /ingest`, `POST /search`, `POST /prefix`
- Storage format:
  - SQLite: `data/are_librarian.sqlite3`
  - `memory` table and `terms` lexical index
- Runs:
  - Code has a documented run path, but I did not start it.
- CLAIRE uses it:
  - No evidence it is currently used by the live CLAIRE service.
- Veritas uses it:
  - No evidence.
- Librarian:
  - YES. This appears to be the Librarian implementation.
- Public/private:
  - Private GitHub repo.
- Safe to integrate now:
  - NO. It is private, separate, and overlaps with current ARE; needs deliberate product boundary review.

### H. ARE Spectacle / Gyro ARE service

- Repositories/locations:
  - `/home/LuciusPrime/are-spectacle-v2/app/services/gyro_are.py`
  - `/home/LuciusPrime/claire/private_repo_payloads/are-spectacle-private/app/services/gyro_are.py`
  - cleanup clones of `Claire-Systems/Analog-Recall-Engine-Legacy` and `Claire-Systems-are-spectacle-private`
- Primary entry point:
  - `gyro_are.py` service code; not inspected deeply in this check-in.
- Storage format:
  - Not fully reviewed here.
- Runs:
  - ARE Spectacle service observed at `127.0.0.1:8010`, but not tested for continuity.
- CLAIRE uses it:
  - Exposed as separate ARE Spectacle route/product.
- Veritas uses it:
  - Not proven.
- Librarian:
  - No.
- Public/private:
  - Mixed public/private repo copies.
- Safe to integrate now:
  - NO for MVP. Keep separate product surface.

## 5. How ARE Should Connect To Continuity

### Option A: Continuity writes directly into one concrete ARE implementation

Benefits:

- simplest short-term code path;
- immediate Truth Spine hash if using `claire_are`;
- one call to `AREStore.ingest()`.

Drawbacks:

- tight coupling to whichever ARE implementation is chosen;
- portability suffers;
- another AI cannot use the capsule if it expects ARE runtime access;
- changing ARE later breaks continuity code.

Coupling risk: HIGH.

Portability: LOW to MEDIUM.

Privacy impact: risky if full capsules are blindly admitted; user profile and private project details can become durable.

Works with ChatGPT/Claude/Gemini/Codex: only if exported as text too.

Survives ARE change later: POOR.

### Option B: Continuity uses an ARE adapter interface

Benefits:

- separates continuity core from ARE implementation;
- can support `claire_are`, legacy vault, Librarian, or no ARE;
- easier to test with fake adapter;
- better long-term engineering boundary.

Drawbacks:

- more code than needed for first MVP;
- still requires choosing what data is admitted;
- can become architecture-heavy if overbuilt.

Coupling risk: MEDIUM to LOW.

Portability: HIGH.

Privacy impact: controllable if adapter only admits redacted selected fields/hashes.

Works with ChatGPT/Claude/Gemini/Codex: YES because export remains Markdown/JSON.

Survives ARE change later: GOOD.

### Option C: Continuity stores canonical local JSON/Markdown capsules; ARE separately admits hashes, provenance, and selected records

Benefits:

- strongest immediate product fit;
- Markdown/JSON remains portable and AI-readable;
- ARE provides provenance, not hard dependency;
- privacy is easier to control;
- works even when no ARE service is running;
- lets public URL remain simple while `/sentiment/are` can show proof.

Drawbacks:

- two layers to explain: capsule artifact and ARE proof;
- verification must check both file hash and ARE truth hash;
- requires a small manifest/provenance file.

Coupling risk: LOW.

Portability: VERY HIGH.

Privacy impact: best of the options if only selected summary/hash metadata goes to ARE.

Works with ChatGPT/Claude/Gemini/Codex: YES. The AI reads Markdown; ARE proof is optional.

Survives ARE change later: STRONG. Capsules remain valid artifacts.

### Option D: Public URL only, no ARE initially

Benefits:

- fastest;
- easiest for Steve to use immediately;
- no coupling.

Drawbacks:

- no canonical provenance proof;
- weaker tamper story;
- does not use CLAIRE's strongest differentiator.

Coupling risk: NONE.

Portability: VERY HIGH.

Privacy impact: depends entirely on the public content.

Works with ChatGPT/Claude/Gemini/Codex: YES.

Survives ARE change later: YES.

### Recommendation

Recommended design: Option C.

Continuity should treat Markdown and JSON capsules as the canonical portable artifact. ARE should admit selected metadata, hashes, version chain, provenance, and optionally a redacted capsule summary. The receiving AI should not need ARE to use the bootstrap. ARE is the proof layer, not the runtime dependency.

Why:

- Steve wants "give any AI a URL and say ingest this."
- Outside AIs can read Markdown, not run CLAIRE ARE.
- CLAIRE still gets authority: Truth Spine hash, timestamp, version chain, tamper evidence.
- If `claire_are`, Librarian, or ARE Spectacle changes later, the capsule format still survives.

## 6. CLAIRE Components That Could Strengthen The Product

| Component | Classification | Why |
|---|---|---|
| ARE | MVP OPTIONAL | Valuable as optional provenance/admission layer. Not required for another AI to consume the bootstrap. |
| Truth Spine | MVP OPTIONAL | Valuable for tamper evidence and canonical version chain. Should back proofs, not block use. |
| TrailLink | UNKNOWN UNTIL CODE REVIEW | Could help lineage, but I have not reviewed live code enough to justify MVP integration. |
| Sentinel | PHASE 2 | Useful for policy validation of what a capsule may include, but not required to ship first useful version. |
| DiodeGuard | MVP REQUIRED | Redaction/safety gate is needed before exporting or admitting capsules. Existing `DiodeProtocol.redact()` already used in continuity paths. |
| Gyro | DO NOT INTEGRATE YET | No immediate continuity problem requires Gyro. |
| ARV | UNKNOWN UNTIL CODE REVIEW | Not enough current-code evidence from this check-in. |
| contradiction detection | PHASE 2 | Useful to detect conflicting restore points or project state, but not MVP. |
| Session Capsule Protocol | MVP REQUIRED | This is the actual product form: structured handoff state. |
| Librarian | DO NOT INTEGRATE YET | Private sidecar, separate storage, not currently live path. Needs product boundary decision first. |
| evidence register | PHASE 2 | Useful for multi-capsule audit and public/private artifact registry. Not first MVP. |
| drift detection | MVP REQUIRED | Core reason for product: control session drift. |
| provenance hashing | MVP REQUIRED | Hash capsules locally even without ARE. |
| privacy redaction | MVP REQUIRED | Must prevent secrets/private corpus from leaking into portable bootstraps. |
| version chaining | MVP OPTIONAL | Valuable soon, but can be simple hash-of-previous in MVP; full chain UI can wait. |

## 7. Smallest Valuable Architecture

MVP must be useful immediately and must not become a year-long architecture project.

### MVP Features

1. Create/edit a `CollaborationProfile`.
2. Create a `SessionCapsule`.
3. Preserve:
   - scope;
   - current state;
   - restore point;
   - next safe step;
   - important insights;
   - failures;
   - do-not-repeat list;
   - active and blocked tasks.
4. Export:
   - Markdown bootstrap;
   - JSON capsule.
5. Redact private/secret-like information before export.
6. Hash each capsule.
7. Verify capsule hash.
8. Optionally admit a redacted summary and hash metadata to `claire_are`.
9. Generate compact handoff text for ChatGPT, Claude, Gemini, Codex, or any other AI.
10. Publish a simple public `/sentiment` page and `/sentiment/raw` Markdown endpoint.

### Features To Postpone

- full UI editor;
- auth accounts;
- multi-user workspace;
- live ARE dependency for outside AIs;
- Librarian integration;
- TrailLink/Gyro/ARV;
- vector search;
- contradiction UI;
- browser extension;
- desktop executable;
- mobile app;
- enterprise admin features;
- full public/private artifact marketplace.

## 8. Why This Is Better Than Alternatives

### Exporting a chat transcript

Transcript export is noisy, long, and hard for another AI to operationalize. A capsule is compact, structured, and tells the next AI what to do.

### Writing a long system prompt

A long system prompt is static. A capsule has restore point, failure history, next safe step, versioning, hash, and optional ARE provenance.

### Ordinary AI memory

Ordinary AI memory is vendor-specific, opaque, incomplete, and not portable across ChatGPT, Claude, Gemini, Codex, and local models. The capsule is portable.

### Vector database

A vector database helps retrieval, but it does not define authority, handoff, style, failure history, or drift rules. It is a search layer, not a continuity contract.

### Project summary document

A summary document describes the project. A Session Capsule instructs the next AI how to resume work, what to avoid, how to detect drift, and how to produce the next handoff.

## 9. Recommended Authoritative Repository

Candidates:

- `Claire-Systems/sentiment`
- `clairetech2025-max/session_capsule_protocol`
- `clairetech2025-max/bootstrap_session_capsule_protocol`
- new private `Claire-Systems/claire-continuity`
- current `claire` monorepo

Recommendation:

Use `Claire-Systems/sentiment` as the authoritative product repository for the portable bootstrap/capsule product.

Reasons:

- It already exists.
- It is already private.
- It has the bootstrap committed and pushed.
- The name matches Steve's product intuition: sentiment as the transferable working bond/drift-control layer.
- It can remain small and usable immediately.

Keep `session_capsule_protocol` and `bootstrap_session_capsule_protocol` as prior/protocol references until reviewed. Do not merge automatically.

Keep `claire` as the implementation incubator for now, but do not make `claire` the product repo for the standalone continuity tool.

Do not create another repo yet unless `sentiment` proves too narrow.

## Final Summary

### Current Implementation Status

PARTIAL but promising.

Working:

- portable Markdown bootstrap exists;
- standalone private GitHub repo exists and is pushed;
- `session_continuity.py` has merged capsule/sentiment classes;
- focused tests pass;
- bootstrap/source were admitted into local `claire_are` Truth Spine;
- uploaded file is preserved.

Not working yet:

- no public `/sentiment` URL;
- no `/sentiment/raw`;
- no `/sentiment/are`;
- no `/continuity`;
- no nginx route;
- no capsule JSON/hash manifest endpoint;
- no public sanitized page;
- no committed/pushed implementation inside the main `claire` repo.

### Best ARE Integration Design

Option C: canonical Markdown/JSON capsules, with ARE separately admitting hashes, provenance, version chain, and selected redacted records.

### Exact MVP

Build a small `sentiment` product that:

- creates/loads a `CollaborationProfile`;
- creates/loads a `SessionCapsule`;
- exports Markdown and JSON;
- redacts sensitive text;
- hashes and verifies capsule files;
- optionally admits capsule hash/provenance to `claire_are`;
- serves:
  - `/sentiment` human page;
  - `/sentiment/raw` raw Markdown;
  - `/sentiment/are` provenance JSON.

### Recommended Next Single Action

Add the public `/sentiment`, `/sentiment/raw`, and `/sentiment/are` routes in the smallest possible way, using the existing `claire_gui.py` public-page helper and `claire_are` for optional provenance proof. Then add the matching nginx location for `/sentiment` only after the local app route works.

### Files I Intend To Change After Approval

1. `/home/LuciusPrime/claire/claire_gui.py`
2. `/home/LuciusPrime/claire/session_continuity.py` only if a small helper is missing
3. `/home/LuciusPrime/claire/test_session_continuity.py` or a new focused route test
4. `/home/LuciusPrime/claire/CLAIRE_CONTINUITY_SENTIMENT_BOOTSTRAP.md`
5. `/etc/nginx/sites-enabled/claire` only after local route verification and with a backup first
