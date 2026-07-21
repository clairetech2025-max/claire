# CLAIRE Drive Architecture Inventory

Audit mode: read-only discovery and comparison.

This inventory reviews relevant Google Drive materials against the current local CLAIRE codebase and prior local GitHub repository audit artifacts. No Drive files, repositories, or application code were changed.

## Summary Dashboard

| Metric | Count |
|---|---:|
| Relevant Drive files reviewed | 24 |
| False-positive Drive hits inspected and excluded | 2 |
| Verified runnable code files from Drive alone | 0 |
| Code or partial-code artifacts | 9 |
| Architecture specifications | 10 |
| Product or operating manifests | 8 |
| Commercialization materials | 5 |
| Patent-sensitive materials | 9 |
| Duplicate or superseded versions | 8 |
| Strong canonical candidates | 5 |

Notes:

- "Verified runnable code" means executed from Drive as-is. No Drive code was executed during this read-only audit.
- Several Drive files contain substantial code-shaped material, but many depend on old Windows paths, missing modules, placeholder functions, or older product names.
- The strongest current executable implementation of ARE / Truth Spine is local under `claire_are/`, not the older Drive snippets.

## File Records

### 1. 000133_Claire Main build_68d2df11_CODE.txt

| Field | Value |
|---|---|
| Drive URL | https://drive.google.com/file/d/1wKQ2lK7tQv1xFohsR7c9vOCCCU59AxOq |
| Drive file ID | `1wKQ2lK7tQv1xFohsR7c9vOCCCU59AxOq` |
| Created | 2026-04-09T19:52:55.562Z |
| Modified | 2026-02-04T10:58:48.000Z |
| Category | PARTIAL CODE |
| Related component | Veritas ingest, capsule builder, OCR, CourtListener ingestion, UI prototype |
| Summary | Large code export containing a hardened-looking `claire_ingest.py`, recursive ingest, manifest hashing, quarantine, PDF text/OCR fallback, DOCX support, chunking, web fetch, CourtListener parsing, and an offline UI bundle. |
| Technical contribution | Earlier universal ingestion and capsule-building design with file manifests, SHA-256 skip behavior, quarantine, and OCR fallback. |
| Executable code | Yes, but not verified runnable; includes old Windows paths and external binary assumptions. |
| Equivalent local code | Partially. Current Veritas and CLAIRE modules contain newer ingestion, evidence, and continuity pieces but not this exact monolithic workflow. |
| Equivalent GitHub code | Likely overlaps with `claire-veritas-legal` and older public/private CLAIRE exports. |
| Predecessor/successor | Predecessor to current Veritas ingestion and Continuity capsule work. |
| Duplication | Superseded by current local implementations in pieces. |
| Current relevance | High for Veritas ingestion archaeology, moderate for Continuity. |
| Privacy sensitivity | High, because it is a large build export and may contain paths, product internals, and ingestion details. |
| Patent sensitivity | Medium to high. |
| Recommended action | MERGE WITH STRONGER VERSION; incorporate manifest/OCR lessons into Veritas only after code review. |

### 2. 000011_ClairePay ARE setup_69236cca.txt

| Field | Value |
|---|---|
| Drive URL | https://drive.google.com/file/d/1AwALQaiIArFjmfkRbERqlwejIYPrCYs1 |
| Drive file ID | `1AwALQaiIArFjmfkRbERqlwejIYPrCYs1` |
| Created | 2026-04-09T19:52:49.057Z |
| Modified | 2026-02-04T10:58:40.000Z |
| Category | PARTIAL CODE |
| Related component | ClairePay, simple ARE prototype |
| Summary | FastAPI ClairePay prototype with a JSONL `ClaireARE`, payment method memory, autopilot selection, and simulated payment routes. |
| Technical contribution | Demonstrates an early domain-specific memory loop: record, recall, choose action, simulate execution, audit. |
| Executable code | Yes in shape, not verified here. |
| Equivalent local code | Not canonical. Current `claire_are/` is stronger for governed memory. |
| Equivalent GitHub code | Possible older ClairePay or prototype repositories. |
| Predecessor/successor | Predecessor to governed demo-mode decision loops. |
| Duplication | Duplicates simple memory behavior now handled by ARE/Truth Spine patterns. |
| Current relevance | Low for Continuity MVP; useful as product history. |
| Privacy sensitivity | Medium. Payment-domain material should remain private until reviewed. |
| Patent sensitivity | Medium. |
| Recommended action | KEEP AS PRODUCT HISTORY; do not use as canonical ARE. |

### 3. Ecosystem Architecture Diagram / Parser-Led Licensing Document

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1ZfcfeaqBfgzizaJ4fJOpsoYZBTeBjA01cqy8eFLgbJ0 |
| Drive file ID | `1ZfcfeaqBfgzizaJ4fJOpsoYZBTeBjA01cqy8eFLgbJ0` |
| Created | 2025-12-10T01:47:29.238Z |
| Modified | 2025-12-10T01:47:55.448Z |
| Category | ARCHITECTURE SPECIFICATION / COMMERCIALIZATION MATERIAL / SUPERSEDED VERSION |
| Related component | Veritas Parser, H&G token fabric, ARE, Diode, C3RP, TrailLink |
| Summary | Early ecosystem map showing data sources into a parser, Hansel and Gretel token fabric, ARE, Diode, C3RP, Lycanthrope, ClairePay, and TrailLink. |
| Technical contribution | Captures early system decomposition and licensing boundaries. |
| Executable code | Mostly no; contains code-shaped fragments but primarily architecture and product language. |
| Equivalent local code | Current names and implementation differ; "Palantir Parser" was superseded by Veritas Parser framing. |
| Equivalent GitHub code | Some ideas appear in legacy ARE/Spectacle and Veritas repositories. |
| Predecessor/successor | Predecessor to current Veritas/ARE/Governance architecture. |
| Duplication | Superseded by later manifest and Q Insight documents. |
| Current relevance | Medium as architecture history, low as implementation guide. |
| Privacy sensitivity | High. |
| Patent sensitivity | High. |
| Recommended action | KEEP AS PRODUCT HISTORY; merge only non-superseded concepts into current canon. |

### 4. AZURE STREAMLIT DEMO UPGRADE 2Claires

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1EEAjHhyQzJ0xOsfnrQ_6rc-BZHFMbLVzt3LsnNKOGZE |
| Drive file ID | `1EEAjHhyQzJ0xOsfnrQ_6rc-BZHFMbLVzt3LsnNKOGZE` |
| Created | 2025-12-30T00:44:03.770Z |
| Modified | 2026-03-15T00:41:49.378Z |
| Category | PARTIAL CODE / PRODUCT DEMO |
| Related component | Veritas, Diode capsule, signed capsule demo |
| Summary | Streamlit local/cloud demo with HMAC-signed capsules, drift threshold checks, and Local Overwatch / Azure Enforcer framing. |
| Technical contribution | Demonstrates early signed capsule and diode-style enforcement proof. |
| Executable code | Code-shaped; not verified runnable. |
| Equivalent local code | Current `claire_are` HMAC chain and `claire_continuity` provenance metadata are stronger. |
| Equivalent GitHub code | Possible overlap with older demo repositories. |
| Predecessor/successor | Predecessor to current Truth Spine and Continuity metadata admission. |
| Duplication | Superseded by current ARE/Truth Spine for provenance. |
| Current relevance | Medium for demo history, low for MVP code. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | Medium. |
| Recommended action | KEEP AS PRODUCT HISTORY; do not integrate directly. |

### 5. Out reach

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1w7BXN5ntrV13DwoibocNUMt08MTPVVwM2BnikyuBI00 |
| Drive file ID | `1w7BXN5ntrV13DwoibocNUMt08MTPVVwM2BnikyuBI00` |
| Created | 2026-05-24T08:42:10.720Z |
| Modified | 2026-05-24T08:44:04.670Z |
| Category | TECHNICAL REVIEW / PRODUCT DEFINITION |
| Related component | ARE, Session Capsule Protocol, Gyro/Q Insight, Sentinel, TrailLink |
| Summary | Technical outreach document describing ARE, Session Capsule Protocol, Gyro/Q Insight, Diode/WriteBarrier, Capsule Integrity, Sentinel, Reflective/Backward ARE, and Trace/Provenance. |
| Technical contribution | Strong concise framing for continuity, external memory authority, and validation claims. |
| Executable code | No. |
| Equivalent local code | Current `claire_continuity`, `session_continuity`, `claire_are`, and C3RP routing tests implement parts. |
| Equivalent GitHub code | Session Capsule and ARE/Spectacle repositories likely contain related proof work. |
| Predecessor/successor | Contemporary product framing for current continuity work. |
| Duplication | Overlaps with Manifest Package v2 and pitch materials. |
| Current relevance | High. |
| Privacy sensitivity | High. |
| Patent sensitivity | High. |
| Recommended action | PROMOTE TO CANON for technical outreach after claims are tied to tests. |

### 6. CLAIRE ORIGIN MANIFEST - Litigation Spine, Build Canon, and Founding Mission

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1U3kJWyqCEwhgKKeWMooJe5_IWXeJpxOhBpK6rQUyDo4 |
| Drive file ID | `1U3kJWyqCEwhgKKeWMooJe5_IWXeJpxOhBpK6rQUyDo4` |
| Created | 2026-03-31T10:00:17.329Z |
| Modified | 2026-03-31T13:03:28.127Z |
| Category | OPERATING MANIFEST / ARCHITECTURE SPECIFICATION |
| Related component | CLAIRE core, ARE, Sentinel, Veritas, ingestion |
| Summary | Founding build canon emphasizing litigation/evidence priority, memory-first flow, ARE, Sentinel-lite, Veritas ledger, and ingestion order. |
| Technical contribution | Defines build doctrine and what not to redesign. |
| Executable code | No. |
| Equivalent local code | Current CLAIRE implementation follows parts, especially ARE/Veritas/Continuity. |
| Equivalent GitHub code | Related to main CLAIRE repo and Veritas repos. |
| Predecessor/successor | Likely predecessor to Manifest Package v2. |
| Duplication | Superseded by Manifest Package v2 but still historically important. |
| Current relevance | High. |
| Privacy sensitivity | High. |
| Patent sensitivity | Medium. |
| Recommended action | KEEP AS PRODUCT HISTORY; use Manifest Package v2 as canonical if confirmed. |

### 7. CLAIRE Manifest Package v2 - Review Copy

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1XK7rsTc4zIa5KtecE-aYt_1Oz_TprYhpFc6fxS4B--w |
| Drive file ID | `1XK7rsTc4zIa5KtecE-aYt_1Oz_TprYhpFc6fxS4B--w` |
| Created | 2026-05-20T11:12:19.626Z |
| Modified | 2026-05-20T11:12:24.921Z |
| Category | OPERATING MANIFEST / PRODUCT DEFINITION / PATENT MATERIAL |
| Related component | CLAIRE constitution, operator manifest, ARE doctrine |
| Summary | Strongest consolidated manifesto package: Origin Manifest, Operator Manifest, and Blueprint. Defines truth outside the model, externalized memory, lineage, and constrained reasoning. |
| Technical contribution | Best current canonical candidate for CLAIRE doctrine and operating contract. |
| Executable code | No. |
| Equivalent local code | Local architecture and AGENTS instructions reflect pieces of this doctrine. |
| Equivalent GitHub code | Should be referenced by main CLAIRE documentation after privacy review. |
| Predecessor/successor | Successor to earlier Origin Manifest. |
| Duplication | Consolidates several earlier docs. |
| Current relevance | Very high. |
| Privacy sensitivity | High. |
| Patent sensitivity | High. |
| Recommended action | PROMOTE TO CANON; KEEP PRIVATE unless explicitly sanitized. |

### 8. Revised Codemask

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1r5ZezmyAI4EzPhjnhlyHN0wK0T4r9oqXxsyE1QLLL8E |
| Drive file ID | `1r5ZezmyAI4EzPhjnhlyHN0wK0T4r9oqXxsyE1QLLL8E` |
| Created | 2025-12-22T06:09:28.145Z |
| Modified | 2026-03-05T22:10:44.411Z |
| Category | ARCHITECTURE SPECIFICATION / PATENT MATERIAL |
| Related component | Truth, authority, behavior planes; ingest; Truth Spine; Directional Constraint; Supervisor; continuity |
| Summary | Non-executable codemask architecture specification expressed as dataclasses and integration edges. |
| Technical contribution | Safe external-review representation of CLAIRE subsystems without full implementation disclosure. |
| Executable code | No. It explicitly functions as code-shaped prose, not executable code. |
| Equivalent local code | Current code implements parts, but this is an abstraction layer. |
| Equivalent GitHub code | Not intended as direct code. |
| Predecessor/successor | Parallel disclosure artifact. |
| Duplication | Overlaps with Manifest v2 and DARPA materials. |
| Current relevance | High for disclosure strategy; medium for engineering. |
| Privacy sensitivity | High. |
| Patent sensitivity | High. |
| Recommended action | KEEP AS SPECIFICATION; promote only sanitized excerpts. |

### 9. handoff

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/11m3vrVa8vqVdDSZMuPq8SYFDY7Mrw-E_QjmCZ531gvQ |
| Drive file ID | `11m3vrVa8vqVdDSZMuPq8SYFDY7Mrw-E_QjmCZ531gvQ` |
| Created | 2026-05-14T22:11:17.821Z |
| Modified | 2026-05-14T22:11:40.892Z |
| Category | OPERATING MANIFEST / TECHNICAL REVIEW |
| Related component | Continuity evaluation, collaboration behavior |
| Summary | Behavioral test checklist for conversation, investor, governance, ambiguity, long-form continuity, developer work, and restraint. |
| Technical contribution | Good acceptance/evaluation scaffold for Continuity and CLAIRE behavior. |
| Executable code | No. |
| Equivalent local code | Current tests do not fully cover this behavioral suite. |
| Equivalent GitHub code | May overlap with session capsule repository documentation. |
| Predecessor/successor | Useful adjunct to Continuity MVP. |
| Duplication | Overlaps with operator manifest. |
| Current relevance | Medium to high. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | Low to medium. |
| Recommended action | INCORPORATE INTO CONTINUITY as future evaluation checklist. |

### 10. MARKETPLACE_LISTING.md

| Field | Value |
|---|---|
| Drive URL | https://drive.google.com/file/d/10iSAzQBPPBUCenzi1Qp2lYKfYsxR0xMr |
| Drive file ID | `10iSAzQBPPBUCenzi1Qp2lYKfYsxR0xMr` |
| Created | 2026-04-21T17:16:35.309Z |
| Modified | 2026-04-21T15:50:13.000Z |
| Category | COMMERCIALIZATION MATERIAL / PRODUCT DEFINITION |
| Related component | ARE Spectacle, Gyro memory middleware |
| Summary | Azure Marketplace draft for ARE Spectacle / Gyro memory middleware with endpoints, deployment shape, and explicit avoided claims. |
| Technical contribution | Clear product boundaries and claims discipline. |
| Executable code | No. |
| Equivalent local code | GitHub audit found legacy/private Spectacle code with related services. |
| Equivalent GitHub code | `Analog-Recall-Engine-Legacy` and `Claire-Systems-are-spectacle-private` are likely related. |
| Predecessor/successor | Commercial packaging layer over ARE/Gyro. |
| Duplication | Overlaps with README and pitch deck. |
| Current relevance | Medium. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | Medium. |
| Recommended action | KEEP AS PRODUCT HISTORY; use claims discipline in public materials. |

### 11. Gemini's Assessment

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1uExW1aOJXrxJ6H4uZz3m9icjtQDk0kSsX6IrNNsuyk8 |
| Drive file ID | `1uExW1aOJXrxJ6H4uZz3m9icjtQDk0kSsX6IrNNsuyk8` |
| Created | 2025-12-15T14:20:20.019Z |
| Modified | 2025-12-15T14:21:37.717Z |
| Category | TECHNICAL REVIEW / COMMERCIALIZATION MATERIAL |
| Related component | CLAIRE strategic positioning |
| Summary | External-style assessment of CLAIRE capabilities and strategy. |
| Technical contribution | Useful for positioning, not implementation. |
| Executable code | No. |
| Equivalent local code | No direct equivalent. |
| Equivalent GitHub code | No direct equivalent. |
| Predecessor/successor | Predecessor to polished decks and outreach docs. |
| Duplication | Overlaps with pitch and outreach. |
| Current relevance | Low to medium. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | Medium. |
| Recommended action | KEEP AS PRODUCT HISTORY; verify claims before reuse. |

### 12. Anduril Lattice Submission - CLAIRE Final Email

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1sJl1frQBHCna8IauoYKJhaisDHdvkMHyXZZ_V0iR1Gc |
| Drive file ID | `1sJl1frQBHCna8IauoYKJhaisDHdvkMHyXZZ_V0iR1Gc` |
| Created | 2026-05-20T10:59:38.495Z |
| Modified | 2026-05-26T21:51:30.536Z |
| Category | COMMERCIALIZATION MATERIAL |
| Related component | ARE, Gyro/Q Insight, Sentinel, TrailLink, Session Capsule Protocol |
| Summary | Concise external submission language for CLAIRE as governed continuity and memory architecture. |
| Technical contribution | Clear, short description of system components and value. |
| Executable code | No. |
| Equivalent local code | Local code implements parts, but this is communication material. |
| Equivalent GitHub code | No direct code equivalent. |
| Predecessor/successor | Contemporary outreach asset. |
| Duplication | Overlaps with Out reach and pitch deck. |
| Current relevance | Medium. |
| Privacy sensitivity | High due contact and patent references. |
| Patent sensitivity | High. |
| Recommended action | KEEP PRIVATE; use as controlled outreach template after redaction. |

### 13. Gyro Cinematic / Cognitive System Document

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1WZJYh8rKxdvvOBE_m-gAXpz4A5gS-YeYuftkqFNJM5M |
| Drive file ID | `1WZJYh8rKxdvvOBE_m-gAXpz4A5gS-YeYuftkqFNJM5M` |
| Created | 2026-06-07T10:23:53.909Z |
| Modified | 2026-06-07T10:24:46.887Z |
| Category | ARCHITECTURE SPECIFICATION / PARTIAL CODE |
| Related component | Gyro, Q Insight, orientation field |
| Summary | Starts as animation prompt, then expands into Gyro cognitive orientation and immune behavior ideas, including 360x360 orientation space and a partial `OrientationField` sketch. |
| Technical contribution | Useful conceptual description of orientation snapshots and quarantine/immune behavior. |
| Executable code | Partial sketch only. |
| Equivalent local code | `claire_core_v1.py` contains a much smaller `Gyro` prototype. |
| Equivalent GitHub code | ARE Spectacle repositories likely contain `gyro_are.py`. |
| Predecessor/successor | Related to Q Insight, but Q Insight is stronger as specification. |
| Duplication | Superseded by Q Insight for architecture. |
| Current relevance | Medium. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | High. |
| Recommended action | MERGE WITH STRONGER VERSION; keep Q Insight as canonical. |

### 14. README.md - ARE Glasses

| Field | Value |
|---|---|
| Drive URL | https://drive.google.com/file/d/1WxjK4QVgBtCUjhYGj96h3zQtzRZzbECn |
| Drive file ID | `1WxjK4QVgBtCUjhYGj96h3zQtzRZzbECn` |
| Created | 2026-04-21T17:16:33.711Z |
| Modified | 2026-04-20T10:14:16.000Z |
| Category | PRODUCT DEFINITION |
| Related component | ARE Glasses, Spectacle, Gyro middleware |
| Summary | README for model-agnostic memory visor exposing ingest, query, gyro, prompt-prefix, trace, and report endpoints. |
| Technical contribution | Clear service API and deployment framing for a middleware product. |
| Executable code | No, README only. |
| Equivalent local code | Related services appear in local GitHub audit clones. |
| Equivalent GitHub code | `Analog-Recall-Engine-Legacy` and private Spectacle repo. |
| Predecessor/successor | Product-facing packaging of ARE/Gyro. |
| Duplication | Overlaps with Marketplace listing. |
| Current relevance | Medium. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | Medium. |
| Recommended action | KEEP AS PRODUCT HISTORY; reconcile with actual service repo before public use. |

### 15. Untitled document - PyGyro Directional Repair

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1v_s4sqy1BTzSRchiGC2TvIbUXlOc0XibdjMCMTyBk1g |
| Drive file ID | `1v_s4sqy1BTzSRchiGC2TvIbUXlOc0XibdjMCMTyBk1g` |
| Created | 2026-05-15T23:54:11.039Z |
| Modified | 2026-05-15T23:54:24.389Z |
| Category | PARTIAL CODE / BROKEN |
| Related component | Gyro repair, code orientation |
| Summary | Python-shaped repair utility for AI-generated Python, but formatting appears broken and imports/main guard are malformed. |
| Technical contribution | Concept of directional repair may be useful, but current artifact is not a reliable implementation. |
| Executable code | Not as captured. |
| Equivalent local code | No direct production equivalent found. |
| Equivalent GitHub code | Unknown. |
| Predecessor/successor | Standalone experiment. |
| Duplication | None confirmed. |
| Current relevance | Low. |
| Privacy sensitivity | Low to medium. |
| Patent sensitivity | Low. |
| Recommended action | ARCHIVE unless PyGyro becomes a defined product. |

### 16. CLAIRE Pitch Deck - Polished Working Draft

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/presentation/d/1xE8wRf5VPpavTSlSFymzzfPprRESv3MRImm1wcPuaZA |
| Drive file ID | `1xE8wRf5VPpavTSlSFymzzfPprRESv3MRImm1wcPuaZA` |
| Created | 2026-05-31T13:32:54.579Z |
| Modified | 2026-06-12T18:35:36.129Z |
| Category | COMMERCIALIZATION MATERIAL |
| Related component | CLAIRE overall, ARE benchmark, Gyro, NVIDIA pitch |
| Summary | Investor/partner deck describing continuity tax, orient-before-generate, ARE performance, commercial positioning, and NVIDIA-related ask. |
| Technical contribution | Strong external narrative; contains benchmark claims that must remain linked to raw benchmark evidence. |
| Executable code | No. |
| Equivalent local code | Benchmarks and ARE code exist locally, but claims need current verification before reuse. |
| Equivalent GitHub code | No direct equivalent. |
| Predecessor/successor | Current commercialization artifact. |
| Duplication | Overlaps with outreach and marketplace materials. |
| Current relevance | High for commercialization, not implementation. |
| Privacy sensitivity | High. |
| Patent sensitivity | High. |
| Recommended action | KEEP PRIVATE; use only with verified benchmark appendix. |

### 17. Claire Diode ARE

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/15GhRJP4v3m8DBtWi5Mcw-nV9o7PYZ1NUMLScnNpnjmc |
| Drive file ID | `15GhRJP4v3m8DBtWi5Mcw-nV9o7PYZ1NUMLScnNpnjmc` |
| Created | 2025-12-04T09:09:47.473Z |
| Modified | 2025-12-08T21:11:41.645Z |
| Category | ARCHITECTURE SPECIFICATION / API SPECIFICATION |
| Related component | ARE, Diode Capsule system |
| Summary | ARE API spec v1.0 with recall, generate, verify, capsule hash, and signature endpoints. |
| Technical contribution | Early service contract for ARE and capsule verification. |
| Executable code | No. |
| Equivalent local code | `claire_are` now provides stronger local API primitives. |
| Equivalent GitHub code | Related to ARE legacy and Spectacle repositories. |
| Predecessor/successor | Early predecessor of current ARE/Truth Spine design. |
| Duplication | Superseded by current `claire_are` code and newer docs. |
| Current relevance | Medium as API history. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | Medium. |
| Recommended action | KEEP AS SPECIFICATION; do not treat as current API. |

### 18. Claire High Level no Military ops

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1wuIqD1RhaTpSTxO07o_cJi5tB_19evO4cUxvoJ1AXfw |
| Drive file ID | `1wuIqD1RhaTpSTxO07o_cJi5tB_19evO4cUxvoJ1AXfw` |
| Created | 2025-12-03T01:58:10.250Z |
| Modified | 2025-12-02T07:51:21.261Z |
| Category | PARTIAL CODE / ARCHITECTURE SPECIFICATION |
| Related component | Breadcrumbs, H&G ledger, ARE, DiodeGuard, C3RP, Sentinel, TrailLink precursor |
| Summary | Early code skeleton for breadcrumb tokens, JSONL ARE, Diode guard, parser bridge, C3RP messaging, Sentinel keyword scan, and beacon stubs. |
| Technical contribution | Important early source for Hansel and Gretel breadcrumbs, guarded routing, and lineage thinking. |
| Executable code | Partial; not verified. |
| Equivalent local code | Current `claire_are`, `write_barrier.py`, `claire_core_v1.py`, and legacy ARE/Spectacle service clones implement stronger pieces. |
| Equivalent GitHub code | Strong overlap with legacy ARE/Spectacle repositories. |
| Predecessor/successor | Predecessor to current ARE/Sentinel/TrailLink ideas. |
| Duplication | Superseded as code but still valuable architecture source. |
| Current relevance | High for recovery of TrailLink/C3RP origins. |
| Privacy sensitivity | High. |
| Patent sensitivity | High. |
| Recommended action | INCORPORATE INTO CLAIRE CORE as history/spec only; do not run directly. |

### 19. Q Insight

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1XcGcXEAEzJlAC8rVF-2_dPAN5cCqa67JXdzYpGDhu98 |
| Drive file ID | `1XcGcXEAEzJlAC8rVF-2_dPAN5cCqa67JXdzYpGDhu98` |
| Created | 2026-05-16T01:12:54.166Z |
| Modified | 2026-05-16T01:12:59.013Z |
| Category | ARCHITECTURE SPECIFICATION / PATENT MATERIAL |
| Related component | Gyro, Q Insight, orientation field, Diode, Sentinel, TrailLink |
| Summary | Strongest Gyro/Q Insight specification: orient before generation, externalized memory, stacked bearing planes, active doors/windows, reverse recognition, and validation plan. |
| Technical contribution | Best architecture source for Gyro/Q Insight. |
| Executable code | No, primarily specification. |
| Equivalent local code | Only a small `Gyro` prototype exists locally; full Q Insight is not implemented. |
| Equivalent GitHub code | ARE Spectacle has related `gyro_are.py`, but likely not full Q Insight. |
| Predecessor/successor | Strong canonical candidate for Gyro/Q Insight. |
| Duplication | Stronger than the cinematic Gyro doc. |
| Current relevance | High, but mostly Phase 2 for Continuity. |
| Privacy sensitivity | High. |
| Patent sensitivity | Very high. |
| Recommended action | PROMOTE TO CANON for Gyro/Q Insight; KEEP PRIVATE. |

### 20. DARPA

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1MLsokIyZqx-qNu4UBE80_dSRHoiNezZqUhWWG0oGcvM |
| Drive file ID | `1MLsokIyZqx-qNu4UBE80_dSRHoiNezZqUhWWG0oGcvM` |
| Created | 2025-12-22T06:34:20.268Z |
| Modified | 2025-12-22T06:43:17.946Z |
| Category | ARCHITECTURE SPECIFICATION / COMMERCIALIZATION MATERIAL / PATENT MATERIAL |
| Related component | Truth, authority, behavior planes; governed AI; defense-facing framing |
| Summary | Governance-first architecture and disclosure document oriented toward controlled technical evaluation. |
| Technical contribution | Useful for high-level architecture and disclosure posture, not implementation. |
| Executable code | No. |
| Equivalent local code | Pieces exist, but this is not code. |
| Equivalent GitHub code | No direct equivalent. |
| Predecessor/successor | Related to Revised Codemask and Manifest v2. |
| Duplication | Overlaps with codemask and pitch materials. |
| Current relevance | Medium. |
| Privacy sensitivity | High. |
| Patent sensitivity | High. |
| Recommended action | KEEP PRIVATE; use only for controlled external evaluation. |

### 21. ARE Truth Spine L1 Deterministic Memory Kernel - v0

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/14UHcK6TwYL7NGLO9OT3tKiQvJCTS-lOSb2Bwl4OnA_8 |
| Drive file ID | `14UHcK6TwYL7NGLO9OT3tKiQvJCTS-lOSb2Bwl4OnA_8` |
| Created | 2026-06-03T10:38:42.698Z |
| Modified | 2026-06-03T10:40:16.597Z |
| Category | PARTIAL CODE / ARCHITECTURE SPECIFICATION |
| Related component | ARE Truth Spine |
| Summary | Complete proposed package for a deterministic memory kernel with capsules, SHA/HMAC integrity, previous signatures, JSONL append-only storage, duplicate rejection, tests, and benchmark. |
| Technical contribution | Strong predecessor for append-only, tamper-evident Truth Spine implementation. |
| Executable code | Appears executable in package form, but not run in this audit. |
| Equivalent local code | Current `claire_are/truth_spine.py` is newer and stronger: segmented JSONL, manifest, HMAC signatures, previous-hash chain, queue writer, `fsync`, envelopes, verify. |
| Equivalent GitHub code | Main CLAIRE repo contains current implementation. |
| Predecessor/successor | Predecessor to current `claire_are` Truth Spine. |
| Duplication | Superseded as implementation; keep for design lineage. |
| Current relevance | High for provenance history and benchmark comparison. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | High. |
| Recommended action | KEEP AS SPECIFICATION; current code remains canonical. |

### 22. Handshake C3RP

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1c7DER23z-Ml_y8UTt8bWiyja6gj98HceJz4p81G0Ckc |
| Drive file ID | `1c7DER23z-Ml_y8UTt8bWiyja6gj98HceJz4p81G0Ckc` |
| Created | 2026-06-14T02:45:43.819Z |
| Modified | 2026-06-14T02:46:29.212Z |
| Category | PARTIAL CODE / ARCHITECTURE SPECIFICATION |
| Related component | C3RP, handshake, lane governance, scoped sessions |
| Summary | FastAPI demo for device registry, nonce handshake, HMAC verification, sessions, C3RP route/lane governance, scopes, and chat route. |
| Technical contribution | Strong design source for scoped routing and authenticated session handling. |
| Executable code | Partial; likely requires fixes before running. |
| Equivalent local code | C3RP-style lane governance exists in current runtime/tests, but not full handshake/session protocol. |
| Equivalent GitHub code | Possible overlap with session capsule and ARE Spectacle repos. |
| Predecessor/successor | Later C3RP design layer. |
| Duplication | Complements `C3RP ROUTER`. |
| Current relevance | Medium for Continuity Phase 2; not MVP-required. |
| Privacy sensitivity | High. |
| Patent sensitivity | Medium. |
| Recommended action | INCORPORATE INTO CONTINUITY later as scoped handoff/session gate. |

### 23. C3RP ROUTER

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1W-tKkM4yQ1a_lqIzQIOUCA1FtgeywwXa06UTpi67YB8 |
| Drive file ID | `1W-tKkM4yQ1a_lqIzQIOUCA1FtgeywwXa06UTpi67YB8` |
| Created | 2026-04-22T19:39:17.757Z |
| Modified | 2026-04-23T17:08:44.284Z |
| Category | PARTIAL CODE |
| Related component | C3RP, memory routing, relevance gate |
| Summary | Router classifies prompts into lanes and suppresses irrelevant memory, including legal case/docket material in abstract or architecture questions. |
| Technical contribution | Directly addresses the memory-routing failure where retrieval substitutes for reasoning. |
| Executable code | Partial; has placeholders. |
| Equivalent local code | Current `AGENTS.md` memory routing spec and local routing tests reflect this. |
| Equivalent GitHub code | Main CLAIRE repo likely contains current implementation. |
| Predecessor/successor | Predecessor to current lane-governance test anchor. |
| Duplication | Not duplicate; source design for current routing doctrine. |
| Current relevance | High. |
| Privacy sensitivity | Medium. |
| Patent sensitivity | Medium. |
| Recommended action | INCORPORATE INTO CLAIRE CORE; adapt concepts into Continuity handoff lanes later. |

### 24. FINAL GEMINI CODE for claire

| Field | Value |
|---|---|
| Drive URL | https://docs.google.com/document/d/1eM6rQ5uUzHq4xqW4H1Dfbs-wzxqHoddaXpkbu7DlLkI |
| Drive file ID | `1eM6rQ5uUzHq4xqW4H1Dfbs-wzxqHoddaXpkbu7DlLkI` |
| Created | 2026-03-22T01:14:21.803Z |
| Modified | 2026-03-22T01:15:06.251Z |
| Category | PARTIAL CODE / BROKEN |
| Related component | Veritas evidence ingestion, OCR, ZIP, entity extraction |
| Summary | Partial `ClaireEvidenceEngine` code with supported extensions, OCR, ZIP extraction, chunking, and legal extraction placeholders. |
| Technical contribution | Early Veritas evidence-ingestion skeleton. |
| Executable code | Not reliable as captured; placeholders and formatting issues observed. |
| Equivalent local code | Current Veritas legal repository and local parser/evidence engine are stronger. |
| Equivalent GitHub code | Likely predecessor to `claire-veritas-legal`. |
| Predecessor/successor | Predecessor to current Veritas ingestion work. |
| Duplication | Superseded by current Veritas code. |
| Current relevance | Medium for archaeology, low for direct integration. |
| Privacy sensitivity | Medium to high. |
| Patent sensitivity | Medium. |
| Recommended action | MERGE WITH STRONGER VERSION only if a missing extraction idea is identified. |

## Excluded False Positives

| Title | Reason excluded |
|---|---|
| 000361_CSP CSPF Support Overview_68600d5e.txt | Legal research/support overview hit on "Collaboration Profile" search terms, not a CLAIRE architecture asset. |
| 000621_Crypto Bot Strategy Code... | Crypto trading bot material hit during "Librarian" search; no meaningful Librarian/ARE architecture content identified. |

## Current Local Implementation Comparison

| Component | Strongest local code found | Status |
|---|---|---|
| ARE / Truth Spine | `claire_are/truth_spine.py`, `claire_are/core.py`, `claire_are/config.py` | Current canonical implementation. Segmented JSONL, manifest, HMAC signatures, previous-hash chain, queue-backed writer, verify/envelopes. |
| Diode / read-write guard | `claire_are/diode_guard.py`, `write_barrier.py` | Partial but real. Write barrier and lane access rules exist. |
| Continuity | `claire_continuity/core.py`, `session_continuity.py` | Real MVP proof exists: private/shareable/handoff exports, redaction, hashing, ARE metadata admission, provenance manifest. |
| C3RP / routing | `AGENTS.md`, current routing tests, `claire_runtime.py` where present | Doctrine and tests exist; full C3RP service remains partial. |
| Gyro | `claire_core_v1.py`, legacy Spectacle clones | Prototype only; full Q Insight not implemented. |
| TrailLink | legacy ARE/Spectacle clones under `github_cleanup_audit/repo_clones/.../app/services/traillink.py` | Exists in legacy/private lines; not integrated into main Continuity MVP. |
| Veritas | `/home/LuciusPrime/claire_repos/claire-veritas-legal`, current dark Veritas service | Real parser/evidence/CourtListener/timeline/report work exists outside Drive docs. |
| Librarian | GitHub audit identifies `clairetech2025-max/ARE-Librarian`; Drive search did not find a strong Librarian spec | Requires separate private repo review. |

## Immediate Findings

- The Drive materials are valuable mostly as architecture, product canon, and design lineage, not as drop-in production code.
- The current local `claire_are` implementation supersedes the Drive Truth Spine v0 code.
- The strongest Drive asset for CLAIRE doctrine is `CLAIRE Manifest Package v2 - Review Copy`.
- The strongest Drive asset for Gyro/Q Insight is `Q Insight`.
- The strongest Drive assets for Continuity framing are `Out reach`, `handoff`, and Manifest Package v2.
- The strongest Drive source for routing discipline is `C3RP ROUTER`.
- The strongest Drive source for early lineage/export-control primitives is `Claire High Level no Military ops`.
- Veritas ingestion ideas appear in older Drive code, but current local Veritas code should remain authoritative unless a missing extractor or manifest behavior is recovered deliberately.

