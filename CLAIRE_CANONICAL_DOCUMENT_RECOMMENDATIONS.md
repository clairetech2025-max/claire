# CLAIRE Canonical Document Recommendations

## Canonical Candidates

| Canonical target | Earliest candidate | Newest candidate | Strongest candidate | Most implemented | Recommendation |
|---|---|---|---|---|---|
| CLAIRE Origin Manifest | `CLAIRE ORIGIN MANIFEST - Litigation Spine...` | `CLAIRE Manifest Package v2 - Review Copy` | `CLAIRE Manifest Package v2 - Review Copy` | Current AGENTS/runtime doctrine partially | Canonize Manifest Package v2 after privacy review. |
| CLAIRE Operator Manifest | `CLAIRE ORIGIN MANIFEST` | `CLAIRE Manifest Package v2 - Review Copy` | `CLAIRE Manifest Package v2 - Review Copy` | AGENTS instructions and demo-mode contract | Canonize v2; add executable acceptance criteria separately. |
| CLAIRE Constitution | `Revised Codemask`, `CLAIRE ORIGIN MANIFEST` | Manifest Package v2 | Manifest Package v2 | AGENTS + current product doctrine | Build a concise repo version from Manifest v2 and Codemask. |
| ARE specification | `Claire Diode ARE` | `ARE Truth Spine L1...` | Current local `claire_are` code plus Truth Spine v0 as lineage | `claire_are/truth_spine.py` | Write canonical spec from current code, not Drive v0. |
| Continuity specification | `Out reach`, `handoff` | Current local `CONTINUITY_ARE_CURRENT_STATE.md` and code | Current local Continuity proof plus `Out reach` | `claire_continuity/core.py`, `session_continuity.py` | Use local code as implementation canon; use Drive docs for product framing. |
| Gyro / Q Insight specification | Gyro cinematic/concept doc | `Q Insight` | `Q Insight` | Local `Gyro` prototype only | Promote `Q Insight` to private canon; implementation remains Phase 2. |
| C3RP specification | `Claire High Level no Military ops` | `Handshake C3RP` | `C3RP ROUTER` for routing, `Handshake C3RP` for scoped sessions | AGENTS routing spec/tests | Canonize routing subset first; handshake later. |
| TrailLink specification | `Claire High Level no Military ops` | Manifest/Outreach references | `Claire High Level no Military ops` plus legacy `traillink.py` code | Legacy ARE/Spectacle clones | Recover into separate TrailLink design doc before integration. |
| Veritas specification | `FINAL GEMINI CODE`, `000133_Claire Main build` | Veritas product directives and current repo | Current Veritas repo plus product directives | Live dark Veritas + tests | Keep current Veritas repo authoritative; Drive files are predecessors. |
| Commercialization brief | `Gemini's Assessment` | Pitch deck / Anduril / Marketplace | Pitch deck for broad story, Anduril for concise technical note | N/A | Keep private; attach evidence appendix before external use. |

## Recommended Canon Set

### 1. CLAIRE Manifest Package v2

Use as the private canonical doctrine document for:

- CLAIRE as the machine, not a chatbot.
- Truth outside the model.
- Externalized memory and authority.
- Governed recall, lineage, and constrained action.

Action: PROMOTE TO CANON after redaction and version stamping.

### 2. Q Insight

Use as the private canonical Gyro/Q Insight architecture.

Action: PROMOTE TO CANON for Phase 2 design. Do not implement full Gyro in Continuity MVP.

### 3. Current `claire_are` Source

Use the current code as the canonical ARE/Truth Spine implementation.

Action: generate a spec from the real code and benchmark evidence. Do not use older Drive snippets as source of truth.

### 4. Current Continuity MVP Source

Use `claire_continuity/core.py` and `session_continuity.py` as implementation canon for portable capsules.

Action: add Insight Records and documentation only after current local proof remains passing.

### 5. C3RP ROUTER

Use as design canon for context-lane selection and memory relevance gating.

Action: incorporate into CLAIRE core routing doctrine and add capsule routing hints in Continuity Phase 2.

## Documents To Keep Private

- `CLAIRE Manifest Package v2 - Review Copy`
- `Q Insight`
- `DARPA`
- `Revised Codemask`
- `Anduril Lattice Submission - CLAIRE Final Email`
- `CLAIRE Pitch Deck - Polished Working Draft`
- `Claire High Level no Military ops`
- `ARE Truth Spine L1 Deterministic Memory Kernel - v0`

Reason: patent-sensitive architecture, commercial strategy, security posture, or proprietary implementation detail.

## Documents Suitable For Sanitized Public Use Later

- A reduced ARE/Truth Spine public specification generated from current code.
- A sanitized Continuity overview focused on portable handoff artifacts.
- A cleaned Marketplace/Spectacle README only after private code boundaries are resolved.
- A Veritas capability matrix that avoids private legal data and unsupported claims.

## Recommended Next Canon Action

Create one private repo document:

`docs/CLAIRE_PRODUCT_CONSTITUTION.md`

Source it from:

- `CLAIRE Manifest Package v2 - Review Copy`
- `Revised Codemask`
- current AGENTS system contract
- current Continuity doctrine

Do not include defense-facing claims, benchmark claims, contact data, or patent-sensitive implementation details in the first public version.

