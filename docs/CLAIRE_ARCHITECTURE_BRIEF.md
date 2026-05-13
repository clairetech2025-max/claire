# Claire Architecture Brief: Orientation Before Generation

## Executive Summary

Claire is a governed cognition layer that gives AI persistent memory, deterministic recall, provenance, policy control, and orientation before generation.

Claire separates:

- memory from the model
- governance from generation
- provenance from prompt history
- orientation from raw retrieval
- trace from normal user output

Core thesis:

> Claire orients before she generates.

## The Problem

Normal AI systems rely heavily on transient context windows, probabilistic generation, basic RAG retrieval, tool routing after interpretation, and fragile memory approximations.

That creates risk:

- hallucination
- memory poisoning
- retrieval hijack
- tool misuse
- provenance loss
- lane drift
- authority drift
- external model identity bleed

## Claire's Core Thesis

Generation should happen only after:

1. memory orientation
2. authority check
3. risk classification
4. provenance lookup
5. context stabilization
6. policy gate
7. output mode selection

That is the practical meaning of orientation before generation.

## Gyro ARE and Q Insight

Q Insight is the intellectual spine of Claire's public architecture. Modern AI systems often generate before they orient. Gyro ARE is designed as a pre-generation orientation layer, not a chatbot, not a base model, and not ordinary retrieval.

Gyro evaluates intent, domain, authority, risk, confidence, time, memory access, and output mode. The visible modules are occupied bearings. The unoccupied points are latent paths that may become relevant as context shifts.

## Digital Gravel

Digital Gravel is small raw memory/data material collected from documents, conversations, logs, demos, events, code outputs, external systems, user actions, and trace records.

Digital Gravel is not final memory. It is raw material that needs compaction, provenance, and governance before it should influence important answers.

Status: Prototype / Roadmap, depending on verified code path.

## SweeperBot Compactor

SweeperBot is the proposed process that deduplicates Digital Gravel, groups related records, preserves provenance, detects conflicts, builds durable memory structures, and prevents raw clutter from overwhelming recall.

Status: Roadmap unless implementation is verified in repo.

## Thematic Anchors

Thematic Anchors are durable memory objects that preserve source links, hashes, chronology, meaning, authority, confidence, and trace references.

Status: Prototype / Roadmap unless implementation is verified in repo.

## ARE Memory Spine: BARE / GYRO / FARE

Claire separates time-aware memory into:

- BARE: backward-looking Analog Recall Engine for historical facts, prior state, evidence, and provenance.
- GYRO: present orientation for active plane, authority, risk, and allowed path.
- FARE: forward-looking Analog Recall Engine for likely next context, user need, risk, and memory demand.

Together:

> Past recall -> present orientation -> future projection.

## Provenance and Trace

Claire uses trace IDs, logs, source-bound memory, and replay surfaces to make outputs inspectable. Drive-supplied benchmark evidence also supports an HMAC-style Diode capsule model with tamper detection.

Merkle-style provenance should be treated as roadmap unless full implementation is verified in repo.

## Sentinel / Lycanthrope Governance

Sentinel monitors policy, risk, drift, output mode, and tool authority. Lycanthrope should be described conservatively as a drift-control or containment concept.

Avoid militarized, fantasy, or dangerous language. Governance should sound like control infrastructure, not spectacle.

## Performance Architecture

Claire's performance direction includes low-latency recall, hot-cache indexing, memory-mapped recall, Bloom filters, and index routing.

NVMe pseudo-RAM, zero-copy acceleration, ARM NEON, and VectorIndex should be treated as roadmap unless benchmarked and implemented.

## Current Implementation vs Prototype vs Roadmap

| Layer / Feature | Status | Evidence / Notes |
|---|---|---|
| Claire GUI | Implemented | Live repo contains GUI/server code |
| Voice visualizer | Implemented | Do not change |
| ARE recall proof | Implemented / Prototype | Repo contains ARE servers and query lanes; verify exact live path |
| Trace IDs | Implemented / Prototype | Repo contains trace endpoints and trace IDs |
| Document ingest | Implemented / Prototype | Repo contains upload and ingest paths |
| BARE / GYRO / FARE UI | Prototype | Demo references exist; verify active behavior |
| Digital Gravel | Prototype / Roadmap | Evidence needed |
| SweeperBot | Roadmap | Evidence needed |
| Thematic Anchors | Prototype / Roadmap | Evidence needed |
| Sentinel policy gate | Prototype / Implemented | Sentinel references exist; verify active path |
| Lycanthrope drift control | Roadmap / Prototype | Evidence needed |
| HMAC Diode Capsule | Prototype evidence | Drive benchmark supports; repo verification needed |
| NVMe pseudo-RAM | Roadmap | Evidence needed |
| ARM NEON VectorIndex | Roadmap | Benchmark needed |
| Termux ARE benchmark | Evidence supplied from Drive | Use with environment caveat |
| Dynamic Echo Memory / BackwardARE | Prototype sketch | Do not deploy broken code |

## Why Claire Is Different From RAG

RAG retrieves similar documents. Claire is designed to orient before retrieval dominates, separate memory from generation, preserve provenance, apply governance before output, trace why an answer was shaped, maintain continuity across time, block unauthorized lanes, and use memory as infrastructure rather than prompt stuffing.

## Enterprise Use Cases

- compliance review
- legal memory and evidence review
- financial approval governance
- customer support memory
- enterprise audit trails
- CRM/governance overlay
- applied domain autopilots such as ClairePay prototype
- governed-systems research

## Closing Positioning Statement

Claire is a governed cognition layer that remembers, orients, verifies, and acts under policy.
