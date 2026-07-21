# GREEN Component Wiring Status

| Component | Status | File / Function | Notes |
|---|---|---|---|
| Main GUI `/reply` and `/ask` | ACTIVE_AND_USED | `claire_gui.build_reply` | Normal user input path. Can still return direct helper replies before runtime. |
| Demo mode branch | ACTIVE_AND_USED | `claire_gui.build_governed_demo_payload`, `ClaireRuntime.handle_demo_message` | Correct for demo probes only; not proof of full CLAIRE. |
| Public demo machine endpoint | ACTIVE_AND_USED | `claire_gui.public_demo_query` | Demo control route with limited synthetic action surface. |
| C3RP / lane router | ACTIVE_AND_USED | `claire_runtime_router`, `lane_classifier.classify_lane` | Used before recall and generation. Project-memory follow-up routing was fixed in this pass. |
| Authority / Handshake Broker | ACTIVE_AND_USED | `handshake_broker.HandshakeBroker.resolve_authority` | Used for scopes/tools. `BUSINESS_FORMATION` scope policy was added in this pass. |
| Diode redaction | ACTIVE_AND_USED | `diode_protocol.DiodeProtocol` | Used before routing and in trace logger. |
| Gyro | ACTIVE_AND_USED | `claire.runtime.gyro.GyroOrientationLayer` | Can stop generation through loopback. |
| Loopback | ACTIVE_AND_USED | `claire.runtime.loopback.LoopbackLayer` | Useful safety fallback, but canned fallback answers must not count as provider-backed reasoning. |
| Sentinel validation | ACTIVE_AND_USED | `sentinel_validator.validate_response` | Runs after provider output. |
| ARE recall gate | ACTIVE_AND_USED | `ClaireRuntime._recall_memory` | Runs before provider generation in normal path. |
| SQLite AREMemoryStore | ACTIVE_AND_USED_WHEN_INJECTED | `are_memory_store.AREMemoryStore` | Used by tests and any runtime constructed with explicit store. |
| Original ARE bridge | ACTIVE_AND_USED_BY_DEFAULT | `original_are_bridge` | Default `ClaireRuntime()` uses original ARE bridge rather than injected SQLite store. |
| FAISS/search helper | ACTIVE_AND_USED_AS_RELEVANCE | `faiss_are_index.query_records` | Downstream relevance only; not memory authority. |
| Provider call | ACTIVE_BUT_FALLBACK_PRONE | `nemotron_adapter.call_nemotron` | Real NIM/local bridge if configured; otherwise deterministic stub. |
| Real external provider | BLOCKED | env `NVIDIA_API_KEY` or local model endpoint | Not verified in this pass. |
| General tool execution in main runtime | IMPLEMENTED_NOT_WIRED | scattered GUI helpers and demo route | No verified main-runtime tool dispatcher for arbitrary real tasks. |
| Upload ingest bridge | ACTIVE_AND_USED | `claire_gui._ingest_one_uploaded_file`, `claire_ingest_bridge.py` | Verified earlier in clean-base smoke and component tests. |
| Veritas Legal engine | ACTIVE_AND_USED | `veritas_legal.engine.EvidenceEngine` | Source IDs, hashes, ARE refs, metadata, packets verified by tests. |
| CourtListener client | PARTIALLY_IMPLEMENTED | `veritas_legal.courtlistener_client.lookup_case_law` | Packet handles unavailable lookup; live network/API behavior not tested here. |
| Trace persistence | ACTIVE_AND_USED | `trace_logger.TraceLogger`, `ClaireRuntime.get_trace` | Runtime traces work; `claire_gui.py` also defines a later `/trace/{trace_id}` public demo alias that may shadow runtime trace retrieval. |
| Restart continuity | VERIFIED_FOR_SQLITE_STORE | `AREMemoryStore`, `TraceLogger` | Verified with isolated durable temp storage and reconstructed runtime. |

## Fake / Demo / Canned Success Paths Found

- `ClaireRuntime.handle_demo_message`: valid demo contract, not real work.
- `claire_gui.public_demo_query`: public demo route; limited hardcoded action handling.
- `nemotron_adapter._deterministic_stub`: provider fallback when no real provider/local bridge exists.
- `LoopbackLayer._direct_general_answer`: canned rescue answers for generic filler and common prompts.
- `claire_gui.public_operator_tone_reply`: direct helper path before governed runtime.
- Multiple GUI presentation sections and proof cards: useful UI, not backend capability.
- Health endpoints: prove process availability only, not functional CLAIRE.

Functional testing must not count any of the above as real provider-backed CLAIRE behavior.
