# CLAIRE Feature Certification Sprint

Date: 2026-07-12

Mode: product certification, not architecture expansion.

Certification command:

```bash
venv/bin/python -m pytest -q --durations=20 test_claire_stream_routes.py test_session_continuity.py test_conversation_continuity.py test_green_restart_continuity.py test_veritas_end_to_end.py tests/test_veritas_legal.py claire_are/tests/test_plugin_are.py test_governed_runtime.py test_memory_routing.py
```

Result:

```text
100 passed, 112 warnings in 19.32s
```

Important product fix completed during certification:

- Removed duplicate GUI route registration for `/trace/{trace_id}` that caused the public demo trace alias to shadow runtime trace replay.
- Added `test_trace_route_returns_runtime_trace_when_demo_trace_missing`.

## Certified Working Features

| # | Capability | Certified Input | Certified Output | Time Evidence | Dependencies | Failure Modes | Repeatable Test |
|---:|---|---|---|---|---|---|---|
| 1 | ARE plug-in ingest | `AREStore.ingest(text="ARE is the memory authority.", lane="architecture", source="test")` | Accepted memory record with SHA/truth hash | `test_records_can_be_ingested_and_recalled`: ~0.22s | `claire_are`, filesystem | bad path, rejected write, disk failure | `claire_are/tests/test_plugin_are.py::test_records_can_be_ingested_and_recalled` |
| 2 | ARE plug-in recall | query `What is ARE authority?` | Returns saved ARE memory | ~0.22s | same | no matching terms returns empty | same |
| 3 | ARE integrity verification | tamper stored payload | `verify()["valid"] == False` | `test_corrupted_memory_records_fail_verification`: ~0.41s | HMAC key, segment files | missing/corrupted segment | `test_corrupted_memory_records_fail_verification` |
| 4 | ARE audit log | complete via `/v1/llm/complete` | audit includes `recall` and `llm_complete` | API test ~0.24s | FastAPI TestClient | audit root unavailable | `test_public_api_ingest_recall_complete_verify_and_audit` |
| 5 | ARE lane-scoped access | legal lane queries architecture memory | empty memory list | ~0.22s | DiodeGuard | bad lane config could overexpose | `test_legal_lane_cannot_read_architecture_lane` |
| 6 | ARE segment rotation | ingest 5 records with low segment max | multiple segments; chain valid | ~0.24s | TruthSpine | failed manifest/segment write | `test_archive_not_delete_segment_rotation_preserves_chain` |
| 7 | Governed completion wrapper | prompt `Explain ARE.` | recall event logged before completion event | ~0.22s | GovernedGateway | no store, write failure | `test_llm_completion_requires_recall_first` |
| 8 | SQLite runtime memory store | append chat memory event | durable SQLite row | covered by continuity tests | sqlite3 | DB locked/corrupt | `test_green_restart_restores_durable_memory_and_trace_store` |
| 9 | Runtime recall before generation | five-turn codename flow | trace shows recall before prompt construction | `test_five_turn...`: ~0.24s | ClaireRuntime, store, trace | provider callback failure | `test_conversation_continuity.py` |
| 10 | Cross-session continuity | ORCHARD then RIVERSTONE correction | current `RIVERSTONE`, historical `ORCHARD` | continuity suite <1s | session_continuity | unresolved conflict if no correction marker | `test_cross_session_continuity_resolves_correction_without_rewriting_history` |
| 11 | Correction history | save old/new project codename | both records preserved; derived current state updated | ~0.24s | memory + continuity | ambiguous correction | `test_five_turn_project_fact_correction_uses_relevant_memory_only` |
| 12 | Irrelevant memory suppression | unrelated arithmetic after ORCHARD save | no ORCHARD/RIVERSTONE in provider context | ~0.24s | lane routing | bad classification | same |
| 13 | Private memory scope refusal | guest asks private memory | no recalled private memory | `test_guest_cannot...`: ~1.98s | HandshakeBroker | misconfigured scopes | `test_guest_cannot_recall_private_memory` |
| 14 | Sensitive prompt redaction | passphrase prompt | secret absent from answer/trace | memory routing test ~0.14s | DiodeProtocol | novel secret pattern missed | `test_passphrase_not_written_to_trace` |
| 15 | Live trade risk gate | `place a live BTC trade now` | refusal, no execution | ~0.09s-0.11s | lane/risk gates | classifier miss | `test_live_trade_blocked_from_chat` |
| 16 | Loopback unsafe/filler fallback | generic filler provider output | bounded answer, trace notes loopback | governed runtime suite | LoopbackLayer | canned response quality | `test_generic_filler_response_triggers_loopback` |
| 17 | Runtime trace logging | normal runtime turn | trace stored and retrievable | route test + runtime tests | TraceLogger, sqlite3 | route collision fixed; DB failure possible | `test_trace_route_returns_runtime_trace_when_demo_trace_missing` |
| 18 | Veritas direct file ingest | local TXT evidence with date/entity | `EvidenceRecord`, date/entity extraction | Veritas tests | filesystem | unsupported type, file too large | `test_ingest_hash_entities_dates_and_claire_explains` |
| 19 | Veritas source hashing | same file across matters | same source hash, different matter-scoped doc ID | Veritas tests | hashlib | source bytes unavailable | `test_matter_scope_changes_source_doc_id_without_changing_source_hash` |
| 20 | Veritas ARE event adapter | parser/file evidence | `are_event_sha` referenced in metadata | Veritas tests | ARE append adapter | ARE append fallback failure | `test_parser_record_writes_are_event_and_governed_metadata` |
| 21 | Veritas parser JSONL adapter | parser JSONL record | legal evidence record with source metadata | ~0.37s for zip/parser test | parser JSONL | malformed JSON skipped | `test_case_file_parser_output_becomes_are_linked_metadata` |
| 22 | ZIP-slip protection | malicious ZIP paths | only safe path parsed | Veritas tests | zipfile | nested malicious names rejected/skipped | `test_claire_parser_rejects_zip_slip_paths` |
| 23 | Veritas timeline | evidence with `2026-05-14` | timeline entry with source_doc_id and ARE sha | E2E test | regex dates | no date found -> empty timeline | `test_veritas_evidence_workflow_preserves_source_provenance_and_are_reference` |
| 24 | Veritas contradiction section | packet generation | contradictions section always present | E2E test | rule-based detector | false negatives possible | `test_veritas_evidence_workflow_preserves_source_provenance_and_are_reference` |
| 25 | Veritas attorney-review packet | ingested evidence | Markdown packet with exhibit index/timeline/boundary | E2E test | filesystem | unsupported format | `test_claire_real_work.py`, `test_veritas_end_to_end.py` |
| 26 | GUI document upload endpoint | supported upload | saved file, chunks sent to ingest bridge | code path; clean-base smoke | FastAPI, ingest bridge | bridge down, unsupported file | `claire_gui._ingest_one_uploaded_file`; smoke verified earlier |
| 27 | GUI Veritas Legal run | latest uploaded evidence | processed files with hashes/metadata paths | code path; clean-base smoke | parser, Veritas engine | no upload, parser unavailable | `/veritas-legal/run`; smoke verified earlier |
| 28 | ARE fast vault ingest/query | JSON memory, query terms | `Memory Anchored`, recall results | clean-base smoke | FastAPI, JSONL | vault path unwritable | `ARE_SERVER.py` smoke verified earlier |
| 29 | Ingest bridge | normalized payload | bridge returns `ok:true`, forwards to ARE | clean-base smoke | requests, ARE URL | ARE down, token mismatch | `claire_ingest_bridge.py` smoke verified earlier |
| 30 | Runtime trace replay endpoint | `GET /trace/trace_runtime_route_test` | runtime trace JSON | new route test in suite | FastAPI, runtime trace logger | trace not found -> not found/status | `test_trace_route_returns_runtime_trace_when_demo_trace_missing` |

## Partial Feature Review

| Partial Feature | Completion Effort | Action This Sprint | Promotion Status |
|---|---:|---|---|
| Normal chat answering | Medium | No provider work in this sprint; keep partial. | PARTIAL |
| Real provider integration | Medium | Not promoted; requires configured real provider and E2E test. | PARTIAL |
| Memory update | Low | Clarified as append-first correction, not mutation. Already certified as correction history. | PARTIAL/renamed behavior |
| Memory explanation | Low | Trace replay route fixed and tested. | Promoted as runtime trace replay, not full natural-language explanation |
| Uploaded document search | Medium | No new certification. | PARTIAL |
| Upload folder | Low | No direct test added. | PARTIAL |
| Veritas PDF parsing | Medium | No corpus certification. | PARTIAL |
| Veritas DOCX parsing | Medium | No complex DOCX certification. | PARTIAL |
| Veritas parser breadth | High | Keep partial. | PARTIAL |
| CourtListener lookup | Medium | Keep partial pending live API/mocked success tests. | PARTIAL |
| Drive research lane | Medium | Keep partial; app credentials absent. | PARTIAL |
| Scholar/CourtListener open pages | Medium | Keep partial. | PARTIAL |
| Office task endpoints | Medium | Keep partial. | PARTIAL |
| Runtime status page | Low | Health/status remain process checks only. | PARTIAL |
| Session recovery summary | Low | Continuity resolver is certified; recovery summary remains partial. | PARTIAL |
| Tool-use governance metadata | Medium | No general dispatcher added. | PARTIAL |
| Trace replay | Low | Fixed route collision and added test. | WORKING |

## Demo Dependency Review

| Demo Path | Current Treatment |
|---|---|
| StableRide/demo_mode JSON path | Keep isolated as demo; not counted as production scheduling. |
| `/are-demo` memory lane UI | Keep isolated as public demo memory, not private CLAIRE memory. |
| `/are-spectacle` | Keep as concept/demo page. |
| `/claire/query` public machine demo | Keep as demo-only; trace path remains `/machine/trace/{trace_id}`. |
| Canned operator identity replies | Keep as fallback/demo tone, not certified provider reasoning. |
| Deterministic fallback answers | Keep as fallback; certification does not count these as real provider. |

## Sprint Answers

### 1. What can CLAIRE do today that competitors cannot?

CLAIRE can combine append-first governed memory, lane-scoped recall, traceable recall-before-generation, correction history, and source-linked legal evidence records in one local system. The differentiator is not chat fluency. It is the ability to show what memory or source supported a response and preserve that path as auditable state.

### 2. What would a customer realistically pay for today?

Today, a customer could pay for local evidence organization and governed memory workflows:

- organizing messy case/project documents into source-hashed evidence records;
- producing attorney-review packets with exhibit index and timeline;
- preserving project facts and corrections across sessions;
- proving what memory/source was used through trace logs.

### 3. What is the fastest path to the first paying customer?

Offer a paid local evidence-organization pilot: one customer provides a folder of documents, CLAIRE/Veritas produces a source index, timeline, review packet, and traceable evidence metadata. Price it as a fixed-scope setup/review package instead of selling “AI assistant” broadly.

### 4. Five highest-priority engineering tasks before commercial release

1. Configure and certify one real provider path end-to-end.
2. Add direct tests for GUI upload-folder and uploaded-document search.
3. Certify PDF/DOCX parsing with a small realistic document corpus.
4. Replace or clearly label all canned fallback paths in the public UI.
5. Add a simple customer-safe export bundle for Veritas outputs.
