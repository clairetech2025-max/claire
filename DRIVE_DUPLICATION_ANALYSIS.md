# Drive Duplication Analysis

## Major Duplication Families

### ARE / Truth Spine

| Artifact | Relationship |
|---|---|
| `Claire Diode ARE` | Early API specification for recall/generate/verify and capsules. |
| `ARE Truth Spine L1 Deterministic Memory Kernel - v0` | Strong predecessor implementation package with JSONL/HMAC/previous-signature chain. |
| `000011_ClairePay ARE setup` | Domain-specific simple JSONL memory prototype. |
| Current `claire_are/truth_spine.py` | Current canonical implementation. |
| Legacy/private ARE Spectacle clones | Service packaging around ARE/Gyro concepts. |

Decision: current `claire_are` supersedes Drive code. Drive artifacts should be retained as lineage/specification, not merged blindly.

### Gyro / Q Insight / Spectacle

| Artifact | Relationship |
|---|---|
| `Q Insight` | Strongest architecture specification. |
| Gyro cinematic/cognitive-system document | Conceptual and visualization extension; superseded by Q Insight for engineering. |
| `README.md - ARE Glasses` | Product/API packaging of Gyro/ARE middleware. |
| `MARKETPLACE_LISTING.md` | Commercial packaging of Spectacle/ARE middleware. |
| `CLAIRE Pitch Deck` | Business narrative and benchmark claims. |
| Local `claire_core_v1.py::Gyro` | Small prototype only. |
| Legacy/private `gyro_are.py` | Implementation candidate requiring review. |

Decision: `Q Insight` should be canonical for architecture; implementation must be recovered from Spectacle/private repos, not from the Drive visualization prompt.

### Continuity / Session Capsule

| Artifact | Relationship |
|---|---|
| `Out reach` | Product and technical framing for Session Capsule Protocol. |
| `handoff` | Behavioral acceptance checklist. |
| `CLAIRE Manifest Package v2` | Doctrine-level framing. |
| `AZURE STREAMLIT DEMO UPGRADE 2Claires` | Earlier signed capsule demo. |
| Current `claire_continuity/core.py` | Current MVP proof implementation. |
| Current `session_continuity.py` | Collaboration profile, sentiment, and capsule primitives. |

Decision: current local code is authoritative for implementation. Drive docs should shape schema, documentation, and tests.

### C3RP / Routing / Memory Governance

| Artifact | Relationship |
|---|---|
| `C3RP ROUTER` | Direct source for lane classification and relevance gating. |
| `Handshake C3RP` | Later scoped-session/authenticated routing extension. |
| `Claire High Level no Military ops` | Early C3RP message and sentinel skeleton. |
| Current AGENTS memory routing spec | Current operational contract. |
| Local routing tests | Current test enforcement. |

Decision: `C3RP ROUTER` is a strong design predecessor. `Handshake C3RP` is Phase 2, not MVP.

### Veritas / Evidence Ingestion

| Artifact | Relationship |
|---|---|
| `000133_Claire Main build` | Large older ingest/OCR/CourtListener/capsule export. |
| `FINAL GEMINI CODE for claire` | Earlier partial/broken evidence engine skeleton. |
| Current `claire-veritas-legal` repository | Stronger current implementation. |
| Live dark Veritas | Current approved product path. |

Decision: Veritas local repo remains authoritative. Drive snippets are predecessors and may contain individual ingestion ideas to recover later.

### Manifest / Constitution / Commercial Story

| Artifact | Relationship |
|---|---|
| `CLAIRE ORIGIN MANIFEST` | Early canonical mission/build doctrine. |
| `CLAIRE Manifest Package v2` | Strongest consolidated canonical candidate. |
| `Revised Codemask` | Safe disclosure/code-shaped architecture layer. |
| `DARPA` | Defense-facing architecture/disclosure material. |
| `Out reach` | Technical outreach narrative. |
| `Anduril Lattice Submission` | Concise external submission. |
| `CLAIRE Pitch Deck` | Commercial/investor packaging. |
| `Gemini's Assessment` | Earlier strategic assessment. |

Decision: Manifest Package v2 should be canonical. Other materials should remain private supporting history unless sanitized.

## Duplicates and Superseded Versions

| Earlier artifact | Stronger current/canonical artifact | Recommendation |
|---|---|---|
| `CLAIRE ORIGIN MANIFEST` | `CLAIRE Manifest Package v2` | Keep as history; canonize v2 if approved. |
| Gyro cinematic doc | `Q Insight` | Merge useful explanation into Q Insight appendix. |
| `Claire Diode ARE` | Current `claire_are` + Truth Spine docs | Keep as API history. |
| `ARE Truth Spine L1... v0` | Current `claire_are/truth_spine.py` | Keep as predecessor; do not replace current code. |
| `FINAL GEMINI CODE for claire` | Current Veritas code | Archive/compare for missing extractors. |
| `000011 ClairePay ARE setup` | Current ARE/Truth Spine for memory authority | Keep as product-specific prototype. |
| `AZURE STREAMLIT DEMO UPGRADE 2Claires` | Current Continuity + ARE metadata admission | Keep demo history. |
| `Gemini's Assessment` | Pitch deck + outreach + Manifest v2 | Keep as external assessment only. |

## Risks

- Several Drive artifacts are code-shaped but not executable; importing them directly would regress current implementations.
- Older names such as "Palantir Parser" are superseded and should not be restored as product names.
- Benchmark and performance claims in commercial docs must be tied to raw command output before reuse.
- Defense-facing and patent-sensitive materials should stay private.
- Librarian was not recovered from Drive and should not be inferred from unrelated hits.

