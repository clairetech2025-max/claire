# AGENTS.md ADDITION — CLAIRE DEMO MODE SPEC

## PURPOSE

The input:
"Schedule a horseback ride tomorrow at 10am"

is NOT a feature request.

It is a SYSTEM DEMONSTRATION TRIGGER.

This input exists to validate and expose the Claire architecture:
- ARE (memory recall)
- Sentinel (policy validation)
- Decision layer
- Trace logging and replay

DO NOT implement scheduling functionality.
DO NOT integrate calendars.
DO NOT perform real-world execution.

---

## DEMO MODE BEHAVIOR

When demo_mode = true:

You MUST execute the following pipeline:

1. INGEST INPUT
2. RUN ARE RECALL
3. RUN POLICY VALIDATION (Sentinel)
4. GENERATE DECISION (simulation only)
5. GENERATE OUTPUT
6. BUILD TRACE OBJECT
7. RETURN STRUCTURED RESPONSE

---

## REQUIRED RESPONSE FORMAT

Return JSON EXACTLY in this shape:

```json
{
  "trace_id": "<unique id>",
  "demo_mode": true,
  "identity": "<short system description>",
  "input_received": "<verbatim input>",
  "recall_check": {
    "status": "found | none | error",
    "summary": "<short summary>",
    "items": []
  },
  "policy_validation": {
    "status": "allowed | blocked | warning | error",
    "summary": "<reason>",
    "rules_triggered": []
  },
  "decision": "<what was decided>",
  "output": "<final user-facing result>",
  "trace_summary": {
    "steps_executed": [],
    "decisions_made": []
  }
}
```

---

## CRITICAL RULES

- NEVER fabricate memory
- NEVER fabricate policy checks
- NEVER perform real actions
- ALWAYS simulate execution
- ALWAYS include trace_id
- ALWAYS include input_received
- ALWAYS include output
- ALWAYS include trace_summary
- KEEP responses concise

---

## ARE INTEGRATION RULE

If no memory exists:
- status = "none"
- summary = "No relevant prior memory found."
- items = []

---

## POLICY RULE

If no blocking condition:
- status = "allowed"
- summary = "No policy constraints violated."
- rules_triggered = []

If system uncertain:
- status = "warning"

---

## DECISION RULE

All actions must be SIMULATED.

Example:
"Simulating scheduling action for demonstration only; no real-world execution performed."

---

## TRACE REQUIREMENTS

trace_id must:
- be generated per request
- be included in logs
- be reusable for replay

trace_summary must include:
- steps_executed:
  ["ingest_input", "retrieve_memory", "validate_policy", "generate_response"]
- decisions_made:
  based on recall + policy outcome

---

## FAILURE HANDLING

If ARE fails:
- recall_check.status = "error"
- continue execution

If policy fails:
- policy_validation.status = "warning"
- continue execution

SYSTEM MUST NOT CRASH

---

## SUCCESS CRITERIA

For the test input, the system must clearly show:
- no memory found (if true)
- policy allowed
- simulated decision
- final output
- full trace structure

---

## GOAL

This is NOT a chatbot feature.

This is a SYSTEM PROBE that proves Claire can:
- observe
- recall
- validate
- decide
- and trace its own behavior

---

DO NOT DEVIATE FROM THIS SPEC.

---

# CLAIRE MEMORY ROUTING SPEC — LANE GOVERNANCE

## PURPOSE

Claire must behave like a reasoning system with governed memory support, not a memory dump with a chatbot attached.

The failure case is a conceptual identity/architecture question being answered with an unrelated legal memory hit. That is not a model eloquence problem. It is a routing problem.

## REQUIRED ORDER FOR NORMAL ANSWERS

Before any broad ARE answer is allowed into the final response:

1. classify the query intent
2. choose allowed memory lanes
3. suppress irrelevant lanes
4. retrieve candidates only as support
5. gate candidates for lane, entity, semantic, question-type, and support-role match
6. answer directly when reasoning_first is selected
7. log accepted and rejected candidates in trace

## NON-NEGOTIABLE RULE

Do not substitute retrieval for a direct answer.

If the user asks a philosophical, architectural, technical, or mixed reasoning question, Claire must answer the question first and use memory only as support. Unrelated case law, dockets, generic document hits, and off-lane memory must be rejected from the final answer.

When the user asks a conceptual or philosophical question, answer the reasoning directly. Use retrieval only as support. Do not substitute irrelevant retrieved material for analysis.

Legal citations and case law may only be surfaced when the user asks for legal research or when legal authority is directly necessary to answer the question.

## TEST ANCHOR

The prompt about Ship of Theseus, deterministic VSC, U.S. Provisional Patent No. 63/942,560, incremental replacement, human memory, ARE modules, and sovereign intelligence must:

- classify as mixed philosophical/architectural/technical
- use reasoning_first
- suppress unrelated legal_case retrieval
- answer with a synthesized identity and sovereignty analysis
- never output Paisley Park v. Boxill or random case law as the answer

---

## IMPLEMENTATION DETAILS (NON-OPTIONAL)

### 1. BACKEND ENTRYPOINT

Modify the existing /ask endpoint (or equivalent):

- Accept:
  {
    "input": "<user text>",
    "demo_mode": true|false
  }

- Do NOT create a separate endpoint for demo mode.
- Demo mode must be a conditional branch in the same pipeline.

---

### 2. TRACE ID GENERATION

- Generate trace_id at the very start of request handling
- Format:
  "trace_<timestamp>_<short-random>"

Example:
"trace_20260419_153012_ab12"

- This ID must:
  - be returned in response
  - be logged
  - be reusable for replay

---

### 3. ORDER OF EXECUTION (STRICT)

The system MUST execute in this exact order:

1. ingest_input
2. generate_trace_id
3. run_are_recall
4. run_policy_validation
5. build_llm_prompt (include recall + policy summaries)
6. call_llm
7. assemble_response_json
8. persist_trace
9. return_response

DO NOT reorder these steps.

---

### 4. LLM PROMPT CONSTRUCTION

When demo_mode=true:

- Use a dedicated system prompt:
  - concise
  - structured
  - no poetic language
  - no hidden chain-of-thought

- Inject:
  - user input
  - recall summary
  - policy summary

DO NOT inject raw logs or full memory dumps.

---

### 5. RESPONSE ASSEMBLY (CODE-LEVEL ENFORCEMENT)

Do NOT rely on LLM to generate full JSON.

Instead:
- LLM generates:
  - identity
  - decision
  - output

Backend must construct:
- trace_id
- input_received
- recall_check
- policy_validation
- trace_summary

This prevents malformed output.

---

### 6. TRACE PERSISTENCE

Persist each trace as JSONL:

File:
data/traces.jsonl

Each entry:
{
  "trace_id": "...",
  "timestamp": "...",
  "input": "...",
  "recall": {...},
  "policy": {...},
  "decision": "...",
  "output": "...",
  "steps": [...]
}

Append-only.

---

### 7. REPLAY ENDPOINT

Implement:

GET /trace/{trace_id}

Behavior:
- search JSONL for matching trace_id
- return full stored object

If not found:
- return 404 with message

---

### 8. DEFAULT FALLBACKS

If ARE unavailable:
- recall_check.status = "error"
- summary = "Recall subsystem unavailable."

If Sentinel unavailable:
- policy_validation.status = "warning"
- summary = "Policy subsystem unavailable."

SYSTEM MUST CONTINUE.

---

### 9. UI REQUIREMENTS

If UI exists:

- Add DEMO MODE toggle (button or switch)
- When enabled:
  - render response sections visually:
    - Identity
    - Input
    - Recall
    - Policy
    - Decision
    - Output
    - Trace

- Show trace_id at top

- Add button:
  "Replay Last Trace"
  -> calls /trace/{trace_id}

---

### 10. VALIDATION RULE

Before returning response:

ASSERT:
- trace_id exists
- input_received exists
- output exists
- trace_summary.steps_executed not empty

If any fail:
- return error
- do NOT silently continue

---

### 11. MINIMALISM RULE

- Do NOT add new frameworks
- Do NOT refactor unrelated code
- Do NOT implement real scheduling logic
- Do NOT expand scope

Only implement demo_mode pipeline.

---

END IMPLEMENTATION DETAILS

---

# CLAIRE FINAL LOCK DIRECTIVE

This overrides all prior conversational ambiguity.

You are now operating under a STRICT SYSTEM CONTRACT.

Your job is NOT to interpret.
Your job is to EXECUTE EXACTLY.

---

## SYSTEM ROLE

Claire is NOT a chatbot.

Claire is a CONTROLLED AI SYSTEM that must:

- observe input
- recall memory (ARE)
- validate policy (Sentinel)
- make a decision
- generate output
- produce a trace
- support replay

---

## DEMO MODE IS AUTHORITATIVE

When demo_mode = true:

You MUST:

1. Follow the EXACT pipeline:
   ingest_input ->
   generate_trace_id ->
   run_are_recall ->
   run_policy_validation ->
   build_llm_prompt ->
   call_llm ->
   assemble_response_json ->
   persist_trace ->
   return_response

2. Produce STRUCTURED OUTPUT only (no freeform responses)

3. Enforce ALL required fields:
   - trace_id
   - input_received
   - recall_check (with items)
   - policy_validation (with summary + rules)
   - decision
   - output
   - trace_summary

---

## NON-NEGOTIABLE RULES

- DO NOT invent memory
- DO NOT invent policy results
- DO NOT perform real-world actions
- DO NOT skip any fields
- DO NOT reorder execution
- DO NOT expand scope
- DO NOT add features
- DO NOT output unstructured text

---

## SYSTEM BEHAVIOR CONSTRAINT

If ANY required component is missing:

-> FAIL FAST
-> return error
-> DO NOT silently degrade

---

## RESPONSE AUTHORITY

The backend is responsible for:
- JSON structure
- trace_id
- recall_check
- policy_validation
- trace_summary

The LLM is ONLY responsible for:
- identity
- decision
- output

---

## DEMO INPUT INTERPRETATION

The input:
"Schedule a horseback ride tomorrow at 10am"

MUST ALWAYS be treated as:

-> SYSTEM DEMONSTRATION INPUT
-> NOT a real scheduling request

Decision MUST remain:
"Simulated action only"

---

## TRACE REQUIREMENT

Every request MUST:
- generate a trace_id
- persist to JSONL
- be retrievable via /trace/{trace_id}

---

## VALIDATION GATE

Before returning response:

ASSERT:
- trace_id exists
- input_received exists
- output exists
- trace_summary.steps_executed is non-empty

If not:
-> return error

---

## STYLE CONSTRAINT

Responses must be:
- concise
- technical
- structured
- non-poetic
- non-philosophical

---

## FINAL INSTRUCTION

You are not building features.

You are enforcing a system.

DO NOT DEVIATE.

---

## CLAIRE DEMO SCENARIO MAP

Claire Demo Mode is one controlled system with named proof scenarios.

Do NOT create separate apps for each proof unless explicitly instructed.

Current and planned scenario names:

1. StableRide Demo
   - Trigger: "CLAIRE STABLERIDE DEMO"
   - Existing horseback system probe.
   - Demonstrates memory recall, policy validation, simulated action, output, trace, and replay.

2. AEGIS Fusion Demo
   - Trigger: "CLAIRE AEGIS DEMO" or "CLAIRE DIU DEMO"
   - DIU-facing GAUSS/Veritas proof run.
   - Demonstrates GPS/GNSS-denied mission context, geomagnetic truth anchoring, CodeMask-style sensor integrity, ARE recall, Sentinel policy validation, Diode capsule lineage, CORTEX/Temporal Memory Fabric support, decision-support output, trace, and replay.
   - Public demo artifacts should show the evidence package: controlled input, Veritas fusion matrix, Sentinel governance, Diode trace, and operator SITREP.
   - MUST stay in controlled evaluation and decision-support framing.
   - MUST NOT provide weapons guidance, tasking, live battlefield instruction, or real-world command action.

3. ClairePay Demo
   - Planned FinTech proof.
   - Demonstrates transaction signal intake, risk/compliance validation, decision, output, audit trace, and replay.

4. Veritas Legal Demo
   - Planned legal research proof.
   - Demonstrates CourtListener/legal recall, jurisdiction and legal-advice warnings, research output, trace, and replay.

All scenarios must preserve the same strict demo contract:
observe -> recall -> validate -> decide -> output -> trace -> replay.
