from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable

from intent_classifier import classify_query
from lane_router import extract_candidates
from memory_eligibility import MemoryEligibility, MemoryMode, determine_memory_eligibility
from original_are_bridge import read_original_are_history
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
    read_only_document_request = _is_document_read_request(cleaned)
    protected_action = (not read_only_document_request) and any(
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


def build_governed_prompt(normalized: dict[str, Any], lane_result: dict[str, Any], authority: dict[str, Any], eligibility: MemoryEligibility, admitted: list[dict[str, Any]], temporal_history: dict[str, Any] | None = None) -> str:
    lines = [
        "Answer this request directly in Claire's normal voice through the selected language model.",
        "Do not reuse a prepared speech. Do not let background records replace the present question.",
        "Separate fact, inference, and uncertainty. Keep the answer direct and natural.",
        f"Route lane: {lane_result.get('lane')}",
        f"Recall mode: {eligibility.mode.value}",
        f"Authority: {authority.get('authority')}",
    ]
    lines.extend(_format_temporal_history_for_prompt(temporal_history or {}))
    if _lane_blocks_legal_memory(lane_result.get("lane")):
        lines.append("Lane isolation: do not use or mention unrelated legal-case, complaint, animal-control, parks-agency, county, party-name, court-pleading, or personal-history material unless explicitly admitted below.")
    document_qa = str(lane_result.get("lane") or "").upper() == "DOCUMENT_QA"
    if document_qa:
        lines.append("Document task: answer only from admitted document context. If admitted document context exists, treat it as the selected or latest uploaded document and do not ask the user to upload it again.")
    if eligibility.required_evidence and not admitted:
        lines.append("Verified evidence available to this route: none.")
    if admitted:
        lines.append("Admitted context. Use only as support; do not quote it as the final answer:")
        for idx, item in enumerate(admitted[:4], 1):
            context_limit = 1400 if document_qa else 360
            text = " ".join(str(item.get("text") or "").split())[:context_limit]
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
    temporal_history_reader: Callable[[], dict[str, Any]] | None = None,
) -> RouteResult:
    trace_steps: list[dict[str, Any]] = []

    temporal_history = (temporal_history_reader or (lambda: read_original_are_history(limit=8)))()
    trace_steps.append({"stage": "preserved_chronological_experience", "payload": _temporal_history_trace_payload(temporal_history)})

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

    prompt = build_governed_prompt(normalized, lane_result, authority, eligibility, admitted, temporal_history)
    trace_steps.append({"stage": "generation_permission", "payload": {"provider": "GO", "admitted_context": len(admitted)}})

    reply = provider_generate(prompt)
    if useful_reply and not useful_reply(reply):
        reply = ""
    validation = validate_output(reply, rejected, quarantined, lane_result, admitted)
    if validation.get("status") == "document_evidence_ignored":
        retry_prompt = prompt + "\n\nRegenerate the answer. The prior draft ignored admitted document evidence. Use the admitted document context above, answer the current request directly, and do not ask for another upload."
        trace_steps.append({"stage": "generation_retry", "payload": {"reason": "document_evidence_ignored"}})
        reply = provider_generate(retry_prompt)
        if useful_reply and not useful_reply(reply):
            reply = ""
        validation = validate_output(reply, rejected, quarantined, lane_result, admitted)
    if validation.get("status") != "passed":
        reply = "Provider output blocked: cross-lane, quarantined, or ignored required document context detected."
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
        "temporal_history": _temporal_history_trace_payload(temporal_history),
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


def _format_temporal_history_for_prompt(temporal_history: dict[str, Any]) -> list[str]:
    records = list(temporal_history.get("records") or [])
    quarantined = list(temporal_history.get("quarantined_records") or [])
    lines = [
        "PRESERVED CHRONOLOGICAL EXPERIENCE -- READ ONLY",
        "These records predate the current interpretation.",
        "Listed order is evidence. The model may interpret these records, but may not rewrite, reorder, summarize away, or treat absence as support.",
        "If the preserved chronology does not support a claim, state the absence rather than inventing continuity.",
    ]
    if not records:
        reason = str(temporal_history.get("reason") or "No prior chronological experience supplied.")
        lines.append(f"State: empty. {reason}")
    else:
        for item in records:
            order = item.get("order")
            ts = item.get("ts")
            sha = item.get("sha") or ""
            text = str(item.get("text") or "")
            lines.append(f"{order}. ts={ts}; sha={sha}; text:")
            lines.append(text)
    if quarantined:
        lines.append(f"Quarantined malformed chronological records: {len(quarantined)}. Do not use them for generation.")
    return lines


def _temporal_history_trace_payload(temporal_history: dict[str, Any]) -> dict[str, Any]:
    records = list(temporal_history.get("records") or [])
    return {
        "status": temporal_history.get("status", "unknown"),
        "reason": temporal_history.get("reason", ""),
        "memory_file": temporal_history.get("memory_file", ""),
        "record_count": len(records),
        "quarantined_count": len(temporal_history.get("quarantined_records") or []),
        "records": [
            {
                "order": item.get("order"),
                "line_number": item.get("line_number"),
                "ts": item.get("ts"),
                "sha": item.get("sha"),
            }
            for item in records[:8]
        ],
    }


def _lane_blocks_legal_memory(lane: Any) -> bool:
    return str(lane or "").upper() in {"CASUAL", "CONCEPTUAL", "ACTION_REQUEST", "DOCUMENT_QA"}


def _blocked_cross_lane_terms() -> list[str]:
    return [
        "steven roth",
        "seahorse equestrian",
        "federal complaint",
        "paloma",
        "spca",
        "california state parks",
        "monterey county",
        "sean james",
        "court pleadings",
    ]


def validate_output(reply: str, rejected: list[dict[str, Any]], quarantined: list[dict[str, Any]], lane_result: dict[str, Any] | None = None, admitted: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    text = str(reply or "")
    blocked_hits = []
    for item in rejected + quarantined:
        candidate_text = " ".join(str(item.get("text") or "").split())
        if len(candidate_text) >= 80 and candidate_text[:80] in text:
            blocked_hits.append(candidate_text[:80])
    cross_lane_hits = []
    lowered = text.lower()
    if lane_result and _lane_blocks_legal_memory(lane_result.get("lane")):
        cross_lane_hits = [term for term in _blocked_cross_lane_terms() if term in lowered]
    document_evidence_ignored = False
    if lane_result and str(lane_result.get("lane") or "").upper() == "DOCUMENT_QA" and admitted:
        ignored_markers = [
            "please upload",
            "go ahead and upload",
            "upload the file",
            "provide the file",
            "send the document",
            "no document",
            "don't have access",
            "do not have access",
        ]
        document_evidence_ignored = any(marker in lowered for marker in ignored_markers)
    status = "passed"
    if blocked_hits or cross_lane_hits:
        status = "blocked_context_detected"
    elif document_evidence_ignored:
        status = "document_evidence_ignored"
    return {
        "status": status,
        "blocked_context_hits": blocked_hits,
        "cross_lane_hits": cross_lane_hits,
        "document_evidence_ignored": document_evidence_ignored,
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
    if _is_document_read_request(cleaned):
        return "DOCUMENT_QA"
    if any(marker in cleaned for marker in ["current branch", "working tree", "repo", "repository", "what files", "project state"]):
        return "PROJECT_STATE"
    if legacy.get("detected_intent") == "LEGAL_RESEARCH" or (
        any(marker in cleaned for marker in ["steve's case", "steves case", "legal case", "case context", "federal complaint"])
        and any(marker in cleaned for marker in ["legal", "case", "court", "complaint", "filing"])
    ):
        return "LEGAL_RESEARCH"
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


def _is_document_read_request(cleaned: str) -> bool:
    text = str(cleaned or "")
    if not text:
        return False
    read_markers = [
        "this document",
        "that document",
        "uploaded document",
        "document i uploaded",
        "file i uploaded",
        "what did i just upload",
        "what did i upload",
        "latest upload",
        "recent upload",
        "summarize this",
        "summarize the document",
        "summarize the file",
        "what does the file",
        "what does the document",
        "what does",
    ]
    document_terms = ["document", "file", "upload", "uploaded", "txt", "pdf", "docx", "md", "json", "py", "csv"]
    if any(marker in text for marker in read_markers) and any(term in text for term in document_terms):
        return True
    return bool(re.search(r"\b[a-z0-9_.-]+\s+(txt|pdf|docx|md|json|jsonl|py|csv)\b", text))


def _candidate_source(candidate: dict[str, Any]) -> str:
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    return str(raw.get("source") or raw.get("id") or candidate.get("source") or "unknown")

