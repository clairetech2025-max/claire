# CLAIRE Current Architecture Gap Report

Date: 2026-07-10
Workspace: `/home/LuciusPrime/claire`

## Purpose

This report pauses implementation work and inventories the current CLAIRE architecture before further migration, refactor, Hugging Face deployment, or plug-in packaging work. It treats latest explicit owner direction as higher authority than older demos or historical code.

## Executive Finding

CLAIRE is not broken because the core ideas failed. It is unstable because multiple generations of the system still coexist:

- original ARE as chronological memory authority
- live `claire_gui.py` runtime
- newer `claire_runtime.py` governed runtime
- Phase One `claire_runtime_router.py`
- `claire_are/` plug-in package
- Go fallback/provider service
- Hugging Face packaging branches
- older demos and hardcoded answer paths

The immediate engineering risk is building a polished system from a stale layer. The next implementation work should consolidate authority, not add another competing runtime.

## Components That Already Exist

### ARE / Memory

- `ORIGINAL_ARE_AUTHORITY.md` defines original ARE as the memory authority.
- `ORIGINAL_ARE_CODE.md` preserves the original append-first JSONL format.
- `original_are_bridge.py` bridges the original ARE record style into current runtime.
- `ARE_SERVER.py` is an older FastAPI ARE query/ingest service over JSONL memory.
- `are_memory_store.py` provides a SQLite-style governed test/runtime memory store.
- `claire_are/` already exists as a plug-in-ready package boundary:
  - `core.py`
  - `truth_spine.py`
  - `diode_guard.py`
  - `gateway.py`
  - `schemas.py`
  - `api.py`
  - `sdk.py`
  - `config.py`
  - `hf_demo_app.py`
  - `tests/test_plugin_are.py`

### Truth Spine / Provenance

- `claire_are/truth_spine.py` implements segmented append-first JSONL records with HMAC signatures and chain verification.
- `trace_logger.py` persists redacted runtime traces to JSONL and SQLite.
- `diode_protocol.py` redacts secret-like content and checks trace safety.

### Diode / Guarding

- `diode_protocol.py` is a general redaction and trace-safety utility.
- `claire_are/diode_guard.py` implements lane-scoped read/write policy for the plug-in package.
- `write_barrier.py` exists as a Phase One writeback gate.

### C3RP / Routing

- `claire_runtime_router.py` implements a Phase One route path:
  `normalization -> provisional_orientation -> lane_classification -> memory_eligibility -> generation_permission -> provider -> output_validation -> writeback_policy`.
- `memory_eligibility.py` defines OFF/SUPPORT/STRICT/REQUIRED/QUARANTINED-style memory eligibility.
- `intent_classifier.py`, `lane_classifier.py`, `lane_router.py`, and `relevance_gate.py` contain overlapping routing and relevance logic.

### GYRO

- `claire/runtime/gyro.py` implements `GyroOrientationLayer`, producing a pre-generation `GyroBearing` with intent, lane, authority, risk, memory eligibility, source provenance, continuity, output boundary, stability, confidence, and reasons.
- Older docs and code also describe Gyro as a prompt visor, sparse orientation field, or future dynamic state system.

### Q-Insight

- Docs reference provisional Q Insight and Q/Gyro orientation.
- No canonical `q_insight.py` state object was found.
- Current code appears to approximate Q-Insight through `provisional_orientation()` in `claire_runtime_router.py` and through `GyroOrientationLayer`, but this may be outdated because the owner says GYRO and Q-Insight meanings changed.

### Runtime / API

- `claire_gui.py` is the primary large FastAPI app and contains the main GUI, `/ask`, `/reply`, `/reply-stream`, trace routes, upload routes, demo routes, and provider calls.
- `claire_runtime.py` implements a newer governed runtime with ARE, C3RP, authority capsules, Gyro, Sentinel-like checks, Diode redaction, trace logging, and demo-mode support.
- `main.go` implements a Go HTTP fallback/provider service with `/ask`, `/chat`, and `/health`.
- `main.py`, `server.py`, `claire_core_v1.py`, and other files are prototypes or historical runtime surfaces.

### Streaming

- `claire_gui.py` currently defines:
  - `GET /reply`
  - `POST /reply`
  - `GET /reply-stream`
  - `POST /reply-stream`
- The browser client selects `POST /reply-stream` for long prompts and `GET /reply?stream=true&q=...` for shorter prompts.
- Therefore, a reported `Stream failed: HTTP 404` is likely caused by deployment mismatch, stale branch, wrong app, wrong route prefix, or an older deployed build, not by absence of the route in current local `claire_gui.py`.

### Hugging Face

- `hf_space/` is a Docker Space packaging path for the full CLAIRE demo.
- `hf_space/Dockerfile` clones a fixed GitHub branch at build time:
  `CLAIRE_GIT_REF=codex/huggingface-portable-demo`.
- `hf_space/start_hf_space.sh` starts optional llama-server, starts the Go provider, then runs `uvicorn claire_gui:app`.
- `hf_claire_runtime_full/docs/FULL_CLAIRE_HF_MIGRATION_PLAN.md` says the full runtime should be a Docker Space, not a Gradio-only demo.
- `claire_are/hf_demo_app.py` is a smaller Gradio demo for the ARE plug-in package.

## Missing Components

1. Canonical architecture authority file
   - There is no single current document that supersedes old Phase Zero/Phase One docs and defines the current meaning of GYRO and Q-Insight.

2. Canonical Q-Insight implementation
   - No dedicated state object/lifecycle module was found.
   - Need definitions for creation, update, stabilization, contradiction, drift, replay, and trace shape.

3. Canonical GYRO definition
   - Current code implements Gyro as a pre-generation bearing.
   - Older docs describe future sparse coordinate fields and motion.
   - Owner says meaning has changed, so current code may be partial or stale.

4. Single runtime authority
   - `claire_gui.py`, `claire_runtime.py`, `claire_runtime_router.py`, `ARE_SERVER.py`, and `claire_are/` all own pieces of the path.
   - The system needs one authoritative runtime call graph.

5. Deployment branch alignment
   - The HF Dockerfile clones a branch from GitHub instead of using local workspace contents.
   - Local repairs will not affect HF unless pushed to the expected branch or the Dockerfile is changed.

6. Provider boundary clarity
   - GO is currently overloaded as source label, Go service, fallback provider, and route concept.
   - Need a stable provider contract.

7. Full route regression for long prompts
   - The Deep Research prompt that triggered `Stream failed: HTTP 404` should become a regression test against `/reply-stream`.

8. Product split
   - Need explicit decision between:
     - public ARE plug-in demo first
     - full CLAIRE runtime HF deployment first
     - both, with separate artifacts

## Components That Exist But Appear Outdated Or Risky

- `main.go` contains hardcoded fallback/canned answers. If GO remains, it should be a provider/execution layer, not an answer authority.
- `claire_gui.py` still contains many historical direct-answer handlers and large protected GUI/runtime mixing.
- `ARE_SERVER.py` is likely legacy relative to `claire_are/`.
- `are_hf_demo/` is an older session-scoped ARE demo, separate from `claire_are/hf_demo_app.py`.
- `claire_core_v1.py` is a useful prototype but not the current live runtime.
- `hf_space/Dockerfile` may deploy a stale branch independent of local repairs.
- `pyproject.toml` is package-scoped to `claire-are`; it may not represent the full CLAIRE runtime dependency surface.

## Canonical ARE Recommendation

Canonical ARE should be split into two layers:

1. Original memory authority principle
   - Source: `ORIGINAL_ARE_AUTHORITY.md`
   - Contract: append-first chronological memory, `{ts, sha, text}`, model does not own the past.

2. Reusable service/package implementation
   - Source: `claire_are/`
   - Contract: API/SDK-ready wrapper preserving original ARE principles while adding Truth Spine, HMAC verification, lane governance, audit, and consult-before-LLM gate.

`ARE_SERVER.py` should be treated as legacy unless a specific behavior exists there that `claire_are/` lacks.

## What GYRO Currently Means

Based on current code, GYRO currently means:

> A pre-generation orientation layer that computes a traceable bearing from intent, lane, authority, risk, memory eligibility, source provenance, continuity, and output boundary before answer generation.

Evidence: `claire/runtime/gyro.py`.

Based on older docs, GYRO previously also meant:

- prompt visor / stabilized recall prefix
- future sparse 360 x 360 coordinate field
- drift, contradiction pressure, stabilization, motion, quarantine

Because the owner says GYRO meaning changed, the current code definition should be considered provisional until Steve redefines it.

## What Q-Insight Currently Means

Based on current repo evidence, Q-Insight is not yet a canonical implemented subsystem. It appears as:

- a documented provisional orientation stage
- UI/demo language
- possibly approximated by `provisional_orientation()` and `GyroOrientationLayer`

Current working definition for implementation should not be assumed. Steve needs to define whether Q-Insight is:

- a state object
- a measurement layer
- a cognition/orientation step
- a trace artifact
- a memory admission gate
- a user-visible explanation surface

## Architecture Assumptions That Are Unclear

1. Should `claire_runtime.py` replace `claire_gui.py` orchestration, or should `claire_gui.py` remain the primary runtime with hooks into `claire_runtime.py`?
2. Is `claire_are/` the canonical public ARE package?
3. Should `ARE_SERVER.py` be deprecated?
4. Should GO be kept as a Go service, renamed, or reduced to provider adapter only?
5. Should new provider calls use `httpx` as standard?
6. Should Hugging Face first deploy the full runtime or the smaller ARE plug-in demo?
7. What is the current authoritative definition of GYRO?
8. What is the current authoritative definition of Q-Insight?
9. Should the Venture Discovery Engine prompt become a regression/evaluation benchmark for Claire?
10. Which GitHub branch is the deployment source of truth?

## Questions Steve Must Answer Before Major Implementation Continues

1. Is `claire_are/` approved as the canonical reusable ARE package?
2. Should full CLAIRE consume `claire_are/`, or should `claire_are/` remain separate from full runtime memory?
3. What is the current one-sentence definition of GYRO?
4. What is the current one-sentence definition of Q-Insight?
5. Should GO remain a Go service?
6. If GO remains, is it only an execution/provider layer with no canned answer authority?
7. Should `httpx` become the standard for new outbound provider/API calls?
8. Which deployment target comes first: ARE plug-in HF demo or full CLAIRE runtime HF Docker Space?
9. Which branch should Hugging Face clone/deploy?
10. Is deletion of obsolete prototypes allowed after preservation, or should they be archived/ignored instead?

## Immediate Engineering Direction

Recommended next steps:

1. Fix test discovery and route tests without touching product architecture.
2. Add regression test for `POST /reply-stream` using a long prompt.
3. Verify local `claire_gui:app` exposes `/reply-stream`.
4. Compare local route table with deployed/HF branch.
5. Make `claire_are/` pass its focused tests and fill only obvious API/schema gaps.
6. Defer deeper GYRO/Q-Insight implementation until Steve supplies updated definitions.

## Current Blockers

- Current GYRO and Q-Insight definitions are owner-level architecture decisions.
- Hugging Face deployment source branch may not match local code.
- Obsolete-code deletion requires care because some files may be historical authority or deployment inputs.

