# Drive Component Recovery Map

This map connects Drive specifications and code-shaped artifacts to the current local CLAIRE implementation.

## 1. Continuity / Session Capsule

| Field | Finding |
|---|---|
| Earliest known design | `CLAIRE ORIGIN MANIFEST`, `Out reach`, Session Capsule references in commercialization docs |
| Strongest Drive specification | `Out reach`, `CLAIRE Manifest Package v2 - Review Copy`, `handoff` |
| Strongest current code | `claire_continuity/core.py`, `session_continuity.py`, `test_claire_continuity_demo.py`, `test_session_continuity.py` |
| Missing functionality | Public route not approved; richer insight records; correction history; explicit evidence basis for beliefs; UI workflow. |
| Duplicated implementations | Drive capsule/HMAC demos are superseded by current local Continuity proof plus `claire_are`. |
| Should strengthen Continuity | Yes. This is the product center. |
| Should remain separate | Portable Markdown/JSON must remain separate from ARE so other AIs can consume it. |
| MVP relevance | Core. |
| Commercial relevance | High. |

Recovery decision: keep the local Continuity MVP as the authoritative implementation and promote the Drive manifest/outreach language into docs and acceptance criteria.

## 2. Collaboration Profile

| Field | Finding |
|---|---|
| Earliest known design | Collaboration behavior appears across `handoff`, Manifest v2, and current code; no stronger exact Drive-only profile spec was found. |
| Strongest Drive specification | `handoff` for behavior expectations; Manifest v2 for operator doctrine. |
| Strongest current code | `session_continuity.py::CollaborationProfile`, `claire_continuity/core.py` demo profile generation. |
| Missing functionality | Stable schema documentation, user-editable profile, profile versioning, trust-note redaction rules. |
| Duplicated implementations | Not confirmed. |
| Should strengthen Continuity | Yes. |
| Should remain separate | It should be embedded by reference in shareable capsules, with private fields redacted. |
| MVP relevance | Core. |
| Commercial relevance | High. |

Recovery decision: current local schema is strongest; add documentation and redaction tests before public exposure.

## 3. Insight Preservation

| Field | Finding |
|---|---|
| Earliest known design | Manifest v2 and outreach docs describe preserving continuity, learned facts, and governed memory. |
| Strongest Drive specification | `Out reach`, `handoff`, Manifest Package v2. |
| Strongest current code | `claire_continuity/core.py` includes `important_insights`; `session_continuity.py` supports continuity facts and capsule summaries. |
| Missing functionality | Explicit "why we believe it", evidence basis, confidence label, correction history, and source linkage per insight. |
| Duplicated implementations | No direct duplicate found. |
| Should strengthen Continuity | Yes. It directly serves "what we know" and "why we believe it." |
| Should remain separate | Insight records should be portable JSON/Markdown; ARE admission should remain metadata-only by default. |
| MVP relevance | Core, but can start simple. |
| Commercial relevance | High. |

Recovery decision: add an `InsightRecord` schema after the MVP proof stabilizes, not before.

## 4. Drift Detection

| Field | Finding |
|---|---|
| Earliest known design | Session Capsule and outreach docs; Gyro/Q Insight expands the orientation concept. |
| Strongest Drive specification | `Q Insight`, `handoff`, `Out reach`. |
| Strongest current code | `session_continuity.py::SentimentMonitor`; current capsule drift/sentiment state. |
| Missing functionality | Quantified drift metrics, correction history, model-to-model comparison, durable drift ledger. |
| Duplicated implementations | Multiple concept versions; no full production implementation. |
| Should strengthen Continuity | Yes, but only in lightweight form for MVP. |
| Should remain separate | Full Gyro/Q Insight should remain Phase 2. |
| MVP relevance | MVP optional/simple. |
| Commercial relevance | High. |

Recovery decision: keep lightweight drift state in MVP; postpone full Gyro orientation engine.

## 5. ARE / Memory Authority

| Field | Finding |
|---|---|
| Earliest known design | `Claire Diode ARE`, `Claire High Level no Military ops`, earlier ARE code exports. |
| Strongest Drive specification | `ARE Truth Spine L1 Deterministic Memory Kernel - v0`, `Claire Diode ARE`, Manifest v2. |
| Strongest current code | `claire_are/truth_spine.py`, `claire_are/core.py`, `claire_are/config.py`. |
| Missing functionality | Benchmark-driven bounded recall optimization remains a known performance follow-up. |
| Duplicated implementations | Many: ClairePay ARE, Truth Spine v0, legacy ARE/Spectacle services. |
| Should strengthen Continuity | Yes, as optional provenance. |
| Should remain separate | Yes. Receiving AIs must not require ARE. |
| MVP relevance | MVP optional, already proven metadata-only locally. |
| Commercial relevance | Very high. |

Recovery decision: current `claire_are` is canonical. Do not revive Drive ARE snippets except as design history.

## 6. Truth Spine / Provenance

| Field | Finding |
|---|---|
| Earliest known design | Early Diode/ARE docs and Truth Spine v0 package. |
| Strongest Drive specification | `ARE Truth Spine L1 Deterministic Memory Kernel - v0`. |
| Strongest current code | `claire_are/truth_spine.py`. |
| Missing functionality | Bounded tail-cache/segment cursor and checkpoint verification optimizations are pending from benchmark analysis. |
| Duplicated implementations | Truth Spine v0 and current `claire_are` duplicate goals; current code supersedes. |
| Should strengthen Continuity | Yes, but only by storing capsule metadata/hash, not full private content by default. |
| Should remain separate | Yes. |
| MVP relevance | MVP optional/provenance. |
| Commercial relevance | Very high. |

Recovery decision: use current `claire_are` adapter pattern; keep private and shareable artifacts canonical outside ARE.

## 7. Diode / Export Control

| Field | Finding |
|---|---|
| Earliest known design | `Claire Diode ARE`, `Claire High Level no Military ops`. |
| Strongest Drive specification | `Revised Codemask`, `Claire High Level no Military ops`, `Q Insight`. |
| Strongest current code | `claire_are/diode_guard.py`, `write_barrier.py`, Continuity redaction/export separation. |
| Missing functionality | Unified export policy engine and audit trail for every export. |
| Duplicated implementations | Drive Diode specs, Streamlit HMAC demo, current guard/barrier code. |
| Should strengthen Continuity | Yes. Redaction/export gating is MVP-required. |
| Should remain separate | Policy engine can be separate, but Continuity must call it. |
| MVP relevance | Core as redaction/export boundary. |
| Commercial relevance | High. |

Recovery decision: Continuity MVP should keep its explicit private/shareable split and later route through a reusable Diode adapter.

## 8. TrailLink / Lineage

| Field | Finding |
|---|---|
| Earliest known design | `Claire High Level no Military ops` H&G breadcrumbs and lineage ideas. |
| Strongest Drive specification | Manifest v2, `Out reach`, `Q Insight`, `Claire High Level no Military ops`. |
| Strongest current code | Legacy/private ARE/Spectacle clones contain `app/services/traillink.py`. |
| Missing functionality | Mainline integration with current Continuity and Truth Spine. |
| Duplicated implementations | Breadcrumb, TrailLink, and Truth Spine chain overlap but are not identical. |
| Should strengthen Continuity | Yes, but Phase 2. |
| Should remain separate | It can remain a library/service used by capsules. |
| MVP relevance | Phase 2. |
| Commercial relevance | High. |

Recovery decision: do not add TrailLink to MVP; first document capsule prior-hash chaining and manifest lineage.

## 9. Gyro / Orientation

| Field | Finding |
|---|---|
| Earliest known design | Early Gyro docs and `Q Insight`. |
| Strongest Drive specification | `Q Insight`. |
| Strongest current code | `claire_core_v1.py::Gyro`; legacy/private `gyro_are.py` services in audit clones. |
| Missing functionality | Full orientation field, active planes, doors/windows, reverse recognition, and validation suite. |
| Duplicated implementations | Multiple spec/prototype versions. |
| Should strengthen Continuity | Yes, eventually as compact orientation snapshot. |
| Should remain separate | Full Gyro should remain separate from Continuity MVP. |
| MVP relevance | Phase 2; MVP optional only as a small orientation field. |
| Commercial relevance | Very high. |

Recovery decision: create a simple orientation snapshot later; do not integrate full Q Insight now.

## 10. C3RP / Context Routing

| Field | Finding |
|---|---|
| Earliest known design | `C3RP ROUTER`, `Claire High Level no Military ops`. |
| Strongest Drive specification | `C3RP ROUTER`, `Handshake C3RP`. |
| Strongest current code | AGENTS memory routing spec, routing tests, local C3RP-style runtime pieces. |
| Missing functionality | Unified service, authenticated scoped sessions, router/trace integration everywhere. |
| Duplicated implementations | Drive router and local tests overlap. |
| Should strengthen Continuity | Yes, to preserve which memory lanes are allowed and which context is off-limits. |
| Should remain separate | Routing service can remain core CLAIRE, with Continuity storing routing hints. |
| MVP relevance | MVP optional; Phase 2 for full service. |
| Commercial relevance | High. |

Recovery decision: add `allowed_lanes` and `blocked_lanes` to capsule/handoff before full C3RP integration.

## 11. Contradiction Detection

| Field | Finding |
|---|---|
| Earliest known design | Veritas and Q Insight materials. |
| Strongest Drive specification | `Q Insight`, Manifest v2, Veritas ingestion/code exports. |
| Strongest current code | Veritas legal code and tests, not the Drive docs. |
| Missing functionality | Direct Continuity integration for contradiction/correction history. |
| Duplicated implementations | Veritas and general CLAIRE concepts overlap. |
| Should strengthen Continuity | Yes, later for "what changed" and "what was corrected." |
| Should remain separate | Veritas contradiction engine should remain legal/evidence subsystem. |
| MVP relevance | Phase 2. |
| Commercial relevance | High. |

Recovery decision: expose contradiction summaries into capsules later, not full contradiction engine in MVP.

## 12. Evidence Register

| Field | Finding |
|---|---|
| Earliest known design | Veritas/ARE/Venture evidence materials. |
| Strongest Drive specification | `000133_Claire Main build`, `FINAL GEMINI CODE for claire`, Manifest v2. |
| Strongest current code | Veritas evidence engine, Venture evidence repository, `claire_are`. |
| Missing functionality | Unified cross-product evidence register remains separate work. |
| Duplicated implementations | Venture, Veritas, and Drive ingest code have overlapping evidence concepts. |
| Should strengthen Continuity | Only as provenance references, not as a full evidence store. |
| Should remain separate | Yes. |
| MVP relevance | MVP optional as links/hashes only. |
| Commercial relevance | High. |

Recovery decision: Continuity should link to evidence records but not become the evidence register.

## 13. Librarian

| Field | Finding |
|---|---|
| Earliest known design | Not clearly found in Drive search. |
| Strongest Drive specification | None identified. |
| Strongest current code | Prior GitHub audit points to `clairetech2025-max/ARE-Librarian` as likely private line. |
| Missing functionality | Requires direct repository review. |
| Duplicated implementations | Unknown. |
| Should strengthen Continuity | Unknown until code review. |
| Should remain separate | Yes until ownership and privacy are clear. |
| MVP relevance | Do not integrate yet. |
| Commercial relevance | Potentially high. |

Recovery decision: treat Librarian as private/unknown and do not integrate into Continuity MVP.

## 14. Veritas

| Field | Finding |
|---|---|
| Earliest known design | `000133_Claire Main build`, `FINAL GEMINI CODE for claire`, manifest docs. |
| Strongest Drive specification | `000133_Claire Main build` for ingestion, Manifest v2 for doctrine. |
| Strongest current code | `/home/LuciusPrime/claire_repos/claire-veritas-legal` and live dark Veritas services. |
| Missing functionality | Full workstation roadmap remains incomplete, but parser/evidence/CourtListener/report pieces are real. |
| Duplicated implementations | White mobile replacement, dark Veritas, old Drive snippets, local repo versions. |
| Should strengthen Continuity | Only by exporting matter summaries and source-linked insights. |
| Should remain separate | Yes. |
| MVP relevance | Not required for Continuity MVP. |
| Commercial relevance | Very high. |

Recovery decision: keep Veritas separate and source-link into Continuity where appropriate.

## 15. CLAIRE Operating Manifest / Constitution

| Field | Finding |
|---|---|
| Earliest known design | `CLAIRE ORIGIN MANIFEST`. |
| Strongest Drive specification | `CLAIRE Manifest Package v2 - Review Copy`. |
| Strongest current code | AGENTS instructions, current architecture docs, runtime constraints. |
| Missing functionality | One canonical repo document should be created after privacy review. |
| Duplicated implementations | Origin Manifest, Manifest v2, Revised Codemask, DARPA, pitch deck. |
| Should strengthen Continuity | Yes. It defines how collaboration and authority should be preserved. |
| Should remain separate | Canon should be a top-level governance document, not buried in Continuity code. |
| MVP relevance | Core as product doctrine, not code. |
| Commercial relevance | Very high. |

Recovery decision: Manifest Package v2 is the strongest canonical candidate.

