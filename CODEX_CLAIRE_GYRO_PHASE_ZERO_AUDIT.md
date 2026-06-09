# CODEX CLAIRE GYRO PHASE ZERO AUDIT

Date: 2026-06-08
Branch observed: `codex/claire-backend-repair`
Mode: inspection only

## Scope And Control Rules

This audit treats the supplied Gyro ARE / Q Insight white paper as the canonical architecture map and the repository as the current implementation terrain. No application code was edited. No package install, delete, branch switch, commit, push, cleanup, or refactor was performed.

The visible GUI is protected ground. Future backend work may require a minimal hook inside `claire_gui.py`, but no layout, HTML, CSS, JavaScript, images, labels, controls, page structure, visible copy, or frontend behavior should be changed without separate explicit approval.

## Canonical White-Paper Rule

No recalled memory may influence generation before:

1. input normalization
2. lineage attachment
3. provisional orientation
4. lane classification
5. authority evaluation
6. memory eligibility decision

Target execution path:

`signal/input -> normalization and lineage -> Gyro provisional orientation -> C3RP lane, authority, route classification -> memory eligibility -> optional governed ARE retrieval -> FAISS/cuVS candidate search where applicable -> FARE projection -> Gyro/Q Insight stabilization or reorientation -> Sentinel inspection -> Diode/WriteBarrier enforcement -> dynamic model/tool execution -> output validation -> TrailLink/Trace/Ledger -> approved writeback only`

## Repository Architecture Map

### Application Entrypoints

- `claire_gui.py`: primary live FastAPI application, GUI shell, API routes, chat orchestration, memory access, provider calls, tracing, demos, upload handling, status routes, and public demo control layer.
- `main.go`: Go HTTP fallback service with `/`, `/ask`, `/chat`, and `/health`; contains many hardcoded answer branches.
- `main.py`: small FastAPI/HTML prototype with `/`, `/ask`, and `/status`.
- `server.py`: small FastAPI action dashboard prototype.
- `claire_core_v1.py`: prototype FastAPI governed-memory core with ARE-like store, Sentinel, Gyro-lite, Diode ledger, `/process`, `/prefix`, and websocket routes.
- `ARE_SERVER.py`: current ARE query/ingest FastAPI service against `data/memory_vault.jsonl`.
- `claire_ingest_bridge.py`: parser/Sentinel ingest bridge, writes Sentinel spine JSONL and forwards chunks into ARE.
- `claire_scholar.py`, `claire_courtlistener.py`: external research/provider lanes.
- `apex/*.py`, `sentinel_core/*.py`, `gumroad_builds/ARE-Spectacle/run_spectacle.py`: prototypes or packaged/demo services.

### GUI Entrypoint

- `claire_gui.py` mounts `/static` and serves the main protected GUI from `@app.get("/")`.
- Static assets: `static/logo.png`, `static/claire_waveform.jpg`.
- Additional older visible templates/prototypes: `templates/index.html`, `claire_gui.html`, `main.py`, `server.py`, `claire_gui_WORKING.py`, `claire_gui.py.save`, `recovered_claire_gui.py`.

### API Entrypoints In `claire_gui.py`

- Chat/API: `/reply`, `/reply-stream`, `POST /reply`, `GET /ask`, `POST /ask`, `POST /claire/query`.
- Trace/report: `/trace/{trace_id}`, `/report/{trace_id}`, `/machine/trace/{trace_id}`.
- Upload/document: `/upload`, `/upload-folder`.
- Research/status: `/scholar`, `/courtlistener/open`, `/drive/status`, `/drive/research`, `/diagnostic`, `/status`, `/health`.
- Business ops: `/office/ad-draft`, `/office/tasks`, `/office/task/{task_id}`.
- TTS: `/tts`.

### Generation Providers

- GO route label/source in `claire_gui.py`: `source = "GO"` in `build_reply()`.
- GO backend URL in Python: `LLM_URL = "http://127.0.0.1:8080"`; `query_llm()` posts prompts to it.
- Go implementation evidence: `main.go` exposes `/ask`, `/chat`, `/health` and returns hardcoded fallback answers; diagnostic UI calls it `Go Fallback Voice` and service `claire-go`.
- Gemini bridge: `query_gemini()` calls Google Gemini when `GEMINI_API_KEY` exists.
- Scholar and CourtListener: source lanes with direct HTTP calls.
- Python HTTP client reality: most live `claire_gui.py` provider calls use `requests`; some APEX prototypes use `httpx`. White paper target says HTTPX should be thin Python-side integration where required.

Conclusion on `GO`: in this repo `GO` means several things depending on context:

- a route/source label in `claire_gui.py`
- the `claire-go` service in diagnostics
- the Go programming language in `main.go`, `hello.go`, and shell scripts
- the model/provider fallback endpoint at `LLM_URL`

It is not proven to be a model name. It is a backend route label and service label tied to a Go HTTP fallback.

### Memory Stores

- `data/memory_vault.jsonl`: ARE/document memory vault used by `ARE_SERVER.py`, upload search, and ingest bridge.
- `data/session_memory.jsonl`: session turns and upload records.
- `data/durable_memory.jsonl`: durable preferences/facts/document context.
- `data/conversation_tmf.jsonl`: TMF snapshots.
- `data/traces.jsonl`: conversation, demo, and routing traces.
- `data/feedback.jsonl`, `data/office_tasks.jsonl`, `data/crypto_paper_trades.jsonl`.
- `data/public_demo.sqlite`: public demo machine trace/control store; sensitive runtime database, excluded from WIP snapshot.
- `silo_data/sentinel_spine.jsonl`: ingest bridge Sentinel spine.

### Vector Indexes / Retrieval

- `ARE_SERVER.py`: deterministic lexical/token index over JSONL records, exact/token scoring, hash verification.
- `claire_core_v1.py`: sentence-transformer embedding path with deterministic fallback vectors, in-memory vector index, prefix output.
- `lane_router.py`: extracts candidates and infers lanes from metadata/text.
- `relevance_gate.py`: computes lane, semantic, entity, question-type, and support-role scores.
- No canonical FAISS/cuVS runtime contract was found on the clean branch. FAISS/cuVS appear as planned or prototype concepts, not a live governed backend.

### Document Ingestion

- `claire_gui.py`: upload endpoints save files under `data/uploads`, extract text, chunk, and POST chunks to `INGEST_BASE_URL`.
- `claire_ingest_bridge.py`: normalizes pushed records, appends to Sentinel spine, forwards to ARE ingest.
- `Veritas_parser.py`: parser file exists, but writes to `~/claire/data/palantir_mem.jsonl`; the old Palantir name is still embedded in its storage path. Canonical name should be Veritas Parser.

### Tests

- `test_memory_routing.py`: major routing/regression suite. It currently verifies some correct lane gating behavior but also asserts canned architecture, identity, governance, and memory-handling replies as authoritative. Phase One must update these tests toward dynamic generation under governed context rather than hardcoded final answers.

### Trace And Persistence

- `persist_routing_trace()`: appends memory-routing records to `TRACE_LOG`.
- `persist_conversation_trace()`: appends conversation traces, but calls `relevant_recent_context()` and document search depending on source after answer construction.
- Demo trace functions append structured demo payloads to JSONL and public demo SQLite.
- `finalize_reply()` writes trace, session memory, possible durable memory, and TMF backloop after output cleanup.

### Configuration

- Constants in `claire_gui.py`: `ARE_URL`, `LLM_URL`, `INGEST_BASE_URL`, `ARE_SPECTACLE_URL`, `GEMINI_MODEL`, and data paths.
- Environment variables: Gemini, Google Drive, public demo, creator mode, timezone, memory document path.
- `go.mod` exists, supporting Go control-plane direction.
- No package installation was performed. Accidental `package-lock.json` remains untracked.

### Legacy Prototypes

Likely historical or prototype files include `main.py`, `server.py`, `claire_gui_WORKING.py`, `claire_gui.py.save`, `recovered_claire_gui.py`, `ARE_SERVER_LOCKED.py`, `sentinel_core/*`, `apex/*`, `sovereign_proxy.go`, `claire_core_v1.py`, `gumroad_builds/ARE-Spectacle/*`, and old shell launch scripts.

## Main GUI File Section Classification

File: `claire_gui.py`

- Lines 1-1037: imports, helper functions, session/recent context helpers, constants, and app setup. Classification: backend route/runtime orchestration/memory or retrieval/provider integration.
- Lines 1038-5881: primary protected visible GUI HTML/CSS/JavaScript template for `/`. Classification: protected visible GUI.
- Lines 5884-6025: ARE/Spectacle query helpers and routing trace. Classification: memory or retrieval / trace.
- Lines 6030-6195: live authority order, governance state, Diode state, conversation trace. Classification: runtime orchestration / trace or persistence.
- Lines 6193-6268 and following: ARE bypass/use heuristics. Classification: memory or retrieval.
- Lines 6332-7132: reflection, ARE formatting, CourtListener/legal orientation, source shaping. Classification: final-answer authority / provider integration / retrieval.
- Lines 7134-7326: ARE glasses and Gyro-stabilized prompt-prefix logic. Classification: prompt injection / memory or retrieval / experimental Gyro.
- Lines 7329-7567: durable memory read/write and memory promotion. Classification: memory or retrieval / persistence / writeback.
- Lines 7568-7600: `contextualize_prompt()`. Classification: prompt injection.
- Lines 7606-7890: document search/summary/shaping. Classification: document QA / memory or retrieval / final-answer authority.
- Lines 7912-8384: self/architecture/governance/identity/demo query detectors and canned replies. Classification: final-answer authority.
- Lines 8420-9900: demo scenario payloads/reports. Classification: demo runtime orchestration / trace / some protected visible demo output data.
- Lines 9910-11157: protected admin, crypto, diagnostics, creator, battleborn, utility logic. Classification: mixed runtime orchestration, provider integration, final-answer authority, unrelated/protected admin.
- Lines 11157-11602: writing and office task logic. Classification: generation / business ops persistence.
- Lines 11629-11648: output cleanup and persistence finalizer. Classification: output validation / trace / persistence.
- Lines 11651-12020: `build_reply()` and response orchestration. Classification: runtime orchestration / final-answer authority / generation.
- Lines 12023-12220: upload extraction/search and document ingestion. Classification: document ingestion / memory or retrieval.
- Lines 12277-12435: Gemini and GO provider invocation. Classification: provider integration / generation.
- Lines 12442-12764: public pages. Classification: protected visible GUI.
- Lines 12765-13295: GUI/API routes including `/`, `/reply`, `/ask`, `/tts`. Classification: protected visible GUI for HTML ranges, backend routes for route handlers.
- Lines 13341-13772: status/diagnostic/action routes. Classification: backend route / provider integration / runtime status.
- Lines 13774-13923: public demo SQLite control layer. Classification: runtime orchestration / trace or persistence.

## Current Chat Call Graph

Primary JSON path:

1. `POST /ask` in `claire_gui.py` reads `input`, `q`, `query`, or `prompt`.
2. If `demo_mode` is true and not a demo-key query, it calls `build_demo_payload()` and returns JSON.
3. Otherwise it calls `build_reply(q)`.
4. `build_reply()` sets `source = "GO"` and immediately calls `relevant_recent_context(q)` before lane classification.
5. It then evaluates many special-case handlers in order: greetings, casual check-in, decision help, CourtListener, writing, Spectacle demo, memory handling, partner/demo/architecture/identity/admin/legal/crypto/demo/system/provenance/horse/reflection/scholar/ingest/Drive/document/session handlers.
6. Many of those handlers return final answers through `finalize_reply()` before `classify_query()` runs.
7. Only after those handlers does `build_reply()` call `classify_query(q)` through `intent_to_dict()`.
8. If reasoning-first, it calls `governed_are_recall()`, which calls `query_are()`, `extract_candidates()`, `gate_retrieval_candidates()`, then `conceptual_answer()`.
9. Else it calls `query_are(q)` if `should_use_are(q)`.
10. It shapes accepted ARE results through `format_are_hit()` and `shape_are_reply()`, or calls `query_llm(contextualize_prompt(q))`.
11. `contextualize_prompt()` can inject recent session context, durable memory, and `gyro_stabilized_prefix()` into the prompt.
12. `gyro_stabilized_prefix()` constructs a prompt visor from `are_glasses_recall_items()` and `recent_turns()`, independent of the canonical Q Insight lifecycle.
13. `query_llm()` wraps prompt with `EXECUTIVE_SYSTEM_PROMPT` and posts to `LLM_URL`.
14. `query_gemini()` may run as a bridge when enabled.
15. Output cleanup happens in `clean_visible_reply()` and `sanitize_public_reply()` inside `finalize_reply()`.
16. `finalize_reply()` writes conversation trace, session memory, possible durable memory, and TMF backloop.

Current defect placement:

- Stale session/durable/Gyro prompt prefixes can enter prompt construction through `contextualize_prompt()`.
- Several final answer handlers bypass the model and the governed routing path.
- Output cleanup occurs after contamination, not before context admission.
- Session memory writeback can occur for model output without explicit WriteBarrier approval.

## Final-Answer Authority Inventory

Functions capable of directly returning final answers or bypassing normal model generation:

- `build_reply()`: master branching authority.
- `finalize_reply()`: returns final response after sanitation/persistence.
- `casual_checkin_reply()`, `reconstruct_prior_discussion_reply()`, `session_reasoning_reply()`.
- Partner handlers: `partner_problem_reply()`, `partner_demo_flow_reply()`, `partner_close_reply()`, `partner_difference_reply()`, `partner_speed_reply()`, `partner_meeting_intro()`.
- Demo handlers: `spectacle_demo_reply()`, `demo_activation_reply()`, `demo_session_reply()`, `demonstration_mode_reply()`, `public_demo_guide_reply()`.
- Architecture/identity handlers: `system_difference_reply()`, `governance_value_reply()`, `memory_handling_reply()`, `provenance_design_reply()`, `continuity_drift_reply()`, `architecture_simple_reply()`, `core_architecture_reply()`, `enterprise_system_reply()`, `self_demo_reply()`, `informatica_stack_brief_reply()`.
- Security/admin handlers: `restricted_admin_reply()`, `creator_reply()`, `battleborn_reply()`, `state_parks_case_reply()`, crypto handlers.
- Research handlers: `courtlistener_open_reply()`, `courtlistener_status_reply()`, `courtlistener_retrieval_reply()`, `scholar_reply()`, `shape_legal_fallback()`.
- Document handlers: `search_uploaded_documents()`, `synthesize_document_summary()`, `shape_document_reply()`, `shape_quarantined_memory_reply()`.
- ARE/retrieval handlers: `format_are_hit()`, `shape_are_reply()`, `conceptual_answer()` in `answer_planner.py`.
- General fallback handlers: `known_general_reply()`, `practical_howto_reply()`.
- `main.go`: independent Go service contains numerous hardcoded final answers for identity, memory, architecture, governance, Gyro, business, and general fallback prompts.

High-risk categories:

- Canned architecture/identity/ARE/RAG/pipeline/benchmark-style answers.
- Direct use of retrieved fragments in `format_are_hit()`/`shape_are_reply()`/document shaping.
- Missing-memory refusal language that can incorrectly outrank general reasoning.

## Prompt-Injection Inventory

Functions capable of adding text to prompts/context:

- `EXECUTIVE_SYSTEM_PROMPT`: base system prompt in `claire_gui.py`.
- `query_llm()`: combines system prompt and user prompt for GO backend.
- `query_gemini()`: provider-specific system instruction.
- `contextualize_prompt()`: injects durable memory, recent conversation context, Gyro visor, and current question.
- `gyro_stabilized_prefix()`, `GyroAnalogRecallEngine.stabilize_vision()`: creates `[GYRO-STABILIZED-RECALL]` prompt block.
- `are_glasses_prefix()`, `AREVirtualGlasses.apply_to_prompt()`: creates memory visor/prefix blocks.
- `shape_document_reply()` and `synthesize_document_summary()`: transform document excerpts into final answer text.
- `courtlistener_retrieval_reply()`, `scholar_reply()`: format source-lane context.
- `main.go`: embeds system behavior as hardcoded textual answers, not prompt injection but final-answer substitution.

## Recall Inventory

Recall/search functions and current preconditions:

- `build_reply()` calls `relevant_recent_context(q)` before classification and memory eligibility. Violation.
- `persist_conversation_trace()` calls `relevant_recent_context()` and sometimes `search_uploaded_documents()` after output; not generation influence directly, but still trace-side retrieval without an explicit Q Insight object.
- `contextualize_prompt()` calls `relevant_recent_context()`, `relevant_durable_memory()`, and `gyro_stabilized_prefix()` before generation; not guarded by explicit memory eligibility. Violation.
- `gyro_stabilized_prefix()` and `GyroAnalogRecallEngine.stabilize_vision()` call recent session memory and ARE glasses items without canonical Q Insight or memory mode. Violation.
- `query_are()` calls ARE `/query`; in the governed branch it happens after `classify_query()`, but `governed_are_recall()` does not receive an explicit memory eligibility decision.
- `search_uploaded_documents()` reads `data/memory_vault.jsonl`; in `build_reply()` it can run before the classifier. Violation for non-document prompts accidentally matched by broad document markers.
- `relevant_recent_context()` reads `SESSION_MEMORY`; current call in `build_reply()` happens before classification. Violation.
- `relevant_durable_memory()` reads `DURABLE_MEMORY`; enters generation through `contextualize_prompt()` without explicit memory mode.
- `claire_core_v1.py` has a better prototype sequence: process query, recall, Sentinel filter, Diode append, prefix. It is not the live chat path.
- `ARE_SERVER.py` indexes and queries memory but does not own live lane classification or memory eligibility.
- `claire_ingest_bridge.py` writes Sentinel spine and forwards to ARE; it does not decide generation eligibility.
- `claire_scholar.py` and `claire_courtlistener.py` perform external retrieval when their handlers fire; some handlers precede the canonical classifier.

## Bypass Analysis

### Recall Before Classification

- `build_reply()` line range around 11685 calls `relevant_recent_context(q)` before `classify_query()`.
- `contextualize_prompt()` can add recent/durable/Gyro memory without a canonical `memory_mode`.
- `gyro_stabilized_prefix()` constructs prompt memory before C3RP/Q Insight exists.

### Memory Before Eligibility

- No explicit memory eligibility object exists in the live chat path.
- `should_use_are()` is a heuristic and not tied to lane, authority, lineage, or Q Insight.

### Stale Session Context Enters Prompt

- `contextualize_prompt()` adds "Recent conversation context Claire should remember".
- `_recent_memory_items_for_gyro()` reads recent turns and can feed them into a Gyro visor.

### Document Content Bypasses Relevance Gating

- `search_uploaded_documents()` performs keyword scoring over all document-upload records and returns text snippets.
- `shape_document_reply()` can use those snippets directly.
- There is no canonical selected-document object or memory-mode `STRICT` enforcement in the live path.

### Retrieved Fragments Become Final Answers

- `format_are_hit()` and `shape_are_reply()` can render accepted ARE text.
- `search_uploaded_documents()` returns "Uploaded document: source\ntext" blocks used for final shaping.
- CourtListener/Scholar handlers return formatted source material directly when triggered.

### Canned Handlers Outrank Model Generation

- Architecture, identity, governance, memory-handling, provenance, demo, and some practical answers return before GO generation.
- Existing tests assert this behavior, which conflicts with the white paper's dynamic natural-language requirement.

### Output Sanitation After Contamination

- `clean_visible_reply()` and `sanitize_public_reply()` run in `finalize_reply()` after final answer selection.
- They are cleanup, not an admission gate.

### Generated Content Enters Authoritative Memory Without WriteBarrier Approval

- `finalize_reply()` calls `remember_turn()` and `maybe_promote_memory()`.
- `maybe_promote_memory()` can write durable facts/preferences based on phrases such as "remember this" or "from now on" without a formal WriteBarrier approval object.
- `conversation_backloop()` writes TMF snapshots after final output.

## Authority Analysis

Current authority owners:

- Normalization: `_clean_for_match()` and `intent_classifier.clean_text()`; duplicated and inconsistent.
- Lane classification: `intent_classifier.classify_query()`, many `is_*_query()` detectors in `claire_gui.py`, CourtListener orientation, demo detectors, Go hardcoded detectors. Conflicting authority.
- Authority classification: partial in CourtListener orientation, `_live_authority_order()`, `_live_governance_state()`, restricted admin checks. No canonical C3RP authority object.
- Memory eligibility: no canonical owner. `should_use_are()`, `should_bypass_are()`, `source_output_allowed`, and document/session heuristics compete.
- Retrieval: `query_are()`, `search_uploaded_documents()`, `relevant_recent_context()`, `relevant_durable_memory()`, Scholar, CourtListener, Drive cache, `claire_core_v1.py`. Conflicting.
- Candidate merging: `lane_router.py` and `relevance_gate.py` for ARE candidates; other lanes have bespoke formatting.
- Relevance gating: `relevance_gate.py` for ARE; document/session/Gyro prefixes have weaker or separate gates.
- Gyro orientation: `GyroAnalogRecallEngine` prompt visor in `claire_gui.py`; `claire_core_v1.Gyro` lite prototype; demo text. No canonical Q Insight lifecycle.
- Q Insight state: represented only in UI text/demo descriptions; no live state object.
- Sentinel inspection: `claire_core_v1.Sentinel`, ingest bridge "Sentinel spine", demo policy checks, `_live_governance_state()`. No single live Sentinel authority.
- Diode enforcement: `claire_core_v1.DiodeLedger`, `app/services/write_barrier.py`, `_live_diode_state()`, demo trace language. No single live WriteBarrier around writeback.
- Model selection: `build_reply()`, `query_llm()`, `query_gemini()`, source ordering in diagnostics.
- Generation: GO backend at `LLM_URL`, Gemini bridge, many canned handlers, Go hardcoded service.
- Output validation: `clean_visible_reply()`, `sanitize_public_reply()`, `is_bad_writing_output()`, some provider-specific guards. Mostly post-generation.
- Trace: `persist_routing_trace()`, `persist_conversation_trace()`, demo trace JSONL, public demo SQLite.
- Memory writeback: `remember_turn()`, `remember_durable_memory()`, `maybe_promote_memory()`, `conversation_backloop()`, ingest bridge, ARE ingest.

The core conflict is that `build_reply()` owns routing, answer selection, retrieval timing, provider choice, and final answer authority at once.

## Terminology Audit

- `ARE`: generally used as Analog Recall Engine in current code/docs. Some UI/public copy correctly says Analog Recall Engine.
- `Veritas Parser`: canonical name appears in `Veritas_parser.py` and Gumroad docs.
- `Palantir Parser`: retired name still appears in white-paper-era text and `Veritas_parser.py` storage path `palantir_mem.jsonl`; should not be introduced into new docs/code.
- `Gyro`: appears in UI, demos, `claire_core_v1.py`, `answer_planner.py`, `main.go`; implemented as prompt visor/Gyro-lite, not full dynamic runtime.
- `Q Insight`: visible UI/demo concept; no live state object found.
- `C3RP`: appears mainly in docs/spec/test context; no canonical live service in clean branch.
- `BARE`/`FARE`: appear in UI/demo copy and Go hardcoded answer; not canonical live memory layers.
- `Sentinel`: appears in prototypes, ingest bridge, demos, UI; no single live Sentinel authority.
- `Diode`/`WriteBarrier`: `claire_core_v1.DiodeLedger`, `app/services/write_barrier.py`, demos; no canonical live writeback gate around `maybe_promote_memory()`.
- `Lycanthrope`: not found as a canonical live runtime component on the clean branch; likely absent or legacy outside inspected hits.
- `Recognition Rail`: appears in UI/demo copy; no canonical implementation found.
- `TrailLink`: appears in UI/copy; trace exists, TrailLink graph not canonical.
- `Pseudo-RAM`/`Temporal Memory Fabric`: TMF snapshots exist as JSONL and concept text; full TMF/Pseudo-RAM absent.
- `Go`/`GO`: mixed as language, route label, fallback service.
- `httpx`: present in APEX prototypes and shell checks; main live `claire_gui.py` uses `requests`.

## White-Paper Gap Analysis

| Component | Current status | Evidence |
|---|---|---|
| Veritas Parser | partially implemented / conflicting | `Veritas_parser.py` exists but stores to `palantir_mem.jsonl`; ingest bridge is named parser/Sentinel, not canonical Veritas runtime. |
| C3RP | architecture/spec only or partial | `intent_classifier.py` approximates lane classification; no full command/control/cognition/routing protocol with authority/memory mode. |
| BARE | represented by legacy/demo concepts | Demo/UI text and Go hardcoded answer; no canonical bedrock authoritative memory layer. |
| ARE | implemented / partial | `ARE_SERVER.py`, `claire_core_v1.py`, JSONL vault, upload ingest, recall functions. |
| FAISS / cuVS | experimental/absent on clean branch | No canonical FAISS/cuVS service found in active files; vector prototype uses sentence-transformer/fallback. |
| FARE | architecture/spec only | Mentioned in UI/demo; no projection module. |
| Q Insight | architecture/spec only | UI concept exists; no state object/lifecycle. |
| Gyro | partially implemented as prompt visor / legacy | `GyroAnalogRecallEngine`, `claire_core_v1.Gyro`; not full dynamic sparse orientation field. |
| Sentinel | partially implemented / fragmented | `claire_core_v1.Sentinel`, ingest bridge, demos, `_live_governance_state()`. |
| Diode / WriteBarrier | partial / fragmented | `DiodeLedger`, `app/services/write_barrier.py`, demo references; not authoritative in live writeback. |
| TrailLink | architecture/spec only | Trace records exist, but event graph/TrailLink not canonical. |
| Trace | implemented / fragmented | JSONL traces and SQLite demo traces. |
| Ledger | partial | `claire_core_v1` diode ledger; public demo SQLite; no unified ledger. |
| Lycanthrope | absent or legacy concept | No canonical live overwatch component identified. |
| Recognition Rail | architecture/spec only | UI/demo copy only. |
| Temporal Memory Fabric | experimental/partial | `TMF_SNAPSHOTS` and backloop; no full SSD/NVMe working-memory system. |
| Go control plane | prototype / intended direction | `main.go` service exists; Python app still owns control plane. |
| HTTPX adapters | experimental/partial | APEX prototypes use `httpx`; live Python mostly uses `requests`. |

## GUI Protection Baseline

Hashes:

- `claire_gui.py`: `3de33536783fcd9f323bf5e9ecf95d45b6454b137aa9851b170e382ef09e2be7`
- `templates/index.html`: `6643312b1366a71dc8bd0008d740c59d6998b80e2cba6080c3fdc87d5b776908`
- `claire_gui.html`: `578ad1827a27a66089af27fbaa7463958a5165774241baf814c42d1f0b457a06`
- `static/logo.png`: `68620b1b930c4240744f61325aeeeaf408c72dde6855f4e41d29b92568335168`
- `static/claire_waveform.jpg`: `65bf3553cdf5e082c2e46f67476288fc40aee27b13e0b8c2d22baa3c4e0415ef`
- `main.py`: `70379a516ba0c5888bf0057698b099cf69a13ca50b35b95341b722916771ee51`
- `server.py`: `79777ee8c3f0fc85a101a53195bba13745bbe49e50a3441d7d522d857570930e`
- `claire_gui_WORKING.py`: `30c0b77c3800019223d9198979e0ee0b853037e62ae405f0ed231e9a9c4dae30`
- `claire_gui.py.save`: `98fabbb386d96273a3579c4e9e842bb07b982d527175da1db840885857644db6`
- `recovered_claire_gui.py`: `5bcbb4ae252d2e4c65d6290978852faf82cad850ecb694f9ce08c7133f5992f8`

Sizes and mtimes:

- `claire_gui.py`: 552727 bytes, 2026-06-07 08:54:47 +0000
- `templates/index.html`: 2677 bytes, 2026-04-14 22:55:52 +0000
- `claire_gui.html`: 3781 bytes, 2026-04-14 22:56:15 +0000
- `static/logo.png`: 331105 bytes, 2026-04-14 22:55:25 +0000
- `static/claire_waveform.jpg`: 15349 bytes, 2026-04-18 13:41:52 +0000
- `main.py`: 2563 bytes, 2026-04-15 06:29:13 +0000
- `server.py`: 4891 bytes, 2026-04-14 22:56:15 +0000
- `claire_gui_WORKING.py`: 18914 bytes, 2026-04-14 22:55:52 +0000
- `claire_gui.py.save`: 19117 bytes, 2026-04-14 22:56:15 +0000
- `recovered_claire_gui.py`: 339 bytes, 2026-04-14 22:55:52 +0000

Protected visible line ranges:

- `claire_gui.py` 1038-5881: main GUI HTML/CSS/JS.
- `claire_gui.py` 12442-12764: public page template and public pages.
- `claire_gui.py` 13174-13277: `/ask` HTML response.
- `templates/index.html` full file.
- `claire_gui.html` full file.
- `server.py` visible HTML/CSS/JS ranges 12-134.
- `main.py` visible HTML response ranges 16-51.
- Static assets listed above.

## Canonical Target Call Graph For Current Repository

Minimal authoritative call graph:

1. Endpoint receives message: `POST /ask`, `POST /reply`, `GET /reply`, or stream wrapper.
2. Create `SignalEnvelope` with trace ID, timestamp, payload hash, source, modality, lineage ID.
3. Normalize input through one module.
4. Create provisional Q Insight state.
5. C3RP classifies lane, authority, route, and memory mode.
6. Memory eligibility returns OFF/SUPPORT/STRICT/REQUIRED/QUARANTINED.
7. If memory mode permits, call governed recall only through one interface.
8. Candidate search may call ARE and future FAISS/cuVS under filters.
9. FARE projects candidates against Q Insight and budget.
10. Sentinel inspects signal/candidates/proposed output.
11. Diode/WriteBarrier blocks unauthorized writeback.
12. GO provider receives one governed context package and dynamically generates.
13. Output validation checks contamination, lane, source claims, and safety.
14. Trace appends observable control facts.
15. Writeback occurs only through explicit WriteBarrier-approved proposal.

Ownership proposal:

- New `signal_envelope.py`: normalization, lineage, payload hash.
- New or expanded `c3rp_router.py`: lane/authority/route/memory-mode classification.
- New `q_insight.py`: minimal state object/lifecycle.
- Existing `intent_classifier.py`: demote into C3RP helper or replace with C3RP.
- Existing `lane_router.py` and `relevance_gate.py`: reuse as ARE candidate helper and FARE precursor.
- New `memory_eligibility.py`: OFF/SUPPORT/STRICT/REQUIRED/QUARANTINED.
- New `governed_context.py`: constructs only admitted context package.
- Existing `query_llm()` in `claire_gui.py`: reuse GO provider call after governed context package.
- Existing `persist_routing_trace()`/`persist_conversation_trace()`: replace/wrap with TrailLink/Trace schema.
- Existing `maybe_promote_memory()`: wrap behind WriteBarrier.

Legacy handlers:

- Remove or demote canned architecture/identity/ARE/RAG/benchmark/pipeline handlers from authoritative answer control.
- Preserve deterministic hardcoded text only for errors, status, empty states, safety notices, explicit UI copy, and protocol messages.

GUI hook:

- Minimal hook in `build_reply()` to call the authoritative backend route.
- No frontend changes.

Q Insight state location:

- Start as backend module-local state keyed by trace ID.
- Later move to Go control plane per white paper.

Sparse Gyro bindings:

- Start in a new backend module with sparse active bindings keyed by trace ID and coordinate.
- Do not instantiate 129,600 objects.

Recall eligibility enforcement:

- Before any call to `query_are()`, `relevant_recent_context()`, `relevant_durable_memory()`, `search_uploaded_documents()`, or prompt-prefix helpers.

Writeback approval:

- Before `remember_turn()`, `remember_durable_memory()`, `maybe_promote_memory()`, `conversation_backloop()`, and ARE ingest of model-derived summaries.

## Full Gyro Implementation Roadmap

### Phase One: One Authoritative Execution Path

- Objective: stop contaminated context and legacy bypasses.
- Required files: `claire_gui.py` backend hook only, `intent_classifier.py` or new `c3rp_router.py`, `lane_router.py`, `relevance_gate.py`, `answer_planner.py`, `test_memory_routing.py`.
- Required interfaces: `route_message(input) -> governed response package`.
- Tests: classification-before-recall, memory eligibility-before-recall, rejected context not generated, no canned architecture authority.
- Stop/go: benchmark/pipeline/Spanish/conceptual prompts no longer pull stale memory or canned speeches.
- Dependencies: existing GO backend, ARE server optional, JSONL trace.
- GUI impact: none.
- Rollback: restore prior backend hook and routing modules.

### Phase Two: Q Insight State Object And Lifecycle

- Objective: implement inspectable orientation state.
- Files: new `q_insight.py`, trace tests, route integration.
- Interfaces: create/update/snapshot/replay Q Insight.
- Tests: provisional, stabilized, reorientation, quarantine, versioning.
- Stop/go: every request has Q Insight state before recall.
- Dependencies: Phase One route.
- GUI impact: none unless later displaying trace.
- Rollback: disable Q Insight integration and retain Phase One route.

### Phase Three: Sparse 360 x 360 Latent Coordinate Space

- Objective: represent sparse coordinate bindings.
- Files: new `gyro_coordinates.py`.
- Interfaces: bind/release/list active coordinates.
- Tests: no heavyweight allocation, deterministic coordinate assignment.
- Stop/go: active-only state storage.
- Dependencies: Q Insight.
- GUI impact: none.
- Rollback: replace coordinate with simple lane state.

### Phase Four: Binding, Release, Rebinding, Expiration, Quarantine

- Objective: manage signal coordinate lifecycle.
- Files: `gyro_coordinates.py`, `q_insight.py`, trace.
- Interfaces: transition API.
- Tests: expire, quarantine, release, rebind, idempotency.
- Stop/go: trace records lifecycle decisions.
- Dependencies: Phase Three.
- GUI impact: none.
- Rollback: keep provisional/stabilized only.

### Phase Five: Continuous Motion And Stabilization

- Objective: implement velocity, drift, contradiction pressure, transition legality.
- Files: `gyro_motion.py`, `q_insight.py`, tests.
- Interfaces: update law over event stream.
- Tests: drift detection, contradiction pressure, deterministic replay.
- Stop/go: same events/policy produce same decisions.
- Dependencies: Phase Four.
- GUI impact: none.
- Rollback: static Q Insight state.

### Phase Six: ARE, FAISS/cuVS, FARE, Sentinel, Diode Contract

- Objective: integrate retrieval/search/gating/writeback under one governed contract.
- Files: `governed_recall.py`, `fare.py`, `sentinel_policy.py`, `write_barrier.py`.
- Interfaces: governed recall, candidate projection, Sentinel action, write proposal.
- Tests: raw vector results never become context; WriteBarrier required.
- Stop/go: admitted context contains IDs/rationale only.
- Dependencies: Phase Five, ARE server.
- GUI impact: none.
- Rollback: use ARE-only governed recall.

### Phase Seven: Multiple Signal Types

- Objective: text, recalled memory, and tool output as separate signals.
- Files: signal envelope and execution broker modules.
- Interfaces: signal ingestion/event queue.
- Tests: tool output untrusted, recalled memory untrusted until admitted.
- Stop/go: each signal has lineage.
- Dependencies: Phase Six.
- GUI impact: none.
- Rollback: text-only.

### Phase Eight: Documents, OCR, Speech, APIs, Telemetry, Policy Events, Model Proposals, Other Agents

- Objective: expand modalities.
- Files: Veritas Parser adapter, Riva/speech adapter, API/tool adapters, telemetry.
- Interfaces: modality adapters to SignalEnvelope.
- Tests: partial speech delayed recall, document scoped QA, policy revocation.
- Stop/go: each modality can be admitted/quarantined.
- Dependencies: Phase Seven.
- GUI impact: none unless new controls separately approved.
- Rollback: disable adapters.

### Phase Nine: Complete Trace, Replay, Recovery, Deterministic Reconstruction

- Objective: TrailLink/Trace/Ledger event reconstruction.
- Files: trace ledger/replay modules; likely Go control-plane service later.
- Interfaces: append, snapshot, replay, recover.
- Tests: same event stream and policy produce same control decisions.
- Stop/go: replay reproduces decisions.
- Dependencies: prior phases.
- GUI impact: none unless trace viewer separately approved.
- Rollback: JSONL trace only.

### Phase Ten: Comparative Benchmark

- Objective: benchmark raw LLM, conventional RAG, governed ARE, and Gyro-oriented ARE.
- Files: benchmark harness, test corpora config, metrics reporter.
- Interfaces: scenario runner and metrics export.
- Tests: latency, provenance, unsafe tool, unauthorized write, context efficiency.
- Stop/go: Gyro improves at least one important dimension at acceptable latency cost.
- Dependencies: stable prototype.
- GUI impact: none.
- Rollback: retain benchmark harness for governed ARE only.

## Minimal Immediate Phase One Repair Proposal

Do not implement until `APPROVED TO BEGIN PHASE ONE`.

Exact files:

- `claire_gui.py`
- `intent_classifier.py` or new `c3rp_router.py`
- `lane_router.py`
- `relevance_gate.py`
- `answer_planner.py`
- `test_memory_routing.py`

Exact functions:

- `build_reply()`
- `contextualize_prompt()`
- `should_use_are()`
- `governed_are_recall()`
- `search_uploaded_documents()`
- `maybe_promote_memory()`
- `query_llm()`
- canned answer detectors/replies listed above

Legacy handlers to remove or demote from authoritative final-answer control:

- `is_memory_handling_query()` / `memory_handling_reply()`
- `is_system_difference_query()` / `system_difference_reply()`
- `is_governance_value_query()` / `governance_value_reply()`
- `is_core_architecture_query()` / `core_architecture_reply()`
- `architecture_simple_reply()`
- `is_public_identity_query()` / `EXECUTIVE_SELF_DESCRIPTION` path for normal conversation
- benchmark/pipeline/runtime/ARE/RAG demo speeches except explicit demo routes
- `known_general_reply()` as final-answer authority except narrow deterministic empty/status cases

Exact GUI backend hook:

- Replace the body of `build_reply()` with a call into a backend route function after preserving demo/admin/status hard stops.
- Or add `route_chat_message(q)` and make `build_reply()` delegate to it.
- No HTML/CSS/JS changes.

Expected behavior before:

- Benchmark/pipeline/Spanish questions can be treated as missing-memory or answered with stale architecture fragments/canned speeches.

Expected behavior after:

- Benchmark question routes to conceptual/technical dynamic GO generation with memory OFF or SUPPORT only.
- Pipeline question routes to architecture/technical dynamic GO generation with admitted context only.
- Spanish capability question routes to casual/capability dynamic GO generation with memory OFF.
- Retrieved fragments cannot be final answers.
- Rejected context is logged but never enters the generation prompt.

Rollback procedure:

- Revert only Phase One backend files to pre-repair commit.
- Verify GUI file hash for protected ranges or full file if no GUI hook was applied.
- Keep WIP snapshot branch as recoverable backup.

## GUI-FOLDER BACKEND EDIT REQUEST

File: `claire_gui.py`

Function: `build_reply()`

Line range: approximately 11681-12005

Purpose: enforce orientation/classification/memory eligibility before any recall, session context, document search, prompt prefix, or final-answer selection.

Why unavoidable: live `/ask`, `/reply`, and stream routes all call `build_reply()`. Backend routing currently lives inside the GUI file.

Visible GUI impact: none if edit is restricted to backend function body and helper calls; no HTML/CSS/JS/visible copy changes.

External-module alternative: add `claire_runtime_router.py` or `c3rp_router.py` and have `build_reply()` delegate to it.

Exact proposed change: not applied in Phase Zero. Future Phase One should insert one authoritative backend call at the top of `build_reply()` after protected demo/admin hard stops, remove pre-classification `relevant_recent_context()`, and require explicit memory eligibility before recall/prompt context.

## Required Invariants And Tests

Tests to design/modify:

- normalization occurs before classification
- classification completes before recall
- memory eligibility completes before recall
- rejected context never reaches generation
- retrieved fragments cannot become final answers directly
- canned architecture responses are not authoritative
- casual prompts do not trigger long-term memory
- conceptual prompts do not leak legal or personal memory
- document questions remain scoped to selected documents
- tool output is treated as an untrusted signal
- authority revocation blocks execution and writeback
- WriteBarrier approval is required for authoritative memory
- same event stream reproduces same control decisions
- visible GUI files remain byte-for-byte unchanged unless separately approved

## Audit Conclusion

The current defect is structural, not tonal. The live application can generate fluent answers, but authority is fragmented across special-case handlers, session memory, document search, ARE recall, prompt-prefix Gyro, provider routing, and cleanup. The white-paper target requires one pre-generation orientation and memory-eligibility authority before any recalled material can steer generation.

Phase One should not build the full Gyro. It should establish the invariant that no memory, document, session context, or prompt-prefix text reaches GO generation before a canonical route has normalized the signal, attached lineage, classified lane and authority, and decided memory eligibility.
