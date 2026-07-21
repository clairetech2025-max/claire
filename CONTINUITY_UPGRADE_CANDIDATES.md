# Continuity Upgrade Candidates

Continuity product goal: preserve the accumulated intelligence created by long-term human-AI collaboration.

The system should preserve:

1. What we know.
2. Why we believe it.
3. How we work together.
4. What we learned together.

## Candidate Classification

| Component | Classification | Reason tied to Continuity |
|---|---|---|
| Diode export/redaction gate | MVP REQUIRED | Prevents private trust notes, secrets, legal matter data, and local infrastructure details from leaking into portable artifacts. |
| Provenance hashing | MVP REQUIRED | Lets another AI or human verify that a handoff artifact has not changed. |
| Private/shareable separation | MVP REQUIRED | Core safety boundary for portable cross-AI handoffs. |
| Collaboration Profile | MVP REQUIRED | Preserves how Steve and the AI work together without preserving an AI identity. |
| Session Capsule Protocol | MVP REQUIRED | Carries current state, restore point, next safe step, failures, and do-not-repeat information. |
| Insight Records | MVP REQUIRED, simple form | Preserves what was learned and why it matters; should include source/basis fields before becoming complex. |
| ARE / Truth Spine provenance | MVP OPTIONAL | Valuable for local verification and authority, but receiving AIs must not require ARE. |
| Drift detection | MVP OPTIONAL | Useful to detect loss of working style or project direction; start lightweight. |
| Evidence confidence labels | MVP OPTIONAL | Helps preserve "why we believe it"; use simple labels first. |
| Correction history | MVP OPTIONAL | Helps prevent repeating errors; can start as `do_not_repeat` and later become structured. |
| C3RP context-lane selection | PHASE 2 | Prevents irrelevant memory pollution; add as capsule routing hints before full router integration. |
| TrailLink lineage | PHASE 2 | Strong for capsule ancestry, but current prior-hash chaining covers MVP lineage. |
| Gyro orientation snapshot | PHASE 2 | Useful compact "where are we pointed" summary, but full Q Insight is larger than MVP. |
| Sentinel admission rules | PHASE 2 | Valuable for policy-gated exports/admissions, but current redaction/validation gate is sufficient for MVP. |
| Contradiction checking | PHASE 2 | Valuable for correcting memory, but not necessary for first portable handoff. |
| Librarian | UNKNOWN UNTIL CODE REVIEW | Drive did not provide a reliable Librarian spec; prior GitHub audit says review private repo first. |
| ARV | UNKNOWN UNTIL CODE REVIEW | Not enough Drive evidence in this pass to define MVP role. |
| Gyro full orientation field | KEEP SEPARATE | Strong architecture, too large for Continuity MVP. |
| Veritas evidence engine | KEEP SEPARATE | Continuity can link to Veritas outputs but should not become legal evidence ingestion. |

## Smallest Valuable Architecture

The MVP should remain:

- Canonical private JSON and Markdown capsule.
- Shareable redacted JSON and Markdown capsule.
- Compact handoff Markdown for another AI.
- Deterministic canonical serialization.
- Stable hash and local verification.
- Optional metadata-only ARE admission.
- Provenance manifest tying artifacts, hash, and ARE record.

## Add Next

1. Add explicit `InsightRecord` fields:
   - `claim`
   - `why_we_believe_it`
   - `basis`
   - `source_refs`
   - `confidence`
   - `status`: extracted, inferred, disputed, user-confirmed, corrected

2. Add simple routing hints:
   - `allowed_lanes`
   - `blocked_lanes`
   - `current_priority`
   - `off_limits_context`

3. Add correction history:
   - `mistake`
   - `correction`
   - `evidence`
   - `do_not_repeat`

4. Add optional ARE adapter interface:
   - keep capsule artifacts canonical
   - admit only metadata and hashes by default
   - allow future Truth Spine/Librarian implementation changes

5. Add behavioral tests from `handoff`:
   - ambiguity handling
   - restraint
   - technical handoff
   - investor/commercial handoff
   - governance language

## Do Not Add Yet

- Full Gyro/Q Insight orientation engine.
- Librarian integration.
- TrailLink service integration.
- Veritas ingestion or legal matter storage.
- Public nginx routes.
- UI.
- Authentication/session handshake.
- Vector database.
- Model-specific memory hooks.

## Why This Is Better Than Existing Alternatives

| Alternative | Limitation | Continuity advantage |
|---|---|---|
| Chat transcript export | Too long, noisy, unstructured, and hard for another AI to operationalize. | Capsule preserves state, basis, next step, failures, and collaboration contract. |
| Long system prompt | Mixes instructions, facts, and private context with no provenance or redaction boundary. | Capsule separates private/shareable content and hashes artifacts. |
| Ordinary AI memory | Platform-bound and opaque. | Capsule is portable across ChatGPT, Claude, Gemini, Codex, and local systems. |
| Vector database | Good for retrieval, weak for authority and handoff. | Capsule is human-readable and has deterministic hash/provenance. |
| Project summary document | Useful but manually inconsistent and usually lacks validation/redaction. | Capsule is schema-backed, verified, and repeatable. |

## Top Five Continuity Additions From Drive Recovery

1. Promote Manifest Package v2 language into the Continuity product constitution.
2. Add Insight Records so capsules preserve "why we believe it," not just "what happened."
3. Add C3RP-style lane hints to prevent future AIs from pulling the wrong context.
4. Formalize Diode-style export gates around redaction and private/shareable separation.
5. Add lightweight correction history before full contradiction detection.

