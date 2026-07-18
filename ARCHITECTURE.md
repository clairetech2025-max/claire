# Architecture

CLAIRE is maintained as one governed runtime with five public engines. The public
engines are adapters and coordination boundaries; they do not erase the existing
internal modules.

## Engines

- Continuity: ARE and Ember handoff state.
- Temporal: Chronos and temporal orientation.
- Cognitive: Recognition Rail, Q Insight 360x360, and Gyro.
- Provenance: TrailLink and Truth Spine.
- Governance: 3CRP, Sentinel, EchoShield, Lycanthrope, and SweeperBots.

## Current Runtime Order

The live message path is preserved and guarded in stages:

1. user input and temporal turn start
2. Diode redaction and temporal resolution
3. 3CRP ingress and C3RP lane routing
4. authority handshake
5. Gyro, ARE recall, Recognition Rail, and Q Insight
6. post-Gyro 3CRP authorization
7. model authorization and invocation
8. EchoShield and Sentinel memory-write review
9. 3CRP memory-write authorization
10. durable ARE commit only when authorized
11. 3CRP egress
12. output release and Truth Spine turn seal

## Memory Governance

Generated model output is not verified evidence. Durable memory writes must pass
EchoShield classification, Sentinel authorization, and 3CRP memory-write
authorization before ARE mutation.

## Shadow Mode

`CLAIRE_CORE_SHADOW_MODE=true` lets the core wrapper report capability and parity
signals without replacing the current authoritative runtime path.
