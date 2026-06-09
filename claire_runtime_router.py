from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable

from intent_classifier import classify_query
from lane_router import extract_candidates
from memory_eligibility import MemoryEligibility, MemoryMode, determine_memory_eligibility
from relevance_gate import compact_candidate, gate_retrieval_candidates
from write_barrier import writeback_decision


ProviderGenerate = Callable[[str], str]


@dataclass
class RouteResult:
    source: str
    reply: str
    trace_payload: dict[str, Any]
    writeback_policy: dict[str, Any]


def normalize_input(text: str) -> dict[str, Any]:
    raw = str(text or "")
    normalized = re.sub(r"\s+", " ", raw.replace("\r\n", "\n").replace("\r", "\n")).strip()
    cleaned = " ".join(re.sub(r"[^a-z0-9\s']", " ", normalized.lower()).split())
    return {
        "text": normalized,
        "cleaned": cleaned,
        "payload_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "normalized_at": datetime.utcnow().isoformat() + "Z",
    }


def provisional_orientation(normalized: dict[str, Any]) -> dict[str, Any]:
    cleaned = normalized.get("cleaned", "")
    return {
        "status": "provisional",
        "source": "user_text",
        "modality": "text",
        "risk_hint": "elevated" if _is_safety_sensitive(cleaned) else "normal",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


def c3rp_classify(normalized: dict[str, Any], orientation: dict[str, Any]) -> dict[str, Any]:
    text = normalized.get("text", "")
    cleaned = normalized.get("cleaned", "")
    legacy = classify_query(text).to_dict()
    lane = _phase_one_lane(cleaned, legacy)
    allowed_lanes = list(legacy.get("allowed_lanes") or [])
    suppressed_lanes = list(legacy.get("suppressed_lanes") or [])
    if lane in {"CONCEPTUAL", "CASUAL"}:
        for blocked in ["legal_case", "personal_context", "random_document_hits"]:
            if blocked not in suppressed_lanes:
                suppressed_lanes.append(blocked)
    return {
        "lane": lane,
        "legacy_intent": legacy,
        "allowed_lanes": allowed_lanes,
        "suppressed_lanes": suppressed_lanes,
        "classified_at": datetime.utcnow().isoformat() + "Z",
    }


def evaluate_authority(normalized: dict[str, Any], lane_result: dict[str, Any]) -> dict[str, Any]:
    cleaned = normalized.get("cleaned", "")
    protected_action = any(
        marker in cleaned
        for marker in [
            "publish",
            "upload",
            "change price",
            "email",
            "post ad",
            "spend money",
            "restart service",
            "delete all",
        ]
    )
    return {
        "authority": "protected_approval_required" if protected_action else "normal_chat",
        "restricted": protected_action or lane_result.get("lane") == "SAFETY_SENSITIVE",
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }


def build_governed_prompt(normalized: dict[str, Any], lane_result: dict[str, Any], authority: dict[str, Any], eligibility: MemoryEligibility, admitted: list[dict[str, Any]]) -> str:
    lines = [
        "Answer this request directly in Claire's normal voice through the selected language model.",
        "Do not reuse a prepared speech. Do not let background records replace the present question.",
        "Separate fact, inference, and uncertainty. Keep the answer direct and natural.",
        f"Route lane: {lane_result.get('lane')}",
        f"Recall mode: {eligibility.mode.value}",
        f"Authority: {authority.get('authority')}",
    ]
    if eligibility.required_evidence and not admitted:
        lines.append("Verified evidence available to this route: none.")
    if admitted:
        lines.append("Admitted context. Use only as support; do not quote it as the final answer:")
        for idx, item in enumerate(admitted[:4], 1):
            text = " ".join(str(item.get("text") or "").split())[:360]
            lanes = ", ".join(str(x) for x in item.get("lanes", [])) or "unknown"
            source = _candidate_source(item)
            lines.append(f"{idx}. source={source}; lanes={lanes}; summary={text}")
    lines.extend(["Current request:", normalized.get("text", "")])
    return "\n".join(lines)


def route_chat_message(
    q: str,
    provider_generate: ProviderGenerate,
    are_recall: Callable[[str], Any] | None = None,
    document_recall: Callable[[str], str] | None = None,
    useful_reply: Callable[[str], bool] | None = None,
) -> RouteResult:
    trace_steps: list[dict[str, Any]] = []

    normalized = normalize_input(q)
    trace_steps.append({"stage": "normalization", "payload": {"payload_hash": normalized["payload_hash"]}})

    orientation = provisional_orientation(normalized)
    trace_steps.append({"stage": "provisional_orientation", "payload": orientation})

    lane_result = c3rp_classify(normalized, orientation)
    trace_steps.append({"stage": "lane_classification", "payload": lane_result})

    authority = evaluate_authority(normalized, lane_result)
    trace_steps.append({"stage": "authority", "payload": authority})

    eligibility = determine_memory_eligibility(normalized, lane_result, authority)
    trace_steps.append({"stage": "memory_eligibility", "payload": eligibility.to_dict()})

    candidates: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []

    if eligibility.mode == MemoryMode.QUARANTINED:
        quarantined.append({"reason": eligibility.reason, "text": normalized["text"][:240], "lanes": [lane_result["lane"]]})
    elif eligibility.mode in {MemoryMode.SUPPORT, MemoryMode.STRICT, MemoryMode.REQUIRED}:
        if eligibility.mode == MemoryMode.STRICT and "document" in eligibility.allowed_stores:
            raw_doc = document_recall(normalized["text"]) if document_recall else ""
            candidates = extract_candidates({"results": [{"text": raw_doc, "source": "document", "lane": "document_upload"}]} if raw_doc else None)
        elif are_recall:
            candidates = extract_candidates(are_recall(normalized["text"]))
        accepted, rejected = gate_retrieval_candidates(
            normalized["text"],
            {
                **lane_result.get("legacy_intent", {}),
                "allowed_lanes": eligibility.allowed_lanes or lane_result.get("allowed_lanes", []),
                "suppressed_lanes": lane_result.get("suppressed_lanes", []),
            },
            candidates,
            threshold=0.42,
        )
    trace_steps.append(
        {
            "stage": "retrieval_and_fare_projection",
            "payload": {
                "attempted": bool(candidates),
                "accepted": len(accepted),
                "rejected": len(rejected),
                "quarantined": len(quarantined),
            },
        }
    )

    admitted = _sentinel_diode_admit(accepted, eligibility)
    trace_steps.append({"stage": "sentinel_diode_admission", "payload": {"admitted": len(admitted)}})

    prompt = build_governed_prompt(normalized, lane_result, authority, eligibility, admitted)
    trace_steps.append({"stage": "generation_permission", "payload": {"provider": "GO", "admitted_context": len(admitted)}})

    reply = provider_generate(prompt)
    if useful_reply and not useful_reply(reply):
        reply = ""
    validation = validate_output(reply, rejected, quarantined)
    trace_steps.append({"stage": "output_validation", "payload": validation})

    write_policy = {
        "trace": writeback_decision("trace", {"writeback_approved": False}).to_dict(),
        "session_turn": writeback_decision("session_turn", {"writeback_approved": False}).to_dict(),
        "durable_fact": writeback_decision("durable_fact", {"writeback_approved": False}).to_dict(),
        "tmf_snapshot": writeback_decision("tmf_snapshot", {"writeback_approved": False}).to_dict(),
    }
    trace_steps.append({"stage": "writebarrier", "payload": write_policy})

    trace_payload = {
        "type": "phase_one_route",
        "input_hash": normalized["payload_hash"],
        "lane": lane_result["lane"],
        "memory_mode": eligibility.mode.value,
        "authority": authority,
        "accepted_candidates": [compact_candidate(item) for item in accepted[:5]],
        "rejected_candidates": [compact_candidate(item) for item in rejected[:8]],
        "quarantined_context": quarantined,
        "steps": trace_steps,
    }

    return RouteResult(
        source="GO",
        reply=reply or "I could not get a usable generated answer from the selected provider.",
        trace_payload=trace_payload,
        writeback_policy=write_policy,
    )


def validate_output(reply: str, rejected: list[dict[str, Any]], quarantined: list[dict[str, Any]]) -> dict[str, Any]:
    text = str(reply or "")
    blocked_hits = []
    for item in rejected + quarantined:
        candidate_text = " ".join(str(item.get("text") or "").split())
        if len(candidate_text) >= 80 and candidate_text[:80] in text:
            blocked_hits.append(candidate_text[:80])
    return {
        "status": "blocked_context_detected" if blocked_hits else "passed",
        "blocked_context_hits": blocked_hits,
    }


def _sentinel_diode_admit(candidates: list[dict[str, Any]], eligibility: MemoryEligibility) -> list[dict[str, Any]]:
    if eligibility.mode in {MemoryMode.OFF, MemoryMode.QUARANTINED}:
        return []
    admitted = []
    for candidate in candidates:
        lanes = {str(lane) for lane in candidate.get("lanes", [])}
        if "legal_case" in lanes and "legal_case" not in eligibility.allowed_lanes:
            continue
        admitted.append(candidate)
    return admitted


def _phase_one_lane(cleaned: str, legacy: dict[str, Any]) -> str:
    if not cleaned or cleaned in {"hi", "hello", "hey", "yo", "hello claire", "hi claire"}:
        return "CASUAL"
    if _is_safety_sensitive(cleaned):
        return "SAFETY_SENSITIVE"
    if any(marker in cleaned for marker in ["this document", "that document", "uploaded document", "document i uploaded", "summarize this", "summarize the document"]):
        return "DOCUMENT_QA"
    if any(marker in cleaned for marker in ["current branch", "working tree", "repo", "repository", "what files", "project state"]):
        return "PROJECT_STATE"
    if any(marker in cleaned for marker in ["publish", "upload", "email", "post", "spend", "restart", "delete", "schedule"]):
        return "ACTION_REQUEST"
    if any(marker in cleaned for marker in ["speak spanish", "hablas espanol", "hablas español", "can you speak", "how are you"]):
        return "CASUAL"
    if legacy.get("reasoning_mode") == "reasoning_first":
        return "CONCEPTUAL"
    if any(marker in cleaned for marker in ["benchmark", "pipeline", "architecture", "rag", "are", "faiss", "pinecone", "runtime", "identity"]):
        return "CONCEPTUAL"
    return "CONCEPTUAL"


def _is_safety_sensitive(cleaned: str) -> bool:
    return any(marker in str(cleaned or "") for marker in ["weapon", "kill", "explosive", "delete all files", "steal", "credential", "api key"])


def _candidate_source(candidate: dict[str, Any]) -> str:
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    return str(raw.get("source") or raw.get("id") or candidate.get("source") or "unknown")

