# CODEX CLAIRE GYRO PHASE ONE TEST PLAN

Status: planning only. Do not implement until `APPROVED PHASE ONE CHANGE PLAN`.

## Test Objective

Prove Phase One enforces execution order and prevents stale memory, retrieved fragments, and canned responses from controlling normal final answers.

## Core Invariants

1. Normalization occurs before classification.
2. Provisional orientation occurs before lane classification.
3. Lane classification completes before any recall.
4. Authority evaluation and memory eligibility complete before any recall.
5. Memory mode OFF prevents session, durable, document, ARE, Gyro prefix, and prompt-prefix recall.
6. Retrieved fragments cannot become final answers directly.
7. Rejected candidates never enter the provider prompt.
8. Canned architecture/system replies are not authoritative in normal chat.
9. Output validation runs before persistence.
10. Authoritative writeback requires WriteBarrier approval.
11. Visible GUI files remain unchanged unless separately approved.

## Required Unit Tests

### Route Order Tests

- Mock `relevant_recent_context`, `relevant_durable_memory`, `query_are`, `search_uploaded_documents`, `gyro_stabilized_prefix`, and provider generation.
- Assert classifier and memory eligibility are called first.
- Assert recall mocks are not called for CASUAL and OFF-mode CONCEPTUAL prompts.

### Reported Failure Regressions

Prompt: `How would you benchmark ARE against FAISS or Pinecone fairly?`

Expected:

- lane: CONCEPTUAL or technical benchmark lane
- memory mode: OFF or SUPPORT with no admitted stale session/legal/personal memory
- provider called dynamically
- final answer does not contain missing-memory refusal, personal legal fragments, or unrelated architecture fragments

Prompt: `Show me your pipeline from input to output.`

Expected:

- lane: CONCEPTUAL/architecture
- dynamic GO/provider generation
- no stale personal/legal/session fragments
- no direct canned pipeline speech as final authority

Prompt: `Claire can you speak Spanish?`

Expected:

- lane: CASUAL or direct capability
- memory mode: OFF
- provider generation or short deterministic capability response if classified as empty-state/protocol
- no architecture stack answer

### Conceptual Leakage Tests

- Ship of Theseus / VSC / ARE prompt rejects legal case and personal memory.
- Architecture and benchmark questions reject personal/legal/prior-project memory unless explicitly requested and eligible.
- "What is RAG compared to ARE?" must not surface stale legal, session, or document snippets.

### Document Scope Tests

- Document questions use STRICT memory.
- If no selected/latest document is available, answer says verified document evidence is unavailable.
- A document hit from a different uploaded file is rejected.
- Retrieved document text is passed as bounded context, not returned directly.

### Project-State Tests

- Project-state questions use REQUIRED verified evidence.
- If no local evidence was inspected by the route, answer must state verified evidence is unavailable.
- Session memory cannot substitute for repo evidence.

### Action Request Tests

- Gumroad/Azure/business operations remain draft-only unless protected approval exists.
- Publishing, uploading, emailing, posting, spending, restarting, or account-state changes are blocked or require protected approval.

### Safety-Sensitive Tests

- Safety lane sets memory mode OFF/QUARANTINED when appropriate.
- Tool output is treated as untrusted signal.
- Authority revocation blocks execution and writeback.

### WriteBarrier Tests

- `remember_turn` may write non-authoritative session trace only when allowed.
- `remember_durable_memory` is blocked without WriteBarrier approval.
- `maybe_promote_memory` cannot write durable memory from generated text without explicit approval.
- Rejected/quarantined memory can be traced but not admitted.

### Prompt Package Tests

- Provider prompt for OFF mode contains normalized user input and route instructions only.
- Provider prompt for SUPPORT/STRICT contains only admitted candidate summaries with source, lane, and provenance metadata.
- Rejected candidates are absent from prompt but present in trace.

### GUI Protection Tests

- Compare SHA-256 hashes of protected GUI/static files before and after Phase One.
- If `claire_gui.py` backend hook changes the whole-file hash, verify no changes in protected visible line ranges.
- No HTML/CSS/JS/static asset diffs permitted.

## Existing Tests To Update

`test_memory_routing.py` currently asserts exact canned answers for several architecture and identity prompts. Update those tests to assert:

- correct route state
- dynamic provider invocation
- absence of contamination
- no exact canned final-answer authority
- preserved Claire voice constraints through system prompt/provider output

Tests likely needing changes:

- public identity query tests
- system difference tests
- governance value tests
- memory handling tests
- provenance design tests
- architecture simple/core architecture tests
- enterprise system question tests

## Test Execution

Preferred:

`venv/bin/python test_memory_routing.py`

Optional compile check:

`venv/bin/python -m py_compile claire_gui.py intent_classifier.py lane_router.py relevance_gate.py answer_planner.py claire_runtime_router.py memory_eligibility.py write_barrier.py test_memory_routing.py`

No package installs. No service restarts unless separately approved.



## Implemented Phase One Test File

Added `test_phase_one_runtime.py`.

Current focused validation:

- classification and memory eligibility precede recall
- OFF mode performs no long-term retrieval
- rejected context is absent from generation prompt
- conceptual prompt path does not call ARE
- document question uses STRICT mode and does not return a raw fragment directly
- canned architecture handler is bypassed as final authority in Python route
- durable/TMF writeback is blocked by WriteBarrier
- direct CASUAL eligibility check returns OFF

Command run:

`venv/bin/python test_phase_one_runtime.py`

Result: passed, 8 tests.

Remaining validation gap:

Live GO samples still expose provider-side canned responses in `main.go`. That is outside the approved `claire_gui.py` hook and must be handled by a separate provider/control-plane approval.
