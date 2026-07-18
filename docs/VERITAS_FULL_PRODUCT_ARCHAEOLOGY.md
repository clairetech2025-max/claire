# Veritas Full Product Archaeology

Audit date: 2026-07-12

Scope: inventory of every Veritas implementation I found across the main Claire repo, the standalone `claire-veritas-legal` repo, and the live host routes. This document separates the approved dark legal workstation from the reduced mobile replacement and from dormant or partial code.

## Live surfaces

| Surface | Path / route | Process | Role | Status |
|---|---|---|---|---|
| Dark Claire GUI | `http://127.0.0.1:8000/` | `claire-gui.service` -> `uvicorn claire_gui:app` | Approved product foundation | REAL_AND_WORKING |
| Standalone dark Veritas shell | `http://127.0.0.1:8020/veritas-legacy/` | `uvicorn web.app:app` | Old dark shell, still live | REAL_AND_WORKING |
| Mobile replacement | `http://127.0.0.1:8011/veritas-mobile` | `claire-veritas-mobile.service` -> `uvicorn claire_gui:app` | Reduced replacement path | REAL_BUT_NOT_WIRED |
| Public phone URL | `https://clairesystems.ai/veritas` | nginx -> `/veritas-mobile` | Phone-facing alias, currently points at mobile replacement | DUPLICATED |
| Public dark root | `https://clairesystems.ai/` | nginx -> `127.0.0.1:8000` | Current public root for dark GUI | REAL_AND_WORKING |

## Capability matrix

| Capability | Existing file/class/route | Status | Tests | Live path | Decision |
|---|---|---|---|---|---|
| CLAIRE dark legal workspace | `claire_gui.py`, `/` | REAL_AND_WORKING | `test_claire_stream_routes.py`, `test_governed_runtime.py`, `test_veritas_legal.py` | `http://127.0.0.1:8000/` | Preserve as product foundation |
| Matter/workspace model | `web/services/workspace.py` (`WorkspaceStore`) | REAL_AND_WORKING | `tests/test_veritas_claire_runtime.py`, `tests/test_veritas_court_listener.py` | dark GUI + standalone repo | Keep |
| Evidence ingest + OCR parser | `claire_parser`, `ClaireParser.parse_tree()`, `ocr_image()`, `extract_pdf_with_ocr()` | REAL_AND_WORKING | `tests/test_veritas_legal.py::test_claire_parser_rejects_zip_slip_paths` and parser tests | local parser CLI / GUI ingest path | Keep |
| Audio transcription | `claire_parser.WhisperTranscriber`, `parse_path()` audio branch | REAL_AND_WORKING in parser code, not live-certified in GUI | parser code exists; no live acceptance in this pass | parser CLI only | Keep but certify separately |
| Video transcription | `claire_parser.extract_audio_from_video()` and video branch | REAL_AND_WORKING in parser code, not live-certified in GUI | parser code exists; no live acceptance in this pass | parser CLI only | Keep but certify separately |
| Folder / archive ingestion | `ClaireParser.parse_tree()`, `parse_zip()`, `safe_extract_zip()` | REAL_AND_WORKING | `tests/test_veritas_legal.py::test_claire_parser_rejects_zip_slip_paths` | parser CLI / GUI upload helper | Keep |
| CourtListener bridge | `claire_courtlistener.py`, `veritas_court_listener.py`, `/courtlistener/*` | REAL_AND_WORKING | `tests/test_veritas_court_listener.py`, `tests/test_courtlistener_client.py` | `http://127.0.0.1:8000/courtlistener/*` | Keep |
| Legal matter profile | `web/services/legal_intel.py` (`default_matter`, `court_profile_report`) | REAL_AND_WORKING | `tests/test_veritas_claire_runtime.py` | dark GUI matter views | Keep |
| Filing templates | `web/services/legal_intel.py` (`FILING_TEMPLATES`) | REAL_AND_WORKING | exercised by packet tests | dark GUI drafting/export | Keep |
| DOCX/PDF packet production | `packet_to_docx_bytes()`, `packet_to_pdf_bytes()` | REAL_AND_WORKING | `test_veritas_end_to_end.py`, `test_claire_real_work.py` | `/export_packet_docx`, `/export_packet_pdf` | Keep |
| Timeline / contradiction / exhibit index | `EvidenceEngine.build_timeline()`, `detect_contradictions()`, `build_exhibit_index()` | REAL_AND_WORKING | `tests/test_veritas_legal.py`, `test_veritas_end_to_end.py` | standalone repo and mobile backend | Keep |
| Source-linked ARE metadata | `EvidenceEngine.ingest_file()`, `ingest_parser_record()` | REAL_AND_WORKING | `tests/test_veritas_legal.py` | standalone repo / parser CLI | Keep |
| Mobile case flow | `/veritas-mobile`, `/veritas-mobile/api/cases/*` | REAL_AND_WORKING for the reduced mobile slice | `test_veritas_mobile_ui.py` | `http://127.0.0.1:8011/veritas-mobile` | Do not replace the dark product with it |
| Mobile OCR/photo/camera workflow | mobile UI + upload path | PARTIAL / NOT CERTIFIED | mobile tests explicitly exclude OCR/photo capture | mobile route only | Do not overclaim |
| Role-based permissions / firm profile | persistent staff directory and firm profile features are not found as a coherent implemented product surface | NOT_IMPLEMENTED | no certified tests found | none | Needs implementation |
| PACER-style docket organizer | matter, docket import scaffolding, court profiles exist | PARTIAL | `tests/test_veritas_claire_runtime.py`, `web/services/dockets.py` | dark GUI | Recover and complete |
| Court filing / e-filing | explicit filing automation is absent | NOT_IMPLEMENTED | none | none | Do not claim |
| Universal evidence ingestion up to 10 GB | parser can recurse folders and archives, but resumable 10 GB sessions and object-storage raw media handling are not certified | PARTIAL | parser tests only | parser CLI / upload helper | Needs architecture work |
| CLAIRE typed front door | guided chat / workflow routing exists in runtime, but not as the required exact demo contract | PARTIAL | `test_governed_runtime.py`, `test_veritas_claire_runtime.py` | main CLAIRE runtime | Recover as front door |
| Replayable trace | `veritas_source_trace.py`, runtime traces, `/trace/{trace_id}` | REAL_AND_WORKING | `test_claire_stream_routes.py`, runtime tests | dark GUI / standalone repo | Keep |

## Decision notes

- The approved visual foundation is the dark CLAIRE // VERITAS workspace in the main Claire repo and the standalone dark shell in `claire-veritas-legal`.
- The `/veritas-mobile` interface is a separate reduced replacement path. It is real, but it should not become the product foundation.
- The parser and legal engine already provide a meaningful ingestion pipeline for text, PDF, DOCX, folder recursion, ZIP safety, timelines, contradictions, and packet production.
- Audio/video, resumable large imports, firm/staff authority, and a full PACER-style matter model are only partially present or missing as a coherent product surface.

## Current verdict

The full Veritas product exists as a set of real but uneven components. The dark legal workstation is the approved base. The mobile interface duplicates some workflows in a reduced form. The next step is to preserve the dark product, recover the working ingestion/legal components, and then complete the missing matter, authority, and production layers without replacing the approved UI.
