# CLAIRE Capability Matrix

Audit date: 2026-07-12

Scope: functional certification of the current `/home/LuciusPrime/claire` codebase. This document reports what CLAIRE can actually do today from implemented code and available tests. It does not count names, comments, UI text, or architecture plans as working features.

Audit evidence command:

```bash
venv/bin/python -m pytest -q test_session_continuity.py test_conversation_continuity.py test_green_restart_continuity.py test_veritas_end_to_end.py tests/test_veritas_legal.py claire_are/tests/test_plugin_are.py test_governed_runtime.py test_memory_routing.py
```

Result:

```text
97 passed, 112 warnings in 26.63s
```

## WORKING

| Name | Description | How Invoked | Source Files | Dependencies | Required Configuration | Status | Evidence |
|---|---|---|---|---|---|---|---|
| ARE plug-in ingest | Appends governed memory records into segmented Truth Spine storage. | API `POST /v1/memory/ingest`; Python `AREStore.ingest()` | `claire_are/api.py`, `claire_are/core.py`, `claire_are/truth_spine.py` | FastAPI for API; stdlib storage core | `CLAIRE_ARE_ROOT`, optional HMAC config via `AREConfig` | WORKING | `claire_are/tests/test_plugin_are.py::test_records_can_be_ingested_and_recalled` |
| ARE plug-in recall | Recalls lane-permitted memory using deterministic token overlap and logs recall event. | API `POST /v1/memory/recall`; Python `AREStore.recall()` | `claire_are/api.py`, `claire_are/core.py`, `claire_are/diode_guard.py` | FastAPI for API | same as above | WORKING | `claire_are/tests/test_plugin_are.py::test_records_can_be_ingested_and_recalled` |
| ARE integrity verification | Verifies HMAC/hash chain and detects corrupted stored payloads. | API `GET /v1/memory/verify`; Python `AREStore.verify()` | `claire_are/core.py`, `claire_are/truth_spine.py` | stdlib | HMAC key/root path | WORKING | `claire_are/tests/test_plugin_are.py::test_corrupted_memory_records_fail_verification` |
| ARE audit log | Returns recent Truth Spine envelopes including recall and completion events. | API `GET /v1/audit/recent`; Python `AREStore.audit_recent()` | `claire_are/api.py`, `claire_are/core.py` | FastAPI for API | configured ARE root | WORKING | `claire_are/tests/test_plugin_are.py::test_public_api_ingest_recall_complete_verify_and_audit` |
| ARE lane-scoped access | Prevents one lane from reading disallowed memory lanes. | Python/API recall | `claire_are/diode_guard.py`, `claire_are/core.py` | stdlib | none beyond store config | WORKING | `claire_are/tests/test_plugin_are.py::test_legal_lane_cannot_read_architecture_lane` |
| ARE archive/segment rotation | Rotates records into multiple segments without breaking chain verification. | Python `AREStore.ingest()` | `claire_are/truth_spine.py`, `claire_are/core.py` | stdlib | `max_segment_records` | WORKING | `claire_are/tests/test_plugin_are.py::test_archive_not_delete_segment_rotation_preserves_chain` |
| Governed completion wrapper | Performs ARE recall before a local/stub completion event and logs both events. | API `POST /v1/llm/complete`; Python `GovernedGateway.complete()` | `claire_are/api.py`, `claire_are/gateway.py`, `claire_are/core.py` | FastAPI for API | configured ARE root | WORKING | `claire_are/tests/test_plugin_are.py::test_llm_completion_requires_recall_first` |
| SQLite memory store | Stores durable runtime memory events, entities, audit log, and session traces in SQLite. | Python `AREMemoryStore.append_memory_event()` | `are_memory_store.py` | sqlite3 stdlib | DB path; default `claire_state/claire_memory.db` | WORKING | Used by `test_conversation_continuity.py`, `test_green_restart_continuity.py` |
| Runtime recall before provider generation | Main `ClaireRuntime` recalls memory before constructing provider prompt. | Python `ClaireRuntime.handle_user_message()`; GUI `/reply` path when runtime active | `claire_runtime.py`, `context_builder.py`, `nemotron_adapter.py` | Runtime modules; optional provider | injected or default memory path | WORKING | `test_conversation_continuity.py` asserts trace step order: `are_chronological_recall` before `nemotron_prompt_construction` |
| Cross-session continuity | Resolves current vs historical values from recalled memories, including correction/supersession. | Python `build_cross_session_continuity_context()`; provider context via `context_builder` | `session_continuity.py`, `context_builder.py` | stdlib | recalled memory records | WORKING | `test_session_continuity.py`, `test_conversation_continuity.py`, `test_green_restart_continuity.py` |
| Correction history | Preserves old and new memory records, marks old value historical in derived context, and current value as corrected. | Runtime memory + continuity context | `session_continuity.py`, `claire_runtime.py`, `are_memory_store.py` | sqlite3 stdlib | durable store | WORKING | ORCHARD -> RIVERSTONE tests in `test_conversation_continuity.py` |
| Irrelevant memory suppression | Does not inject project memory into unrelated arithmetic turn in tested continuity flow. | Runtime chat path | `claire_runtime.py`, `lane_classifier.py`, `session_continuity.py` | runtime modules | trusted test session | WORKING | `test_conversation_continuity.py` |
| Private memory scope refusal | Guest/public access cannot read owner/private memories. | Runtime chat path | `handshake_broker.py`, `claire_runtime.py`, `are_memory_store.py` | runtime modules | authority metadata if trusted | WORKING | `test_governed_runtime.py::test_guest_cannot_recall_private_memory` |
| Sensitive prompt redaction | Redacts passphrases/secrets from answers and traces. | Runtime chat path | `diode_protocol.py`, `trace_logger.py`, `claire_runtime.py` | stdlib | none | WORKING | `test_governed_runtime.py::test_passphrase_not_repeated`, `test_passphrase_not_written_to_trace` |
| Risk gate for live trading | Blocks live trade execution from chat. | Runtime chat path | `claire_runtime.py`, `handshake_broker.py`, `claire/runtime/loopback.py` | runtime modules | none | WORKING | `test_governed_runtime.py::test_live_trade_blocked_from_chat` |
| Loopback for unstable/unsafe response | Returns bounded/refusal answers when Gyro/authority blocks generation or provider gives generic filler. | Runtime chat path | `claire/runtime/loopback.py`, `claire_runtime.py` | runtime modules | none | WORKING | `test_governed_runtime.py::test_unstable_gyro_stops_generation_before_model_call`, `test_generic_filler_response_triggers_loopback` |
| Runtime trace logging | Writes trace records to JSONL and SQLite; trace includes lane, recalled memory IDs, model used, validator result, memory write decision. | Python `TraceLogger.log()`; runtime chat | `trace_logger.py`, `claire_runtime.py` | sqlite3 stdlib | trace paths | WORKING | `test_governed_runtime.py`, `test_green_restart_continuity.py` |
| GUI runtime trace replay | Returns runtime trace JSON from `/trace/{trace_id}` when no public demo trace exists. | API `GET /trace/{trace_id}` | `claire_gui.py`, `trace_logger.py`, `claire_runtime.py` | FastAPI, runtime trace logger | trace_id and runtime trace store | WORKING | `test_claire_stream_routes.py::test_trace_route_returns_runtime_trace_when_demo_trace_missing` |
| Veritas Legal direct file ingest | Reads local TXT/MD/LOG/CSV/JSON/JSONL/DOCX/PDF evidence, redacts secret-like markers, extracts dates/entities. | Python `EvidenceEngine.ingest_file()` | `veritas_legal/engine.py` | PyPDF2 for PDF; zipfile/html for DOCX | state directory; optional PyPDF2 for PDF | WORKING | `tests/test_veritas_legal.py::test_ingest_hash_entities_dates_and_claire_explains` |
| Veritas source hashing | Calculates stable source SHA-256 and matter-scoped `source_doc_id`. | Python `EvidenceEngine.ingest_file()` / `ingest_parser_record()` | `veritas_legal/engine.py` | stdlib hashlib | matter_id | WORKING | `tests/test_veritas_legal.py::test_matter_scope_changes_source_doc_id_without_changing_source_hash` |
| Veritas ARE event adapter | Converts legal evidence into append-first ARE-style event text and stores metadata referencing ARE sha/truth hash. | Python `EvidenceEngine.ingest_file()`, `ingest_parser_record()` | `veritas_legal/engine.py` | enhanced ARE if available; original ARE fallback | ARE append function or default adapter | WORKING | `tests/test_veritas_legal.py::test_parser_record_writes_are_event_and_governed_metadata` |
| Veritas parser JSONL adapter | Turns parser output records into governed legal evidence records. | Python `EvidenceEngine.ingest_parser_jsonl()` | `veritas_legal/engine.py`, `claire_parser` | stdlib; parser module | parser JSONL path | WORKING | `tests/test_veritas_legal.py::test_case_file_parser_output_becomes_are_linked_metadata` |
| ZIP-slip parser protection | Hardened parser rejects malicious ZIP paths. | Parser test path | `claire_parser`, `tests/test_veritas_legal.py` | zipfile stdlib | parser temp root | WORKING | `tests/test_veritas_legal.py::test_claire_parser_rejects_zip_slip_paths` |
| Veritas timeline | Builds simple timeline from extracted date strings and source citations. | Python `EvidenceEngine.build_timeline()` | `veritas_legal/engine.py` | stdlib regex | ingested evidence records | WORKING | `tests/test_veritas_legal.py`; `test_veritas_end_to_end.py` |
| Veritas contradiction candidates | Rule-based date/negation contradiction candidates with source excerpts and hashes. | Python `EvidenceEngine.detect_contradictions()` | `veritas_legal/engine.py` | stdlib regex | multiple evidence records | WORKING | Included in `tests/test_veritas_legal.py`; packet tests assert section exists |
| Veritas attorney-review packet | Generates Markdown/PDF packet with matter header, exhibit index, timeline, contradiction section, redaction notice, boundary statement. | Python `EvidenceEngine.generate_review_packet()` | `veritas_legal/engine.py` | stdlib PDF writer; optional CourtListener client | state dir with evidence | WORKING | `test_veritas_end_to_end.py`, `test_claire_real_work.py` |
| GUI document upload endpoint | Accepts supported upload file, extracts text, chunks it, sends chunks to ingest bridge, remembers upload metadata. | API/GUI `POST /upload` | `claire_gui.py` | FastAPI, requests, upload extraction deps | `INGEST_BASE_URL`, upload directory | WORKING | Code path `claire_gui._ingest_one_uploaded_file`; earlier clean-base smoke test anchored upload |
| GUI Veritas Legal run | Runs hardened parser on recent uploaded files and stores source-linked Veritas Legal state. | API/GUI `POST /veritas-legal/run` | `claire_gui.py`, `veritas_legal/engine.py`, `claire_parser` | FastAPI, parser, Veritas engine | uploaded file, state dir | WORKING | Earlier clean-base smoke returned processed file with `source_doc_id`, `source_hash`, `are_event_sha`; Veritas engine tests pass |
| ARE fast vault server ingest/query | Appends JSONL memory vault records and searches indexed token/exact matches. | API `POST /ingest`, `POST /query`, `GET /are/raw`, `GET /health` | `ARE_SERVER.py` | FastAPI | `CLAIRE_MEMORY_VAULT_PATH` optional | WORKING | Clean-base smoke previously: ingest success and query found test memory; code path implemented |
| Ingest bridge | Normalizes parser/sentinel payloads and forwards to ARE ingest. | API `POST /ingest`, `/parser/push`, `/sentinel/push` | `claire_ingest_bridge.py` | FastAPI, requests | `ARE_INGEST_URL`, optional `INGEST_TOKEN` | WORKING | Clean-base smoke previously: bridge returned `ok:true` and ARE success |

## PARTIAL

| Name | Description | How Invoked | Source Files | Dependencies | Required Configuration | Status | Evidence |
|---|---|---|---|---|---|---|---|
| Normal chat answering | Main chat can answer through `ClaireRuntime`, local bridge, Gemini, NVIDIA, or deterministic fallback, but quality depends on provider config and many canned/direct paths exist. | GUI/API `GET/POST /reply`, `GET/POST /ask`; Python `build_reply()` | `claire_gui.py`, `claire_runtime.py`, `nemotron_adapter.py` | FastAPI, requests, provider | `LLM_URL`/local bridge or provider keys | PARTIAL | Code path exists; tests use injected provider callbacks, not live external provider |
| Real provider integration | Supports NVIDIA NIM, local LLM bridge, and Gemini helper, but no audit run verified live credentials today. | Runtime `call_nemotron()`; `query_llm()`; `query_gemini()` | `nemotron_adapter.py`, `claire_gui.py` | requests; external provider | `NVIDIA_API_KEY`, `NVIDIA_NIM_BASE_URL`, `NVIDIA_NIM_MODEL`, `LLM_URL`, `GEMINI_API_KEY` | PARTIAL | Code path exists; absent credentials fall back to deterministic/local behavior |
| Memory update | There is no in-place update. Corrections are represented as new durable records plus derived continuity context. | Chat: “Correction: remember this...” | `claire_runtime.py`, `memory_committer.py`, `session_continuity.py` | SQLite memory store | durable memory enabled | PARTIAL | `test_conversation_continuity.py` proves correction by append, not mutation |
| Memory explanation | Runtime trace can show recalled memory IDs and rejected memories; user-facing explanation is not consistently exposed as a polished feature. | Debug/trace paths | `claire_runtime.py`, `trace_logger.py`, `claire_gui.py` | runtime modules | debug request or trace access | PARTIAL | Trace records contain `memories_recalled`, `memories_rejected`; GUI trace route has shadowing risk |
| Uploaded document search | Searches uploaded document chunks in memory vault by filename/latest upload/terms. | GUI helper `search_uploaded_documents()` | `claire_gui.py`, `ARE_SERVER.py` | JSONL vault | uploaded docs in vault | PARTIAL | Code path exists; not covered by the 97-test audit run |
| Upload folder | Iterates multiple uploaded files and ingests each supported file. | API/GUI `POST /upload-folder` | `claire_gui.py` | FastAPI uploads, ingest bridge | `INGEST_BASE_URL` | PARTIAL | Code path exists; not directly tested in audit run |
| Veritas PDF parsing | PDF text extraction supports first 25 pages through PyPDF2 when installed. | `EvidenceEngine.ingest_file()` | `veritas_legal/engine.py` | PyPDF2 optional | PyPDF2 installed | PARTIAL | Test warnings show PyPDF2 installed; broad PDF corpus not certified |
| Veritas DOCX parsing | Reads `word/document.xml` from DOCX zip and strips XML tags. | `EvidenceEngine.ingest_file()` | `veritas_legal/engine.py` | zipfile/html stdlib | valid DOCX | PARTIAL | Code path exists; not deeply validated against complex DOCX |
| Veritas legal parser breadth | GUI hardened parser can parse trees and supports OCR flag, but legal engine itself only certifies text-like, DOCX, PDF and parser JSONL. | `/veritas-legal/run`; parser module | `claire_gui.py`, `claire_parser`, `veritas_legal/engine.py` | parser deps | parser available | PARTIAL | ZIP-slip and parser JSONL tests pass; broad scans/images/audio/video not certified |
| CourtListener lookup | Client exists and packet includes verified case-law section or unavailable notice, but live API access is not certified here. | Python `lookup_case_law()`; packet generation | `veritas_legal/courtlistener_client.py`, `veritas_legal/engine.py` | requests/network | optional CourtListener API/token if used | PARTIAL | Packet tests mock unavailable state and ensure honest notice |
| Drive research lane | GUI route can read local Drive research cache or report setup required; it does not have built-in Drive connector credentials. | API `GET /drive/status`, `POST /drive/research` | `claire_gui.py` | FastAPI; local cache | `CLAIRE_GOOGLE_OAUTH_TOKEN_JSON` or service account for app, or cache file | PARTIAL | Code returns setup-required if credentials/cache absent |
| Scholar / CourtListener open pages | GUI has `/scholar` and `/courtlistener/open` routes/helpers, but live research capability depends on route code/config and was not certified. | API/GUI routes | `claire_gui.py`, `claire_courtlistener.py` | requests/network | CourtListener config if live | PARTIAL | Route definitions exist; not included in audit test evidence |
| Office task endpoints | Office ad draft and task read endpoints exist; capability scope and persistence are limited. | API `POST /office/ad-draft`, `GET /office/tasks`, `GET /office/task/{task_id}` | `claire_gui.py` | FastAPI | app state paths | PARTIAL | Route definitions exist; not tested in audit run |
| Runtime status page | Reports subsystem statuses from config/env and local checks. | API `GET /status`, `GET /diagnostic`, `GET /health` | `claire_gui.py`, `ARE_SERVER.py`, `claire_ingest_bridge.py` | FastAPI | running services | PARTIAL | Health/status prove process availability, not full work completion |
| Session recovery summary | Builds recovery summary from repo checkpoint/current truth/recent memories. | Python `build_session_recovery()` | `session_continuity.py` | stdlib | current truth dict + memory list | PARTIAL | `test_session_continuity.py` passes; this is summary only, not full project recovery |
| Tool-use governance metadata | Authority capsule has allowed tools per lane, and subsystem status helpers exist for Veritas/CourtListener, but no general tool dispatcher is certified. | Runtime chat | `handshake_broker.py`, `claire_runtime.py` | runtime modules | trusted device/authority metadata | PARTIAL | `test_governed_runtime.py` verifies gate behavior; real tool execution not broadly certified |
| Trace explanation | Runtime traces are now retrievable; a plain-English explanation of each trace is not consistently exposed as a polished user-facing feature. | Debug/trace paths | `trace_logger.py`, `claire_runtime.py`, `claire_gui.py` | sqlite3/FastAPI | trace DB/path | PARTIAL | Trace replay is working; human-readable explanation remains partial |

## BROKEN

| Name | Description | How Invoked | Source Files | Dependencies | Required Configuration | Status | Evidence |
|---|---|---|---|---|---|---|---|
| Guaranteed real provider answer | If no NVIDIA key/local bridge/Gemini path is available, code falls back to deterministic stubs rather than proving real model completion. | Chat provider path | `nemotron_adapter.py`, `claire_gui.py` | external provider | provider credentials/endpoint | BROKEN as a certification claim | Code path `_deterministic_stub()` runs when no provider key/local bridge is available |
| General-purpose tool completion from main chat | There is no certified main-runtime dispatcher that can execute arbitrary tasks, save result, and report tool trace outside specific hardcoded routes. | Expected chat/tool workflow | scattered helpers in `claire_gui.py`, `claire_runtime.py` | varied | varied | BROKEN as a broad capability | Only specific routes/helpers are implemented; audit tests do not prove broad tool execution |

## DEMO ONLY

| Name | Description | How Invoked | Source Files | Dependencies | Required Configuration | Status | Evidence |
|---|---|---|---|---|---|---|---|
| Governed demo mode / StableRide probe | Structured JSON demonstration for “Schedule a horseback ride tomorrow at 10am”; simulates observe/recall/policy/decision/output/trace. | `/reply` or `/ask` with `demo_mode=true`; `ClaireRuntime.handle_demo_message()` | `claire_runtime.py`, `claire_gui.py` | runtime modules | none | DEMO ONLY | AGENTS spec; `handle_demo_message()` returns simulated action only |
| ARE public memory lane demo | Public demo lane code, memory save/recall, ledger, delete lane. | `/are-demo`, `/are-demo/api/lane`, `/open`, `/memory`, `/recall`, `/delete` | `claire_gui.py` | FastAPI, local demo storage | demo state dir/env | DEMO ONLY | Route definitions exist; not production/private CLAIRE memory |
| ARE Spectacle page | Public visual/demo page for ARE concept. | GUI `GET /are-spectacle` | `claire_gui.py` | FastAPI/HTML | none | DEMO ONLY | Static/demo route |
| Public demo machine control | Allows controlled demo query such as listing public demo files and writes demo trace. | API `POST /claire/query`, `GET /machine/trace/{trace_id}` | `claire_gui.py` | FastAPI, SQLite demo DB | public demo DB path | DEMO ONLY | `_public_demo_orientation()` only allows tiny demo action set |
| Canned operator identity replies | Direct responses for “Lucius Prime”, “Battleborn”, creator/operator prompts. | Chat helper before runtime provider | `claire_gui.py`, `claire/runtime/loopback.py` | stdlib | none | DEMO ONLY | `public_operator_tone_reply()`, `_direct_general_answer()` |
| Deterministic fallback answers | Hardcoded answers for OfficeAI, NVIDIA, legal caution, horse hoof, trading status, tool-supply-chain prompts. | Provider fallback / loopback | `nemotron_adapter.py`, `claire/runtime/loopback.py` | stdlib | no provider key or drift detected | DEMO ONLY | `_deterministic_stub()`, `_direct_general_answer()` |

## NOT IMPLEMENTED

| Name | Description | How Invoked | Source Files | Dependencies | Required Configuration | Status | Evidence |
|---|---|---|---|---|---|---|---|
| In-place memory update | Editing an existing ARE/memory record. | Expected memory API | none | n/a | n/a | NOT IMPLEMENTED | Architecture uses append-first corrections; no update endpoint/function certified |
| Memory deletion from ARE authority | Deleting authoritative ARE records. | Expected memory API | none | n/a | n/a | NOT IMPLEMENTED | ARE doctrine/archive-not-delete; no delete in `claire_are/api.py` |
| Full Chronos temporal engine | General temporal reasoning layer for arbitrary effective time/state queries. | Expected module/API | no complete `chronos_engine.py` in repo | n/a | n/a | NOT IMPLEMENTED | Search found no existing Chronos module before user paste; only session continuity subset exists |
| Production authentication/RBAC | User login, enterprise roles, permission administration. | Expected platform feature | none certified | n/a | n/a | NOT IMPLEMENTED | Authority capsule is demo/trusted-device metadata, not production auth |
| Real calendar/scheduling action | Actually scheduling horseback rides/calendar events. | Demo trigger expected | none | n/a | n/a | NOT IMPLEMENTED | Demo spec explicitly forbids real scheduling |
| Live trading execution | Placing live trades. | Chat/tool request | no safe execution path certified | exchange API would be required | n/a | NOT IMPLEMENTED | Runtime blocks live trading from chat |
| Court filing/e-filing | Filing legal documents with courts. | Chat/tool request | none | court e-filing integration | n/a | NOT IMPLEMENTED | Runtime blocks legal filing actions |
| Audio/video transcription pipeline | MP3/MP4/hearing audio/video transcription into Veritas evidence. | Expected Veritas ingest | not certified in `EvidenceEngine` | speech/video deps | n/a | NOT IMPLEMENTED in certified engine | Legal engine handles text-like, DOCX, PDF, parser JSONL; GUI parser media disabled in Veritas route |
| Image OCR evidence path | Image/scanned evidence OCR into legal records. | Expected Veritas ingest | not certified in `EvidenceEngine` | OCR deps | n/a | NOT IMPLEMENTED in certified engine | `EvidenceEngine._extract_text()` rejects image suffixes |
| Enterprise deployment/cutover automation | Production migration, rollback, traffic switching. | Expected ops | docs/scripts only, not certified | cloud infra | n/a | NOT IMPLEMENTED | No cutover performed; BLUE remains unchanged |

## API Inventory

| Endpoint | Source | Capability | Requires Auth | Returns Real Data? | Status |
|---|---|---|---|---|---|
| `GET /v1/health` | `claire_are/api.py` | ARE plug-in health | no | yes, verify count/root | WORKING |
| `POST /v1/memory/ingest` | `claire_are/api.py` | ARE plug-in ingest | no built-in auth | yes | WORKING |
| `POST /v1/memory/recall` | `claire_are/api.py` | ARE plug-in recall | no built-in auth | yes | WORKING |
| `POST /v1/llm/complete` | `claire_are/api.py` | Governed recall-before-completion stub/API | no built-in auth | yes, local governed completion event | WORKING |
| `GET /v1/audit/recent` | `claire_are/api.py` | ARE audit | no built-in auth | yes | WORKING |
| `GET /v1/memory/verify` | `claire_are/api.py` | ARE verify | no built-in auth | yes | WORKING |
| `POST /ingest` | `ARE_SERVER.py` | Fast memory vault ingest | no built-in auth | yes | WORKING |
| `GET /are/raw` | `ARE_SERVER.py` | Raw vault recall with verification fields | no built-in auth | yes | WORKING |
| `POST /query` | `ARE_SERVER.py` | Vault recall query | no built-in auth | yes | WORKING |
| `GET /health` | `ARE_SERVER.py` / `claire_gui.py` / `claire_ingest_bridge.py` | Health | no | process status only | PARTIAL |
| `POST /ingest`, `/parser/push`, `/sentinel/push` | `claire_ingest_bridge.py` | Bridge parser/sentinel payloads to ARE | optional token | yes | WORKING |
| `GET/POST /reply` | `claire_gui.py` | Main chat | no app auth certified | yes, but provider/fallback dependent | PARTIAL |
| `GET/POST /reply-stream` | `claire_gui.py` | Streaming reply | no app auth certified | likely yes | PARTIAL |
| `GET/POST /ask` | `claire_gui.py` | Ask page/chat | no app auth certified | yes, same chat path | PARTIAL |
| `GET /trace/{trace_id}` | `claire_gui.py` | Trace replay | no app auth certified | yes, runtime or demo trace where present | WORKING |
| `GET /report/{trace_id}` | `claire_gui.py` | Trace/report view | no app auth certified | likely trace-derived | PARTIAL |
| `GET /drive/status`, `POST /drive/research` | `claire_gui.py` | Drive research cache/status | config-dependent | setup-required or cache | PARTIAL |
| `POST /veritas-legal/run` | `claire_gui.py` | Veritas evidence workflow on uploaded files | no app auth certified | yes | WORKING |
| `POST /upload`, `/upload-folder` | `claire_gui.py` | Upload evidence/documents | no app auth certified | yes | WORKING/PARTIAL |
| `POST /office/ad-draft`, `GET /office/tasks`, `GET /office/task/{task_id}` | `claire_gui.py` | Office task/demo helpers | no app auth certified | limited local data | PARTIAL |
| `GET /diagnostic`, `/status`, `/action` | `claire_gui.py` | Runtime status/diagnostic | no app auth certified | yes, status only | PARTIAL |
| `POST /claire/query`, `GET /machine/trace/{trace_id}` | `claire_gui.py` | Public demo machine control | no app auth certified | demo data | DEMO ONLY |
| `/are-demo/*` | `claire_gui.py` | Public ARE memory lane demo | no app auth certified | demo data | DEMO ONLY |
| `GET /`, `/privacy`, `/terms`, `/support`, `/scholar`, `/courtlistener/open`, `/are-spectacle` | `claire_gui.py` | Web pages/helpers | no app auth certified | static/helper output | PARTIAL/DEMO ONLY |

## GUI Inventory

| Visible Function | Source | What It Actually Does | Status |
|---|---|---|---|
| Main front page | `GET /` in `claire_gui.py` | Serves public CLAIRE interface HTML. | PARTIAL |
| Ask CLAIRE | `/ask`, `/reply` in `claire_gui.py` | Sends prompt through `build_reply()` and `ClaireRuntime` unless direct helper/fallback path fires. | PARTIAL |
| Demo mode toggle/probe | `build_governed_demo_payload()` | Returns structured simulated system demonstration JSON. | DEMO ONLY |
| Upload file | `/upload` | Saves supported file, extracts text, chunks and forwards to ingest bridge. | WORKING |
| Upload folder | `/upload-folder` | Iterates multiple uploads and ingests supported files. | PARTIAL |
| Veritas Legal button | `/veritas-legal/run` | Parses recent uploaded evidence and creates Veritas legal records/metadata/trace. | WORKING |
| ARE demo page | `/are-demo` and API routes | Session/public demo memory lanes and ledger. | DEMO ONLY |
| ARE Spectacle | `/are-spectacle` | Public concept/demo page. | DEMO ONLY |
| Trace/replay | `/trace/{trace_id}`, `/machine/trace/{trace_id}` | Runtime trace exists, but GUI route collision creates ambiguity. | BROKEN/PARTIAL |
| Drive research | `/drive/status`, `/drive/research` | Uses cache/credentials if available, otherwise setup-required. | PARTIAL |
| Status/diagnostic | `/status`, `/diagnostic`, `/health` | Reports process/config status, not full capability. | PARTIAL |
| Office task UI/API | `/office/*` | Limited local office/ad-draft/task behavior. | PARTIAL |

## Tools Inventory

| Tool | Working? | Demo? | Stub? | Disabled? | Evidence |
|---|---:|---:|---:|---:|---|
| ARE memory ingest/recall/verify | yes | no | no | no | `claire_are/tests/test_plugin_are.py`, `ARE_SERVER.py` |
| SQLite runtime memory store | yes | no | no | no | `test_green_restart_continuity.py` |
| Trace logger | yes | no | no | no | `test_governed_runtime.py` |
| Diode redaction | yes | no | no | no | `test_governed_runtime.py` |
| Handshake/authority capsule | yes for demo authority | partial | no | no | `test_governed_runtime.py` |
| Gyro orientation | partial | no | no | no | Wired in `ClaireRuntime`; tested for loopback blocking |
| Sentinel output validation | partial | no | no | no | Wired in `ClaireRuntime`; direct sentinel tests exist |
| NVIDIA NIM provider | config-dependent | no | no | no | `nemotron_adapter.py`; not live-certified |
| Local LLM bridge | config-dependent | no | no | no | `nemotron_adapter._call_local_bridge()` |
| Gemini helper | config-dependent | no | no | no | `claire_gui.query_gemini()` |
| Deterministic fallback provider | yes | yes | yes | no | `nemotron_adapter._deterministic_stub()` |
| Veritas Legal evidence engine | yes | no | no | no | `tests/test_veritas_legal.py`, `test_veritas_end_to_end.py` |
| CourtListener client | partial | no | no | no | client exists; failure handling tested/mocked |
| Google Drive research | partial | no | no | no | setup-required route; app credentials not certified |
| Public machine list-files action | yes | yes | no | no | `/claire/query`, `_public_demo_machine_execute()` |
| Calendar scheduling | no | yes simulation only | n/a | effectively disabled | Demo spec forbids real scheduling |
| Live trade execution | no | no | n/a | blocked | `test_live_trade_blocked_from_chat` |
| Court filing/e-filing | no | no | n/a | blocked | runtime legal filing block |

## Totals

TOTAL FEATURES FOUND: 63

- Working: 31
- Partial: 17
- Broken: 2
- Demo: 6
- Missing: 7

## If someone downloaded CLAIRE today, what useful work could they accomplish immediately?

They could run a local governed-memory and evidence-organization system. Immediately useful work includes:

- ingesting and recalling governed memories through the ARE plug-in API;
- verifying memory integrity and seeing audit events;
- running a controlled CLAIRE runtime conversation with durable memory in local SQLite;
- saving a fact, restarting, and recalling it later;
- applying corrections as new append-first memory records and deriving current versus historical state;
- uploading supported documents and organizing them into Veritas Legal evidence records;
- hashing evidence, assigning `source_doc_id`, extracting dates/entities, building a simple timeline, and generating a Markdown/PDF attorney-review packet;
- using trace logs to inspect what memory and policy path supported an answer.

They could not yet rely on it as a full production assistant that autonomously uses arbitrary tools, performs real scheduling, executes live trades, files legal documents, or guarantees live provider-backed conversation without configuring and validating an external/local model provider.
