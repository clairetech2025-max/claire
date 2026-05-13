# Claire ARE / Diode Benchmark Summary

## Executive Summary

Drive-supplied benchmark evidence shows Claire's ARE / Diode memory path performing deterministic local recall, HMAC-style verification, and tamper detection under tested Android / ARM64 Termux conditions.

Public-safe claim:

> On local Android/ARM64 hardware running Termux, Claire's ARE/Diode benchmark demonstrated sub-millisecond deterministic recall, HMAC verification, and tamper detection under the tested conditions.

This evidence is strong, but it should not be generalized into universal production performance without reproduced repo scripts, machine specs, CSV output, and commit-linked reports.

## Test Environment

| Field | Value |
|---|---|
| Source | Drive-supplied benchmark PDFs |
| Environment | Termux |
| Hardware / OS class | Android / ARM64 |
| Runtime | Python |
| Storage | Local SQLite |
| Cloud dependency | None reported |
| GPU dependency | None reported |

## System Under Test

The benchmark describes:

- capsule-based memory units with immutable payloads
- SQLite-backed append-only storage
- deterministic key addressing
- HMAC-SHA256 integrity verification
- diode-style write-once / verify-many behavior
- explicit separation of recall, verification, and end-to-end recall + verify paths

## Load Performance

| Capsules | Load Time | Insert Rate |
|---:|---:|---:|
| 50,000 | 7,517.62 ms | 6,651 inserts/sec |

## Latency Results

| Test | p50 | p95 | p99 | Notes |
|---|---:|---:|---:|---|
| ARE recall only | 0.042 ms / 0.052 ms | 0.057 ms / 0.160 ms | 0.122 ms / 0.273 ms | Termux local SQLite, values vary by run/report |
| HMAC verify only | 0.075 ms | 0.093 ms | 0.170 ms | HMAC over SHA256(payload) |
| Recall + verify | 0.152 ms | 0.221 ms | 0.276 ms | End-to-end local path |

Two benchmark artifacts report slightly different recall p95/p99 values. Treat them as separate runs or report variants rather than hiding the difference.

## Scale Curve

| Capsules | Recall p50 | Recall p99 | E2E p50 | E2E p99 |
|---:|---:|---:|---:|---:|
| 50,000 | 0.052 ms | 0.160 ms | 0.146 ms | 0.273 ms |
| 200,000 | 0.053 ms | 0.234 ms | 0.147 ms | 0.629 ms |
| 1,000,000 | 0.054 ms | 0.182 ms | 0.148 ms | 0.419 ms |

## Tamper Detection

| Check | Result |
|---|---|
| Original verify | True |
| After mutation | False |
| Outcome | Tamper detected |

## Public-Safe Interpretation

The benchmark supports the claim that Claire's ARE / Diode design can perform very fast local deterministic recall and integrity verification under the tested conditions.

It does not yet prove universal production performance, superiority over all RAG systems, full Merkle-DAG provenance, full enterprise validation, or defense readiness.

## Claims Not Supported Yet

- universal production performance
- all-RAG comparison superiority
- cryptographic non-repudiation
- full Merkle-DAG provenance
- full enterprise validation
- full defense readiness
- "eliminates hallucinations"
- "impossible to hack"

## Recommended Next Benchmarks

- reproduce from repo scripts
- include Git commit hash
- emit CSV and markdown reports
- run on Azure VM
- run on laptop hardware
- test 5 million capsules
- compare against local vector search
- compare against cloud RAG call
- include machine specs
- generate chart images
