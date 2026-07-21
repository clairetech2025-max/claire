# GREEN Functional Scorecard

| Area | Score | Evidence |
|---|---|---|
| Conversation continuity | VERIFIED_WORKING | `test_conversation_continuity.py` passes five-turn fact/correction flow using real `ClaireRuntime`, `AREMemoryStore`, and trace. |
| Durable recall | VERIFIED_WORKING | `test_green_restart_continuity.py` and `claire_are/tests/test_plugin_are.py` verify durable memory after restart. |
| Relevance filtering | PARTIALLY_WORKING | Continuity test verifies unrelated arithmetic turn receives no project memory. Existing `test_memory_routing.py` covers legal-lane suppression. Broader user/session leakage tests remain incomplete. |
| Correction handling | PARTIALLY_WORKING | Test verifies old and corrected records are both recalled chronologically; accepted-current resolution still depends on provider reasoning. |
| Provider generation | BLOCKED | Real provider-backed path requires `NVIDIA_API_KEY` or live local model bridge. Current tests use in-process provider callbacks or local/stub. |
| Tool execution | PARTIALLY_WORKING | Component tests verify local file read, repository search, ARE ingest/recall, Veritas packet generation. Main `ClaireRuntime` general tool dispatcher remains unverified. |
| Artifact creation | VERIFIED_WORKING | `test_claire_real_work.py` and `test_veritas_end_to_end.py` verify Markdown review packet creation. |
| Restart continuity | VERIFIED_WORKING | `test_green_restart_continuity.py` verifies same SQLite memory/trace paths after runtime reconstruction. |
| Veritas workflow | VERIFIED_WORKING_FOR_TXT_LOCAL | `test_veritas_end_to_end.py` verifies source hash, source_doc_id, legal metadata, ARE event SHA, timeline, packet. Broader file types need more tests. |
| Governance | PARTIALLY_WORKING | Scope policy, Diode, authority broker, Sentinel, and lane filtering are wired. Real step-up auth and enterprise permissioning are not implemented. |
| Traceability | VERIFIED_WORKING | Runtime trace and Veritas trace files are generated and asserted in tests. GUI `/trace/{trace_id}` route shadowing risk remains. |
| Honest degradation | PARTIALLY_WORKING | Veritas packet reports CourtListener unavailable under mocked failure; unsupported packet format raises `ValueError`. Provider fallback still risks hiding missing real provider unless tests require real provider metadata. |

## Current Functional Verdict

GREEN is stronger than the prior shell demo, but it is not fully operational CLAIRE yet.

Verified now:

- Real multi-turn memory continuity with correction history.
- Real recall-before-generation ordering in trace.
- Real durable memory after restart for injected SQLite store.
- Real Veritas local evidence provenance and packet artifact.
- Real ARE plug-in memory ingest/recall/verify/audit.

Still blocked or incomplete:

- Real provider-backed end-to-end request.
- Main-runtime general tool dispatcher for arbitrary tasks.
- Full user/session isolation coverage.
- Corrupted-memory exclusion in the main `ClaireRuntime` path.
- Cross-restart validation using restored production-like Lane A/B preserved data.
- Veritas beyond local TXT/parser evidence workflow.
