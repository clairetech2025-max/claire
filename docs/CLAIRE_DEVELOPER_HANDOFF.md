# Claire Developer Handoff

## Purpose

This file protects the Claire demo, identity, and architecture during future Codex or developer work.

## Do Not Change Without Explicit Approval

- GUI layout
- voice visualizer
- visual identity
- existing live demos
- ARE architecture
- Sentinel/governance core
- memory systems
- Session Capsule / continuity systems
- routing architecture
- trace systems
- backend APIs
- voice pipeline
- websocket infrastructure
- latency-sensitive systems
- secrets/env files
- production memory files

## Claire Identity

Claire is a governed cognition layer built around deterministic recall, persistent orientation, provenance, auditability, policy control, and low-latency memory.

Claire should not be turned into a generic chatbot, CRM copilot, Salesforce clone, or standard RAG wrapper.

Project Lantern Relay / Session Capsule continuity should be treated as an additive front-end handoff layer for ARE. It preserves operational restart state; it does not replace ARE, FARE, BARE, Sentinel, TrailLink, C3RP, Diode, or trace replay.

## Presentation Rule

Claire should answer the user's question first. Architecture should be implied first and explained second unless the user asks for detail.

## Memory Routing Rule

Do not substitute retrieval for a direct answer. If the user asks a conceptual, philosophical, technical, or mixed reasoning question, answer directly and use memory only as support.

## Continuity Capsule Rule

If Session Capsules are implemented, they must capture structured operational state rather than raw transcript dumps. Required concepts include current objective, changed files or artifacts, failures, restore points, next safe step, and do-not-repeat notes.

Capsules should re-orient the next session before work resumes. They should not authorize real-world action, bypass Sentinel, override lane governance, or replace trace persistence.

## Demo Mode Rule

Demo scenarios should preserve:

observe -> recall -> validate -> decide -> output -> trace -> replay

All real-world actions remain simulated unless an explicitly protected human approval path is used.

## Business Ops Rule

Allowed without protected approval:

- drafting copy
- preparing packaging checklists
- generating release notes
- producing demo traces and reports
- reading local project state

Requires protected approval:

- publishing
- uploading paid products
- changing prices
- emailing or posting
- spending money
- restarting services
- changing Azure/Gumroad account state

## Benchmark Rule

Drive benchmark files are treated as real supplied evidence. Public claims must still state the tested environment and avoid universal claims.

## Continuity Proof Rule

The `PROOF_OF_CONTINUITY - Copy-2.md` file is now authorized by Lucius Prime as Claire-facing continuity material for explanation in partner/Microsoft writing. Project Lantern Relay / Session Capsule Protocol is a Claire-origin continuity concept invented by Lucius Prime with Codex build assistance. Treat it as prototype proof until the implementation and tests are present in this repo and verified locally.
