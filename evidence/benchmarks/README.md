# Claire Benchmark Evidence

## Purpose

This folder is reserved for controlled benchmark source artifacts, reproducible scripts, CSV outputs, and generated reports.

The current benchmark numbers in `docs/CLAIRE_BENCHMARK_SUMMARY.md` are based on Drive-supplied source PDFs that the project owner has confirmed are true.

## Current Source Artifacts

| Artifact | Source | Status | Notes |
|---|---|---|---|
| `ARE Test- (2)(4).pdf` | Google Drive | Source supplied externally | Termux / Android ARM64 ARE + Diode benchmark evidence |
| `BENCHMARK TESTS(4).pdf` | Google Drive | Source supplied externally | Polished ARE / Diode benchmark report |
| `Dynamic echo memory(5).pdf` | Google Drive | Source supplied externally | Early BARE / backward memory prototype sketch |

## Current Public-Safe Claim

> On local Android/ARM64 hardware running Termux, Claire's ARE/Diode benchmark demonstrated sub-millisecond deterministic recall, HMAC verification, and tamper detection under the tested conditions.

## Needed For Partner-Grade Proof

- copy sanitized source PDFs into this folder
- add a reproducible benchmark script
- emit raw CSV results
- include machine specs
- include Git commit hash
- add chart images
- add a direct local/vector/cloud-RAG comparison
- add an Azure/server benchmark run

## Claim Boundaries

Do not use these benchmarks to claim:

- universal production performance
- superiority over all RAG systems in all contexts
- full Merkle-DAG provenance
- cryptographic non-repudiation
- defense readiness
- impossible-to-hack security
- hallucination elimination
