# Veritas Mobile Backend Support Matrix

| Mobile Capability | Backend Support | Current Behavior |
|---|---|---|
| Mobile home screen | REAL_AND_WORKING | `/veritas-mobile` serves the Android-first interface with large tap targets and bottom navigation. |
| New Case | REAL_AND_WORKING | `POST /veritas-mobile/api/cases` creates a local case record and isolated case directory. |
| Open Case | REAL_AND_WORKING | `GET /veritas-mobile/api/cases` lists recent cases from the mobile case index. |
| Case Dashboard | REAL_AND_WORKING | `GET /veritas-mobile/api/cases/{case_id}` returns documents, people, organizations, dates, rules, events, reports, and activity from case state. |
| TXT/MD/PY/CSV/JSON/JSONL upload | REAL_AND_WORKING | Upload uses the existing Claire parser, then `EvidenceEngine.ingest_parser_jsonl()`. |
| PDF upload | PARTIAL | Accepted by the parser path when readable text can be extracted. Scanned/image-only PDFs may return no text. |
| DOCX upload | PARTIAL | Accepted by the parser path when text can be extracted from the document. |
| Image/photo upload | NOT_IMPLEMENTED | Not advertised in the mobile UI. Upload returns unsupported type. |
| OCR | NOT_IMPLEMENTED | Mobile upload constructs parser with `enable_ocr=False`. |
| Browser folder upload | BLOCKED | Not certified because browser/device support varies and the backend endpoint currently handles file uploads one at a time. |
| Upload progress | PARTIAL | UI shows uploading/status per file. It does not stream byte-level progress. |
| Per-file status | REAL_AND_WORKING | Each selected file reports added or failed independently in the UI loop. |
| Unsupported-file handling | REAL_AND_WORKING | Unsupported suffixes return a readable 400 response and do not appear successful. |
| No-text-found handling | REAL_AND_WORKING | Parser output with zero records returns a readable 422 response. |
| Source hashing | REAL_AND_WORKING | Evidence records include stable `source_hash`/`source_sha256`. |
| Source document ID | REAL_AND_WORKING | Evidence records include `source_doc_id` derived from matter/source hash. |
| ARE event reference | REAL_AND_WORKING | Evidence records include `are_event_sha` from `EvidenceEngine`. |
| Document detail | REAL_AND_WORKING | `GET /documents/{source_doc_id}` returns title, summary, dates, people, organizations, rules, source hash, source ID, and ARE reference. |
| Technical details hidden | REAL_AND_WORKING | Technical provenance is inside the "Show Technical Details" accordion. |
| Natural-language search | REAL_AND_WORKING | Rule/keyword/date search over case evidence records; not semantic search. |
| Search source links | REAL_AND_WORKING | Search results include `source_doc_id`, snippet, dates, people, rules, and document title. |
| Timeline | REAL_AND_WORKING | Timeline uses `EvidenceEngine.build_timeline()` and includes source document and ARE references. |
| Ask Veritas | PARTIAL | Case-scoped rule-based answering over evidence records. It cites sources and reports uncertainty. It does not call a real LLM provider in this slice. |
| Legal-advice boundary | REAL_AND_WORKING | Ask responses include an attorney-review/legal-advice boundary. |
| Contradiction prompt | PARTIAL | Uses existing rule-based `EvidenceEngine.detect_contradictions()`. It is not advanced legal reasoning. |
| Missing-evidence prompt | PARTIAL | Honest limited response only; no certified missing-evidence detector is presented as working. |
| Document Index report | REAL_AND_WORKING | Saves a Markdown report with source references. |
| Timeline report | REAL_AND_WORKING | Saves a Markdown timeline with source references. |
| Case Summary report | REAL_AND_WORKING | Saves a Markdown case summary with evidence counts. |
| Evidence Packet report | PARTIAL | Calls existing `generate_review_packet()`; includes backend-supported sections. |
| Witness List report | PARTIAL | Builds from extracted person entities only. |
| Saved reports reopenable | REAL_AND_WORKING | Report files are saved under the case `reports/` directory and returned by path in API responses. |
| Private case isolation | REAL_AND_WORKING | Mobile API creates a separate `EvidenceEngine` state directory per case. Test verifies search does not bleed across cases. |
| Demo/canned output prevention | REAL_AND_WORKING | Mobile Ask path does not call the demo-mode scheduler/probe path and tests assert demo phrases are absent. |
| Authentication | NOT_IMPLEMENTED | This slice does not add auth or RBAC. |
| Public deployment | NOT_IMPLEMENTED | No cutover or public routing change was performed. |

## Important Product Boundary

The current mobile product is evidence organization and attorney-review support. It is not a substitute for legal advice and does not claim production legal reasoning, OCR, semantic search, enterprise readiness, or full provider-backed legal analysis.
