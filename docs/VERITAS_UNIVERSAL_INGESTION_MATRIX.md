# Veritas Universal Ingestion Matrix

Audit date: 2026-07-12

This matrix records what the current code actually supports, what is partial, and what is still missing.

## Current parser support

| Input type | Current implementation | Status | Notes |
|---|---|---|---|
| TXT / MD / LOG / PY / HTML / XML / CSV / JSON / JSONL / RTF / INI / CFG / TOML | `claire_parser.read_text_file()` + `ClaireParser.parse_path()` | REAL_AND_WORKING | Native text extraction exists |
| PDF | `extract_pdf_text_native()`, OCR fallback via `extract_pdf_with_ocr()` | REAL_AND_WORKING in parser code | Live GUI usage depends on route-specific config |
| DOCX | `extract_docx_text()` | REAL_AND_WORKING | Reads paragraphs and tables |
| ODT | `extract_odt_text()` | REAL_AND_WORKING | Optional `odfpy` dependency |
| PNG / JPG / JPEG / WEBP / BMP / TIFF / TIF | `ocr_image()` | REAL_AND_WORKING in parser code | Requires Tesseract/Pillow |
| MP3 / WAV / M4A / FLAC / OGG | `WhisperTranscriber.transcribe()` | REAL_AND_WORKING in parser code | Optional Whisper backend |
| MP4 / MOV / MKV / AVI / WEBM | `extract_audio_from_video()` + transcribe | REAL_AND_WORKING in parser code | Uses ffmpeg |
| ZIP | `safe_extract_zip()` + recursive parse | REAL_AND_WORKING | ZIP-slip protection exists |
| Nested folders | `ClaireParser.parse_tree()` | REAL_AND_WORKING | Recurses safely and skips excluded dirs |

## Ingestion modes

| Mode | Current implementation | Status | Notes |
|---|---|---|---|
| Single file | `ClaireParser.parse_path()` | REAL_AND_WORKING | Chunked JSONL output |
| Multiple files | `ClaireParser.parse_tree()` | REAL_AND_WORKING | Recursive |
| Entire folder | `ClaireParser.parse_tree()` | REAL_AND_WORKING | Recursive |
| ZIP archive | `ClaireParser.parse_zip()` | REAL_AND_WORKING | Safe extraction |
| Mixed evidence collection | parser + EvidenceEngine | PARTIAL | Works for supported types only |
| Resumable large import | not found as a full managed session flow | NOT_IMPLEMENTED | No durable resumable import manifest found as a product surface |
| 10 GB matter import | not certified | NOT_IMPLEMENTED | No verified chunked server-side session architecture yet |

## Legal workspace support

| Legal artifact | Existing codepath | Status | Notes |
|---|---|---|---|
| Matter profile | `web/services/legal_intel.py`, `WorkspaceStore.matter_profile()` | REAL_AND_WORKING | Court profile + templates + docket summary |
| Docket import | `web/app.py:/docket/import`, `web/services/dockets.py` | REAL_AND_WORKING | Converts docket payloads into matter state |
| Timeline | `EvidenceEngine.build_timeline()`, `WorkspaceStore.timeline()` | REAL_AND_WORKING / PARTIAL depending path | Simple timeline from extracted dates |
| Contradictions | `EvidenceEngine.detect_contradictions()` | REAL_AND_WORKING | Rule-based candidate contradictions |
| Search | `WorkspaceStore.search()` | REAL_AND_WORKING | Token/priority/temporal weighted search |
| CourtListener research | `VeritasCourtListener`, `/courtlistener/*` | REAL_AND_WORKING | Governed bridge to public research |
| Draft packet | `EvidenceEngine.generate_review_packet()` | REAL_AND_WORKING | Markdown/PDF/DOCX in supported paths |
| Exhibit index | `build_exhibit_index()` | REAL_AND_WORKING | Source-linked |
| Evidence packet export | `packet_to_markdown()`, `packet_to_docx_bytes()`, `packet_to_pdf_bytes()` | REAL_AND_WORKING | DOCX/PDF require optional deps |

## Missing or incomplete as a single product surface

- Resumable upload sessions with restart recovery
- Object-storage/raw-media tier for large imports
- Unified matter lifecycle and PACER-style docket model
- Persistent firm profile and staff directory
- Explicit prepared/reviewed/approved/signed/filed authority fields
- A single canonical ingestion pipeline for every supported file type through the live GUI

## Decision

The parser is broader than the legal engine, and the legal engine is broader than the mobile replacement. The missing step is not to invent new parsing logic from scratch. The missing step is to wire the existing parser, evidence engine, and legal workspace into one authoritative, dark, governed product surface.
