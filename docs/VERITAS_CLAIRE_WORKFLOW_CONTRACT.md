# Veritas CLAIRE Workflow Contract

CLAIRE is the typed front door for Veritas Legal.

## Contract

When a user asks for legal work, CLAIRE must:

1. identify the objective
2. choose the legal workflow lane
3. suppress irrelevant memory and research lanes
4. retrieve only supporting evidence
5. ask one concise clarifying question when needed
6. route the user into the correct Veritas surface
7. show progress and evidence provenance
8. never fabricate legal facts
9. never claim court filing, attorney approval, or signed status without explicit action

## Good CLAIRE prompts

- Create a new matter.
- Add this folder to an existing matter.
- Upload the discovery production.
- OCR all scanned documents.
- Extract all dates and build a chronology.
- Find every document mentioning CCR §4331.
- Draft a statement of facts using admitted evidence only.
- Prepare an exhibit index.
- Show contradictions between these declarations.

## Current state

Existing code already supports pieces of this contract:
- `claire_runtime.py` performs governed routing and memory validation.
- `veritas_claire_runtime.py` guides legal workspace use and blocks destructive actions.
- `claire_gui.py` exposes the dark legal workspace, `/ask`, `/veritas-legal/run`, CourtListener routes, and demo traces.

What is still missing is a single canonical front-door implementation that:
- uses a dedicated typed prompt
- emits a structured trace object
- persists replayable demo traces
- cleanly separates demo mode from real workflow mode
- behaves consistently across the dark GUI and the legal workspace

## Rule on memory routing

Reasoning comes first. Memory is support, not a substitute for answering the question. Irrelevant legal hits must not replace direct analysis for architectural or conceptual questions.

## Failure handling

- If recall is unavailable: continue, but mark recall as error.
- If policy validation is unavailable: continue, but mark policy as warning.
- If required fields cannot be constructed: fail closed.

## Replay requirement

Every meaningful workflow trace must be replayable by trace ID. The replay object should include:
- input received
- recall summary
- policy summary
- decision
- output
- step list

## Current verdict

CLAIRE exists as a strong governed runtime, but the product contract is not yet fully centralized into one typed front door. The contract should be implemented without replacing the dark Veritas workspace.
