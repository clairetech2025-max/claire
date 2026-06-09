# CODEX CLAIRE GYRO PHASE ONE CHANGE PLAN

Status: planning only. Do not implement until `APPROVED PHASE ONE CHANGE PLAN`.

## Objective

Establish one authoritative chat execution path and stop contaminated context, stale fragments, retrieved text, and canned architecture/system responses from reaching final answers.

Phase One is not the full Gyro implementation. It creates the clean runtime foundation that later Q Insight/Gyro/C3RP/Sentinel/Diode work will control.

## Current Hashes

- `claire_gui.py`: `3de33536783fcd9f323bf5e9ecf95d45b6454b137aa9851b170e382ef09e2be7`
- `intent_classifier.py`: `94712a223b11bff097212239ed47c2acdb57c502e13678b114b8e038199a7eed`
- `lane_router.py`: `d252fb21f074848251a7c8e86145e98b5018cd5dc21d0216bdfdd578ae5df0fe`
- `relevance_gate.py`: `d1286a41254bea7cb3fad9c7c536934f2b077bc56b34b2f399404d4779e908ac`
- `answer_planner.py`: `c8f08fea70851912437aadc1bc6821ef80ceeae2cba38797d70e8105708d4354`
- `test_memory_routing.py`: `08089d5d80c9ee937072afa6d615a9a5724a0e0c68ac447c922cad8e1b845f8d`

## Exact Files Proposed

Application/backend:

- `claire_gui.py`
- `intent_classifier.py`
- `lane_router.py`
- `relevance_gate.py`
- `answer_planner.py`

Tests:

- `test_memory_routing.py`

New backend modules proposed:

- `claire_runtime_router.py`
- `memory_eligibility.py`
- `write_barrier.py`

No GUI-facing HTML, CSS, JavaScript, image, label, button, page structure, visible copy, control, styling, or frontend behavior changes are proposed.

## New Backend Modules

### `memory_eligibility.py`

Purpose: own explicit memory mode decisions for Phase One.

Interfaces:

- `MemoryMode`: OFF, SUPPORT, STRICT, REQUIRED, QUARANTINED
- `MemoryEligibility`: mode, allowed stores, allowed lanes, required evidence, reason
- `determine_memory_eligibility(normalized_input, lane_result, authority_result) -> MemoryEligibility`

Existing behavior:

- `should_use_are()`, document heuristics, session heuristics, `source_output_allowed`, and `contextualize_prompt()` independently decide whether memory participates.

Proposed behavior:

- No recall path may run unless `MemoryEligibility.mode` permits it.
- CASUAL and unrelated CONCEPTUAL prompts default to OFF.
- Architecture/benchmark/pipeline/ARE/RAG questions default to OFF or SUPPORT only; no legal/personal/session memory unless explicitly requested and lane eligible.
- DOCUMENT_QA uses STRICT and only selected/latest document store.
- PROJECT_STATE uses REQUIRED and must rely on verified local evidence or say evidence is unavailable.

Dependencies:

- Calls `intent_classifier.py` output.

GUI impact:

- none.

Rollback:

- remove module and restore old `should_use_are()`/`contextualize_prompt()` call sites.

### `write_barrier.py`

Purpose: Phase One WriteBarrier shim around persistence. It is not the full Diode runtime.

Interfaces:

- `WriteIntent`: session_turn, durable_fact, durable_preference, tmf_snapshot, trace
- `writeback_allowed(intent, route_state, source, query, output) -> bool`
- `writeback_decision(...) -> dict`

Existing behavior:

- `finalize_reply()` always writes session trace and session turn, may promote durable memory through `maybe_promote_memory()`, and writes TMF backloop after output.

Proposed behavior:

- Trace writes remain allowed as audit records.
- Authoritative durable memory writes require explicit WriteBarrier approval.
- Session turn persistence can remain non-authoritative but must be marked as session trace material, not truth.
- Generated output must not enter authoritative memory merely because it was generated.

Dependencies:

- `claire_runtime_router.py` route state.

GUI impact:

- none.

Rollback:

- restore direct calls from `finalize_reply()`.

### `claire_runtime_router.py`

Purpose: own the one authoritative chat path for Phase One.

Interfaces:

- `route_chat_message(q: str, provider_generate: Callable, retrieval_adapters: dict | None = None) -> RouteResult`
- `RouteResult`: source, reply, trace_payload, writeback_policy
- `normalize_input(q) -> NormalizedInput`
- `provisional_orientation(normalized) -> dict`
- `classify_route(normalized, orientation) -> lane/authority`
- `build_governed_context(...) -> bounded context package`
- `validate_output(...) -> ValidationResult`

Existing behavior:

- `build_reply()` owns all routing and returns early through many handlers.

Proposed behavior:

- `build_reply()` delegates normal chat to `route_chat_message()`.
- The route function executes: normalization -> provisional orientation -> C3RP lane classification -> authority -> memory eligibility -> optional governed retrieval -> relevance/FARE projection -> Sentinel/Diode admission gate -> dynamic GO/provider generation -> output validation -> trace -> approved writeback only.
- Phase One "Sentinel/Diode" are minimal enforceable gates, not full named architecture paint.

Dependencies:

- `intent_classifier.py`, `memory_eligibility.py`, `lane_router.py`, `relevance_gate.py`, `write_barrier.py`, existing GO provider function `query_llm()`.

GUI impact:

- none.

Rollback:

- make `build_reply()` call old logic or restore file from hash/branch.

## Existing Files And Functions

### `claire_gui.py`

Line ranges:

- `query_are()` around 5884
- `governed_are_recall()` around 5987
- `maybe_promote_memory()` around 7532
- `contextualize_prompt()` around 7568
- `shape_document_reply()` around 7851
- canned/system reply detectors around 7912-8384
- `finalize_reply()` around 11638
- `build_reply()` around 11681
- `search_uploaded_documents()` around 12170
- `query_llm()` around 12386

Existing behavior:

- `build_reply()` calls `relevant_recent_context(q)` before classification.
- Many special handlers can return final answers before classification and before GO generation.
- `contextualize_prompt()` can inject recent session memory, durable memory, and Gyro prefix without explicit eligibility.
- `search_uploaded_documents()` can read document memory under broad keyword rules.
- `query_are()` can be called by multiple helpers without a single route-state contract.
- `finalize_reply()` persists trace/session/durable/TMF after cleanup, with no formal WriteBarrier approval.

Proposed behavior:

- Add a minimal backend hook in `build_reply()` for normal chat: call `route_chat_message()`.
- Preserve deterministic hard stops only for explicit demo mode, protected admin/security refusal, writing lane if user explicitly asks to rewrite/draft, and status/empty-state protocol responses.
- Do not let architecture, benchmark, pipeline, identity, ARE, RAG, runtime, or general system-description handlers return final answers. They may become hints/facts in the bounded context package only when eligible.
- `contextualize_prompt()` must not be called unless `route_chat_message()` has allowed SUPPORT/STRICT/REQUIRED memory. For OFF, GO receives only normalized input and compact route instructions.
- `query_are()`, `search_uploaded_documents()`, `relevant_recent_context()`, durable memory lookup, and Gyro prefix generation must be reachable only through the route's memory eligibility decision for normal chat.
- `query_llm()` remains the GO/provider invocation; do not remove providers and do not migrate HTTP clients.
- `finalize_reply()` uses WriteBarrier decision to limit authoritative writeback.

Dependencies:

- New `claire_runtime_router.py`, `memory_eligibility.py`, `write_barrier.py`.

GUI impact:

- none if backend-only ranges are edited.

Rollback:

- revert `claire_gui.py` to hash above or reverse the backend hook patch.

### `intent_classifier.py`

Line ranges:

- `detect_question_lane()` around 219
- `classify_query()` around 259
- `lanes_for_intents()` around 339
- `suppressed_for_intents()` around 362

Existing behavior:

- Intent taxonomy is old: legal/philosophical/architectural/technical/psychological/operational/mixed.
- Detected lanes are old: ABSTRACT_REASONING, FACTUAL_RECALL, INTERNAL_MEMORY_LOOKUP, LEGAL_RESEARCH, SYSTEM_STATUS, HYBRID_REASONING_WITH_MEMORY.

Proposed behavior:

- Add Phase One lane mapping to required lanes: CONCEPTUAL, PROJECT_STATE, DOCUMENT_QA, ACTION_REQUEST, CASUAL, SAFETY_SENSITIVE.
- Preserve existing classifier outputs if needed for compatibility, but expose a new route-lane field.
- Add authority hints: public_chat, project_evidence_required, document_scoped, protected_action_required, safety_restricted.
- Classification must be callable without retrieval.

Dependencies:

- `memory_eligibility.py`.

GUI impact:

- none.

Rollback:

- revert classifier file.

### `lane_router.py`

Line range:

- `extract_candidates()` around 192

Existing behavior:

- Extracts text and lane metadata from ARE-like records.

Proposed behavior:

- Preserve extraction.
- Ensure each candidate retains source identity, provenance-ish metadata, lane, store, and raw record.
- Do not make final-answer decisions here.

Dependencies:

- route state and memory eligibility.

GUI impact:

- none.

Rollback:

- revert file.

### `relevance_gate.py`

Line range:

- `gate_retrieval_candidates()` around 178

Existing behavior:

- Scores lane, semantic, entity, question type, and support role.

Proposed behavior:

- Treat this as Phase One FARE projection precursor.
- Require memory eligibility and active route lane as inputs.
- Rejected candidates must be traceable but never included in provider prompt.
- Retrieved fragments cannot become final answers directly.

Dependencies:

- `memory_eligibility.py`, `claire_runtime_router.py`.

GUI impact:

- none.

Rollback:

- revert file.

### `answer_planner.py`

Line range:

- `conceptual_answer()` around 34 and hardcoded answer helpers below it.

Existing behavior:

- Contains question-specific long final answers for Ship of Theseus/VSC/ARE scenarios.

Proposed behavior:

- Demote from final-answer authority.
- Either remove from normal chat path or convert to compact internal hints/facts only.
- Dynamic GO/provider generation must produce the actual answer.

Dependencies:

- route result and GO provider.

GUI impact:

- none.

Rollback:

- revert file.

### `test_memory_routing.py`

Existing behavior:

- Good tests exist for suppressing legal leakage.
- Several tests assert canned final answers from architecture/identity/governance/memory handlers.

Proposed behavior:

- Update tests to assert authority order and contamination prevention rather than exact canned answers.
- Add tests for the reported failures:
  - "How would you benchmark ARE against FAISS or Pinecone fairly?"
  - "Show me your pipeline from input to output."
  - "Claire can you speak Spanish?"
- Add instrumentation tests proving no recall call before classification/memory eligibility.

Dependencies:

- route module and mocked provider/retrieval functions.

GUI impact:

- none.

Rollback:

- revert test file.

## GUI-FOLDER BACKEND EDIT REQUEST

File: `claire_gui.py`

Function: `build_reply(q: str)`

Line range: approximately 11681-12005

Exact backend defect:

- `build_reply()` calls session-context retrieval before classification.
- It lets many special handlers return final answers before the governed path.
- It calls or permits document memory, ARE memory, durable memory, and Gyro prompt-prefix injection without a single memory eligibility decision.
- It routes some architecture/identity/benchmark/pipeline/system questions to canned text rather than dynamic GO/provider generation.

Exact proposed change:

- Add one backend delegation hook for normal chat: `route_chat_message(...)`.
- Move normal chat through the Phase One path: normalize -> provisional orientation -> classify -> authority/memory eligibility -> optional governed retrieval -> relevance/admission -> GO/provider generation -> output validation -> trace/writeback policy.
- Keep deterministic protocol/safety/empty-state/demo/status paths only where required.
- Remove pre-classification `recent_context = relevant_recent_context(q)` from normal chat.
- Prevent `contextualize_prompt()` and Gyro/session/durable/document recall from running unless route state permits memory.

Why unavoidable:

- The live `/ask`, `/reply`, and streaming APIs all call `build_reply()`.
- Backend orchestration currently lives inside `claire_gui.py`.
- A separate module can own the new logic, but `build_reply()` must call it.

Visible GUI impact: none.

External-module alternative:

- Implement the route in `claire_runtime_router.py`, then keep the `claire_gui.py` edit to a minimal delegation hook plus adapter functions.

Rollback method:

- Restore `claire_gui.py` to hash `3de33536783fcd9f323bf5e9ecf95d45b6454b137aa9851b170e382ef09e2be7`, or reverse only the `build_reply()` backend hook patch.

## Canned Handlers To Demote

Demote from final-answer authority in normal chat:

- `system_difference_reply()`
- `governance_value_reply()`
- `memory_handling_reply()`
- `provenance_design_reply()`
- `continuity_drift_reply()`
- `architecture_simple_reply()`
- `core_architecture_reply()`
- `enterprise_system_reply()`
- `self_demo_reply()`
- `informatica_stack_brief_reply()`
- `known_general_reply()` except narrow deterministic fact/status cases if explicitly allowed
- `conceptual_answer()` and long answer helpers in `answer_planner.py`
- hardcoded architecture/identity/ARE/RAG/pipeline/benchmark responses in `main.go` should be treated as legacy fallback behavior and not authoritative for the Python route in Phase One

Keep hardcoded text only for:

- errors
- safety notices
- empty states
- deterministic protocol responses
- explicit UI copy
- protected admin/security refusals
- explicit demo-mode protocol payloads

## Recall Paths To Move Behind Eligibility

- `relevant_recent_context()`
- `relevant_durable_memory()`
- `query_are()`
- `governed_are_recall()`
- `search_uploaded_documents()`
- `contextualize_prompt()`
- `gyro_stabilized_prefix()`
- `are_glasses_prefix()`
- `GyroAnalogRecallEngine.stabilize_vision()`
- `AREVirtualGlasses.observe_and_recall()`
- `query_spectacle()` except explicit demo protocol path
- Scholar, CourtListener, Drive cache, and document search handlers for normal chat

## Dependencies

- GO backend at `LLM_URL` must remain intact.
- Existing provider behavior must remain intact.
- Existing HTTP client choices must remain intact during Phase One.
- ARE server may be unavailable; route must continue with memory OFF/none/error according to eligibility.

## Rollback Steps

1. Confirm current branch is `codex/claire-backend-repair`.
2. Revert only Phase One files listed above.
3. Verify protected GUI hashes if `claire_gui.py` was edited.
4. Run routing tests.
5. Leave audit/plan files intact unless explicitly asked to remove them.

