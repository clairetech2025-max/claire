# Veritas Product Constitution

This is the product contract for Veritas Legal as it exists in the codebase today and as it should be completed.

## 1. Identity

- `CLAIRE` is the front door.
- `Veritas Legal` is the legal evidence and litigation workstation behind that front door.
- `ARE / Truth Spine` is the authority for durable memory and provenance.
- `CourtListener` is governed external research, not memory authority.
- The approved visual foundation is the dark CLAIRE // VERITAS interface.

## 2. Workflow order

1. User states an objective.
2. CLAIRE classifies intent.
3. CLAIRE chooses allowed lanes.
4. CLAIRE suppresses irrelevant memory and evidence.
5. CLAIRE retrieves supporting evidence only.
6. CLAIRE asks one concise clarifying question when needed.
7. Veritas executes the legal workflow.
8. ARE / Truth Spine records governed evidence and traces.
9. The user can replay the trace.

## 3. Evidence lifecycle

1. Ingest source.
2. Preserve original.
3. Hash original.
4. Extract text.
5. OCR when required and available.
6. Transcribe audio/video when available.
7. Extract entities, dates, citations, amounts, and document numbers.
8. Attach provenance: source path, source document ID, page or timestamp, source hash, confidence, and ARE event hash.
9. Admit the evidence into governed memory.
10. Store the legal projection and keep the raw authority linked.

Evidence is never treated as fact unless its status is explicit:
- extracted
- inferred
- disputed
- user-confirmed

## 4. Document-production lifecycle

1. Assemble source-backed packet.
2. Apply firm profile.
3. Apply court profile.
4. Generate editable DOCX and print-ready PDF.
5. Preserve citations and source appendix.
6. Mark work as draft until human review.
7. Do not claim signed, filed, or court-approved without an explicit authorized action.

## 5. Roles

- Firm Administrator
- Attorney
- Paralegal
- Legal Assistant
- Reviewer
- Read Only

Authority rules:
- attorney approval is not implied by paralegal or assistant activity
- signing authority is explicit
- filing authority is explicit
- exports are auditable

## 6. Product boundaries

- No real court filing automation.
- No secret exposure.
- No private legal corpus ingestion during automated tests.
- No replacement of ARE or Truth Spine.
- No blind rewrite of working dark interfaces.

## 7. Required completion targets

The intended product should eventually include:
- PACER-style matter organization
- folder and archive ingestion
- OCR and media transcription
- CourtListener research
- contradictions and timelines
- source-linked analysis
- drafting and packet production
- firm branding
- role-based permissions
- replayable audit trails

## 8. Current constitution status

The constitution is partially satisfied by existing code:
- dark GUI foundation exists
- parser / evidence engine exist
- CourtListener bridge exists
- packet generation exists
- replayable traces exist

The constitution is not yet fully satisfied because firm/staff authority, resumable large imports, and a complete front-door CLAIRE workflow are not yet finished as a single coherent product.
