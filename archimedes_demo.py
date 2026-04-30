"""Controlled Project ARCHIMEDES demo content.

This module contains presentation-safe, deterministic material only. It does
not execute real-world operations, task systems, or destructive actions.
"""

from __future__ import annotations


ARCHIMEDES_ALIASES = {
    "claire archimedes demo",
    "archimedes demo",
    "project archimedes demo",
    "claire project archimedes demo",
    "darpa archimedes demo",
    "claire darpa demo",
}


def is_archimedes_alias(cleaned: str) -> bool:
    return cleaned in ARCHIMEDES_ALIASES or "archimedes" in cleaned


def archimedes_identity() -> str:
    return (
        "Claire Executive Mode running Project ARCHIMEDES: a controlled DARPA-facing "
        "source-manifest, passive correlation, and evidence-package demonstration with "
        "governed recall, Gyro orientation, Sentinel validation, Diode lineage, "
        "immune-style containment, and replayable trace."
    )


def archimedes_decision() -> str:
    return (
        "Run a controlled ARCHIMEDES evaluation: intake the project/source manifest, "
        "classify evidence assets, simulate passive multi-signal correlation, validate "
        "presentation boundaries, seal a Diode trace, and emit a replayable DARPA "
        "briefing package."
    )


def archimedes_output() -> str:
    return (
        "Project ARCHIMEDES Demo result: Claire treated the package as a controlled "
        "DARPA presentation artifact, not an operational system. The demo normalized "
        "the source-manifest concept, separated claim, code, evidence, governance, "
        "passive correlation, and replay lanes, validated the request through Sentinel, "
        "and sealed the result into a Diode-style trace. The output is a presentation-safe "
        "proof spine: what was ingested, what was classified, how weak signals were "
        "correlated into confidence-scored cues, what was allowed, what was withheld "
        "from operational framing, and how the decision path can be replayed."
    )


def archimedes_fields() -> dict:
    return {
        "identity": archimedes_identity(),
        "decision": archimedes_decision(),
        "output": archimedes_output(),
        "lane": "archimedes_darpa_evaluation",
    }


def archimedes_artifacts() -> list[dict]:
    return [
        {
            "title": "CONTROLLED MANIFEST INTAKE",
            "summary": "ARCHIMEDES starts from a project/source manifest rather than a loose chat answer.",
            "items": [
                "SOURCE_INDEX: documents, code blocks, PDFs, and repo references are treated as separate assets",
                "CLAIM_LEDGER: technical claims are separated from implementation evidence",
                "BUILD_SURFACE: Claire GUI remains the presentation surface, not the core of ARCHIMEDES",
                "IP_FOUNDATION: provisional-patent material is treated as source evidence, not unsupported certification",
                "SCOPE_BOUNDARY: evaluation/demo output only; no live operational execution",
            ],
        },
        {
            "title": "PATENT FOUNDATION MAP",
            "summary": "The demo maps provisional-patent concepts into inspectable software lanes.",
            "items": [
                "EXTERNALIZED_MEMORY: the model consumes curated context but does not own the record",
                "PROVENANCE_VERIFICATION: source lineage and content hashes travel with evidence",
                "ONE_WAY_INTEGRITY: Diode / WriteBarrier prevents generated output from rewriting upstream truth",
                "MODEL_AGNOSTIC_GOVERNANCE: Sentinel and Trace remain outside the model path",
            ],
        },
        {
            "title": "EVIDENCE PACKAGE MODEL",
            "summary": "The demo converts scattered project material into a DARPA-readable proof package.",
            "items": [
                "ARCHITECTURE: ARE, Gyro, Sentinel, Diode, Veritas, CodeMask, and Trace are mapped as lanes",
                "SOURCE QUALITY: each asset is classified by role, confidence, and support value",
                "IMPLEMENTATION GAP: claims without local code are marked as presentation claims",
                "REPLAY VALUE: every output is linked to trace_id and report evidence",
            ],
        },
        {
            "title": "PASSIVE CORRELATION LAYER",
            "summary": "ARCHIMEDES frames passive cueing as evidence fusion, not command execution.",
            "items": [
                "SIGNAL_INPUTS: simulated RF, optical, telemetry, timing, geomagnetic, and observer metadata",
                "FUSION_OUTPUT: confidence-scored geospatial cue hypotheses with provenance",
                "NO_ACTION_PATH: cues do not trigger live tasking, targeting, suppression, or kinetic handoff",
                "REVIEW_MODE: output is an operator/evaluator evidence package for human review",
            ],
        },
        {
            "title": "GYRO ORIENTATION FIELD",
            "summary": "Gyro selects the cognitive bearing before recall or generation dominates the answer.",
            "items": [
                "BARE: reverse recall checks prior capsules, traces, and source lineage",
                "GYRO: active planes classify intent, domain, authority, risk, provenance, and output mode",
                "FARE: forward recall prepares next-risk and next-evidence expectations",
                "Q_INSIGHT: dormant bearings can be activated, blocked, quarantined, or routed under trace",
            ],
        },
        {
            "title": "SENTINEL PRESENTATION GATE",
            "summary": "Sentinel keeps the demonstration in decision-support and evaluation framing.",
            "items": [
                "NO TASKING: no live command, actuator path, or autonomous execution",
                "NO DESTRUCTIVE ACTION: duress, shred, wipe, or bricking concepts become quarantine-only proof fields",
                "NO SECRET CLAIMS: protected keys, credentials, and private internals are not surfaced",
                "HUMAN REVIEW: output is a briefing artifact for accountable human evaluation",
            ],
        },
        {
            "title": "AI IMMUNE-SYSTEM MAP",
            "summary": "The patent-aligned immune analogy becomes concrete runtime containment lanes.",
            "items": [
                "BEHAVIORAL IMMUNE LAYER: Sentinel checks prompt pressure, lane drift, and authority drift",
                "MEMORY IMMUNE LAYER: Diode and hash-chain verification detect tampering or mutation",
                "INFORMATION IMMUNE LAYER: Veritas preserves source lineage before model interpretation",
                "RECOVERY IMMUNE LAYER: suspicious paths are quarantined or rerouted instead of executed",
            ],
        },
        {
            "title": "DIODE TRACE LINEAGE",
            "summary": "ARCHIMEDES uses forward-only proof records for review and replay.",
            "items": [
                "TRACE_INPUT: manifest prompt, recall summary, policy result, decision, and output",
                "TRACE_SEAL: hash-linked capsule demonstrates integrity of the presentation run",
                "TRACE_REPLAY: /trace/{trace_id} retrieves the stored evidence object",
                "REPORT_READY: the result can become a presentation page without changing Claire core",
            ],
        },
        {
            "title": "DARPA BRIEFING RESULT",
            "summary": "The first demo proves governance, traceability, and evidence discipline.",
            "items": [
                "What it proves: Claire can turn a complex project archive into a controlled evidence and cue package",
                "What it does not claim: finished hardware, live tasking, autonomous execution, or deployed authority",
                "Next build step: manifest parser plus deterministic passive-correlation scorecards",
                "Integration path: one Claire GUI button, one demo scenario, one replayable trace",
            ],
        },
    ]


def archimedes_policy_summary() -> str:
    return (
        "Allowed as a controlled DARPA-facing ARCHIMEDES presentation demo: source-manifest "
        "intake, evidence classification, passive correlation cueing, Gyro orientation, Sentinel "
        "governance, Diode lineage, immune-style containment, report assembly, and trace replay "
        "are demonstrated as decision-support artifacts only."
    )


def archimedes_policy_rules() -> list[str]:
    return [
        "darpa_presentation_mode",
        "source_manifest_evaluation",
        "passive_correlation_simulation",
        "gyro_orientation_required",
        "immune_containment_only",
        "decision_support_only",
        "no_operational_tasking",
        "trace_replay_required",
    ]


def archimedes_passive_correlation() -> dict:
    return {
        "status": "simulated",
        "name": "ARCHIMEDES Passive Correlation Layer",
        "summary": "Combines weak simulated observations into confidence-scored cue hypotheses with provenance.",
        "inputs": [
            {"lane": "rf", "value": "bearing-only emitter observation", "confidence": 0.71},
            {"lane": "optical", "value": "low-resolution silhouette / motion cue", "confidence": 0.64},
            {"lane": "telemetry", "value": "observer timing and platform-state metadata", "confidence": 0.82},
            {"lane": "geomagnetic", "value": "terrain-consistent navigation anchor", "confidence": 0.77},
            {"lane": "history", "value": "ARE prior-pattern capsule match", "confidence": 0.74},
        ],
        "fusion": {
            "method": "weighted provenance-preserving cue fusion",
            "cue_class": "geospatial_hypothesis",
            "confidence": 0.78,
            "output_mode": "operator_review_package",
        },
        "blocked_paths": [
            "live_tasking",
            "autonomous_targeting",
            "kinetic_handoff",
            "jamming_or_suppression",
            "destructive_node_action",
        ],
    }


def archimedes_gyro_orientation() -> dict:
    return {
        "intent": "darpa_architecture_and_passive_correlation_demo",
        "domain": "ai_governance_runtime",
        "authority": "local_architecture_docs_and_provisional_material",
        "risk": "avoid_operational_execution_or_overclaimed_certification",
        "output_mode": "evidence_package",
        "temporal_modes": ["BARE", "GYRO", "FARE"],
        "allowed_lanes": [
            "architecture",
            "passive_correlation",
            "provenance",
            "governance",
            "trace_replay",
        ],
        "blocked_lanes": [
            "live_tasking",
            "autonomous_action",
            "weaponization",
            "external_model_identity",
            "unsupported_trl_or_clearance_claims",
        ],
        "active_planes": [
            {
                "plane": "intent",
                "bearing_degrees": 0,
                "bearing_class": "direct_architecture_proof",
                "confidence": 0.91,
            },
            {
                "plane": "risk",
                "bearing_degrees": 135,
                "bearing_class": "pressure_test_and_containment",
                "confidence": 0.84,
            },
            {
                "plane": "provenance",
                "bearing_degrees": 270,
                "bearing_class": "source_lineage_and_trace",
                "confidence": 0.88,
            },
            {
                "plane": "time",
                "bearing_degrees": 315,
                "bearing_class": "bare_gyro_fare_cycle",
                "confidence": 0.82,
            },
        ],
        "resolved_path": "controlled_passive_correlation_evidence_package",
        "drift_warning": False,
        "rationale": "DARPA-facing architecture demo with passive cueing value; keep output in governed evaluation and replay lanes.",
    }


def archimedes_ai_immune_map() -> dict:
    return {
        "status": "active",
        "summary": "Immune-system framing maps to concrete containment and integrity controls.",
        "layers": [
            {
                "layer": "behavioral",
                "component": "Sentinel",
                "function": "detects lane drift, prompt pressure, and authority drift",
            },
            {
                "layer": "memory_integrity",
                "component": "Diode / WriteBarrier",
                "function": "prevents generated output from rewriting source memory",
            },
            {
                "layer": "information_integrity",
                "component": "Veritas",
                "function": "normalizes source evidence with lineage and hash anchors",
            },
            {
                "layer": "recovery",
                "component": "Quarantine",
                "function": "reroutes suspicious or contaminated paths into review-only mode",
            },
        ],
    }


def archimedes_patent_foundation() -> dict:
    return {
        "status": "mapped",
        "summary": "Local provisional-patent material supports the governed-memory and provenance architecture lanes.",
        "concepts": [
            "externalized memory outside model weights and transient prompt context",
            "immutable or append-only truth/provenance records",
            "one-way directional integrity between source memory and model output",
            "independent governance outside the model",
            "traceable decision reconstruction for audit and replay",
            "model-agnostic deployment surface",
        ],
        "caution": "Patent/provisional status is shown as source evidence only; legal scope and claims require formal patent review.",
    }


def archimedes_live_proof() -> dict:
    return {
        "status": "active",
        "summary": "ARCHIMEDES proof spine is active for controlled passive-correlation presentation output.",
        "manifest_lane": "source documents, code blocks, PDFs, repo references",
        "classification_lane": "claim, evidence, implementation gap, governance rule, replay artifact",
        "patent_lane": "externalized memory, one-way integrity, provenance, governance, traceability",
        "passive_correlation_lane": "simulated weak-signal fusion into confidence-scored cue hypotheses",
        "gyro_lane": "multi-plane orientation before recall, tool use, persistence, or generation",
        "immune_lane": "Sentinel, Diode, Veritas, and quarantine controls mapped as runtime immunity",
        "sentinel_lane": "presentation-safe decision-support validation",
        "diode_lane": "forward-only trace capsule for replay and review",
        "passive_correlation": archimedes_passive_correlation(),
        "gyro_orientation": archimedes_gyro_orientation(),
        "ai_immune_map": archimedes_ai_immune_map(),
        "patent_foundation": archimedes_patent_foundation(),
    }
