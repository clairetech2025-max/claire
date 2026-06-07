# Claire Proof Layer

## Purpose

This document collects what Claire can credibly show today and what still needs repo-grade verification. The goal is evidence over hype.

## What the Live Demo Proves

The live Claire codebase includes surfaces for:

- conversational response
- ARE-oriented memory paths
- document upload / ingest
- trace IDs
- demo payloads
- proof/status panels
- public scenario demos

Exact production status should be verified per route before public claims are expanded.

## What ARE Recall Proof Shows

Repo evidence shows ARE server components and query lanes. Drive benchmark evidence shows a capsule recall model with deterministic addressing, SQLite storage, HMAC verification, and tamper detection under tested local Android / ARM64 Termux conditions.

## What Trace / Status / Pipeline Prove

Trace IDs and replay endpoints appear in the repo. Public claims should remain conservative until trace persistence, replay, and exact request lifecycle are verified against the active deployed service.

## What Session Capsule Proof Shows

Unique room name: `PROJECT_LANTERN_RELAY`

Origin: Claire-origin continuity concept invented by Lucius Prime with Codex build assistance.

The proof document describes a local Session Capsule Protocol prototype. The reported prototype creates structured capsules, validates required continuity fields, saves JSON and Markdown artifacts, indexes saved capsules, recalls the best capsule for an operational query, and preserves failures, restore points, next safe steps, and do-not-repeat notes.

Reported test evidence:

- `13 passed in 0.15s`
- capsule creation
- spoken handoff preservation
- validation
- JSON persistence
- Markdown persistence
- indexing
- recall
- do-not-repeat preservation
- full round trip

Public-safe wording:

> Claire's Project Lantern Relay prototype demonstrates structured session handoff, local persistence, recall, and do-not-repeat preservation under tested local conditions.

Do not claim this is live production continuity until the prototype is integrated into this repo and verified against the active Claire service.

## What Uploaded Benchmark Evidence Shows

Drive-supplied PDFs report:

- 50,000 capsules inserted
- 7,517.62 ms load time
- 6,651 inserts/sec
- sub-millisecond ARE recall
- sub-millisecond HMAC verification
- sub-millisecond recall + verify
- tamper detection after mutation
- scale tests up to 1,000,000 capsules

## What Tamper Detection Proves

The benchmark shows a mutation failing verification after the original payload passed. Public wording:

> The uploaded benchmark shows mutation detection in the tested capsule model.

Do not claim cryptographic perfection or impossible-to-hack security.

## What the Scale Curve Suggests

The scale curve suggests deterministic local recall remained sub-millisecond across 50,000, 200,000, and 1,000,000 capsule tests under the reported conditions.

This suggests a strong low-latency memory architecture. It does not prove every deployment will perform the same way.

## ClairePay Applied Prototype

ClairePay can be described as an applied prototype concept showing how ARE could remember billers, payment methods, prior outcomes, and user preferences to support safer next actions.

Do not describe it as production bill-pay unless production controls, compliance, and protected approval paths are implemented.

## Evidence Table

| Claim | Evidence Found | Evidence Needed | Public-Safe Wording |
|---|---|---|---|
| Claire has persistent memory | ARE service references, local memory files, JSONL-style records | confirm active repo files and deployed path | "Claire uses an external memory layer rather than relying only on context windows." |
| Claire supports deterministic recall | Drive Termux ARE benchmark | reproducible repo script | "Claire's ARE benchmark demonstrates sub-millisecond deterministic recall under tested local conditions." |
| Claire verifies memory integrity | Drive HMAC verification benchmark | confirm implementation file | "Claire's benchmark includes HMAC-based capsule verification." |
| Claire detects tampering | Drive tamper test passed | test script and output artifact | "The uploaded benchmark shows mutation detection in the tested capsule model." |
| Claire is faster than cloud RAG calls | Local recall benchmark suggests speed advantage | direct RAG comparison test | "Claire is designed for low-latency deterministic recall; benchmark evidence should be displayed where available." |
| Claire has traceability | trace UI/routes/log references | replay test | "Claire exposes decision traces and proof surfaces." |
| Claire can preserve operational continuity | Project Lantern Relay / Session Capsule proof document | integrate prototype into repo and run tests locally | "Claire's Project Lantern Relay prototype demonstrates structured session handoff and restart-state recall under tested local conditions." |

## Benchmark Evidence Still Needed

- reproducible repo script
- raw CSV output
- machine specs
- Git commit hash
- benchmark artifact folder
- direct RAG comparison
- Azure/server benchmark
- verification of HMAC implementation in active repo
- Session Capsule prototype folder or imported test artifacts
- cold-start vs capsule-restart demo output

## Implementation Evidence Codex Should Verify

- ARE endpoints
- trace/replay endpoints
- document ingest route
- Sentinel policy gate
- BARE/GYRO/FARE routing
- benchmark scripts
- Diode/HMAC implementation
- Session Capsule creation, validation, persistence, indexing, and recall
- public proof/status surfaces
