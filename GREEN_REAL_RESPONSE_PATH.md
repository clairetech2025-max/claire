# GREEN Real Response Path

This report maps the actual code path in the current GREEN branch. It does not treat file presence as runtime activation.

## Main User Chat Path

Observed entrypoints:

- `claire_gui.py` `/reply`
- `claire_gui.py` `/ask`

Actual call chain for normal chat:

1. User input reaches `claire_gui.build_reply(q, debug)`.
2. `build_reply` first checks local direct-response helpers, including `public_operator_tone_reply`.
3. If no local direct response is returned, `build_reply` requires `CLAIRE_GOVERNED_RUNTIME`.
4. `CLAIRE_GOVERNED_RUNTIME.handle_user_message(...)` runs in `claire_runtime.ClaireRuntime`.
5. `ClaireRuntime.handle_user_message` generates a trace ID with `trace_logger.new_trace_id`.
6. Input is normalized and redacted through `DiodeProtocol`.
7. C3RP routing runs through `claire_runtime_router` and `lane_classifier`.
8. `HandshakeBroker` resolves authority and allowed memory scopes/tools.
9. `GyroOrientationLayer` evaluates posture before generation.
10. If Gyro or authority blocks the request, `LoopbackLayer` can return before model generation.
11. `_recall_memory(...)` runs before provider generation.
12. Recall uses either:
    - `original_are_bridge.read_original_are_history` plus FAISS-style helper `faiss_are_index.query_records` when `use_original_are=True`; or
    - `AREMemoryStore` SQLite recall methods when a memory store is injected.
13. `_memory_supports_active_query(...)` filters candidates by lane, scope, entity, and term overlap.
14. `context_builder.build_context_packet` builds provider context.
15. `nemotron_adapter.build_messages` constructs messages.
16. `nemotron_adapter.call_nemotron` calls the provider path.
17. Provider output is sanitized, loopback-checked, Sentinel-validated, and boundary-filtered.
18. `_commit_memory(...)` decides whether the turn becomes durable memory.
19. `TraceLogger.log(...)` writes append-only JSONL and SQLite trace records.
20. `AREMemoryStore.append_session_trace(...)` writes a session trace if an injected store is active.
21. Response returns to `claire_gui.build_reply`.

Trace evidence:

- Normal path trace steps include `are_chronological_recall` before `nemotron_prompt_construction`.
- The new continuity tests assert this order.

## Demo Mode Path

Observed entrypoint:

- same `/reply` or `/ask` route when `demo_mode=true`

Actual call chain:

1. `claire_gui.build_governed_demo_payload(...)`
2. `ClaireRuntime.handle_user_message(..., metadata={"demo_mode": True})`
3. `ClaireRuntime.handle_demo_message(...)`
4. Backend assembles fixed JSON structure.
5. Trace is persisted to `data/traces.jsonl`.

Status:

- This is a controlled demonstration path.
- It must not be counted as real provider-backed CLAIRE work.

## Public Demo Machine Path

Observed entrypoint:

- `claire_gui.py` `/claire/query`

Actual behavior:

1. Accepts query.
2. Runs `_public_demo_orientation`.
3. Allows only a small demo action such as `list_files`.
4. Writes demo machine trace rows.
5. Returns result.

Status:

- This is public demo machinery, not the main CLAIRE runtime.

## Veritas Legal Path

Observed entrypoints:

- `claire_gui.py` `/upload`
- `claire_gui.py` `/upload-folder`
- `claire_gui.py` `/veritas-legal/run`
- `veritas_legal.engine.EvidenceEngine`

Actual call chain for GUI Veritas run:

1. Uploaded file is saved locally by `_ingest_one_uploaded_file`.
2. Text is extracted and chunked.
3. `ingest_document_chunks` sends chunks to `claire_ingest_bridge`.
4. `/veritas-legal/run` loads the hardened parser.
5. Parser output JSONL is fed into `EvidenceEngine.ingest_parser_jsonl`.
6. `EvidenceEngine` assigns `matter_id`, `source_doc_id`, `source_hash`, `text_sha256`.
7. Legal evidence event is written through ARE adapter.
8. Governed legal metadata references the ARE event SHA.
9. Summary and traceable paths are returned.

Status:

- Veritas TXT/parser/metadata/packet workflow is verified by tests.
- This does not mean advanced contradiction, missing evidence, or legal strategy is complete.

## Provider Path

Observed code:

- `nemotron_adapter.call_nemotron`

Actual behavior:

- If `provider_generate` is supplied, runtime uses in-process provider callback.
- If `NVIDIA_API_KEY` exists, runtime calls NVIDIA NIM-compatible endpoint.
- If no API key exists, runtime can use a local bridge at `CLAIRE_LOCAL_LLM_URL` / `LLM_BASE_URL`.
- If no local bridge responds, runtime falls back to deterministic stub output.

Status:

- Real provider-backed GREEN was not verified in this pass.
- Provider validation is blocked unless a real provider secret or local model endpoint is configured.
