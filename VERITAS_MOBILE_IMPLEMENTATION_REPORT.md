# Veritas Mobile Implementation Report

## Mission

Implemented a mobile-first Veritas interface for a modern Android phone. The workflow is designed around a first-time user creating a case, uploading evidence, seeing extracted facts, searching, asking a case-scoped question, and generating a basic report without using a terminal or developer tools.

Azure BLUE was not stopped, redirected, deleted, cleaned, or modified as a deployment target.

## Files Changed

- `claire_gui.py`
  - Added `/veritas-mobile` mobile web interface.
  - Added mobile case state helpers under `VERITAS_MOBILE_STATE_DIR`.
  - Added case-scoped JSON APIs for cases, upload, documents, search, timeline, Ask Veritas, and reports.
  - Wired upload into the existing Claire parser and `veritas_legal.EvidenceEngine`.
  - Kept hashes, source IDs, ARE references, and parser details hidden behind "Show Technical Details".
- `test_veritas_mobile_ui.py`
  - Added repeatable FastAPI tests for the first-time mobile workflow and backend support boundaries.
- `VERITAS_MOBILE_IMPLEMENTATION_REPORT.md`
- `VERITAS_MOBILE_BACKEND_SUPPORT_MATRIX.md`
- `VERITAS_MOBILE_TEST_RESULTS.md`
- `VERITAS_STEVE_ACCEPTANCE_TEST.md`

## Implemented Mobile Screens

- Home
  - New Case
  - Open Case
  - Upload Evidence
  - Search Evidence
  - Build Timeline
  - Generate Report
  - Ask Veritas
  - Recent Cases
- Bottom Navigation
  - Home
  - Case
  - Search
  - Ask
  - Reports
- Case Dashboard
  - Upload Evidence
  - Ask Veritas
  - Documents
  - People
  - Timeline
  - Search
  - Reports
  - Recent Activity
  - Plain-language "What changed?" summary
- Document Upload
  - Supported types only: TXT, MD, PY, PDF, DOCX, CSV, JSON, JSONL
  - Per-file status
  - Unsupported-file errors
  - No-text-found errors
- Document View
  - Title
  - Summary
  - Dates
  - People
  - Organizations
  - Rules / statutes
  - Ask about this document
  - Add to Report
  - Technical details hidden by default
- Search
  - Natural-language query box
  - Suggested prompts
  - Source-linked snippets
- Timeline
  - Build / refresh timeline
  - Chronological events
  - Source document link per event
- Ask Veritas
  - Case-scoped question interface
  - Suggested prompts
  - Source-backed answers when evidence exists
  - Legal-advice boundary included
  - Honest blocked message when no evidence exists
- Reports
  - Document Index
  - Timeline
  - Case Summary
  - Evidence Packet
  - Witness List

## Storage

Mobile case state is stored under:

`CLAIRE_RUNTIME_DATA_DIR / "veritas_mobile"`

Each case receives its own directory and its own `EvidenceEngine` state, which prevents cross-case bleed in the mobile interface.

## Real Backend Wiring

The upload flow is:

source file -> existing Claire parser -> parser JSONL -> `EvidenceEngine.ingest_parser_jsonl()` -> evidence record -> source hash/source_doc_id -> ARE event reference -> mobile case summary

Search, timeline, document detail, Ask Veritas, and reports read from the case-specific evidence records created by that flow.

## Not Implemented In This Slice

- Browser folder upload certification.
- Camera/photo upload.
- OCR from phone photos.
- Real provider-backed legal reasoning.
- Full contradiction or missing-evidence product UX beyond existing rule-based backend signals.
- User authentication.
- Enterprise permissions.
- Public deployment or traffic cutover.

## Safety Notes

- No private Steve documents were ingested during implementation.
- Tests use synthetic text evidence only.
- Developer internals are hidden from the normal mobile flow.
- Hashes/source IDs/ARE references are available only under "Show Technical Details".
- The UI does not advertise OCR or photo capture as working.
