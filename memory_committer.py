from __future__ import annotations

from typing import Any

from are_memory_store import AREMemoryStore, MemoryEvent
from entity_registry import identify_entities

DURABLE_MARKERS = [
    "remember this",
    "save this",
    "new company structure",
    "role changed",
    "milestone",
    "legal fact",
    "case fact",
    "horse fact",
    "nvidia",
    "veritas",
    "filed",
    "ein",
]


def should_commit_memory(message: str, lane: str, eligibility: Any) -> tuple[bool, str]:
    lowered = str(message or "").lower()
    if getattr(eligibility, "category", "") == "SENSITIVE_MEMORY":
        return False, "Sensitive memory requires explicit confirmation before durable write."
    if any(marker in lowered for marker in ["password", "passphrase", "private key", "api key", "battleborn_"]):
        return False, "Sensitive credential-like content is not eligible for durable memory."
    if not getattr(eligibility, "should_consider_write", False):
        return False, getattr(eligibility, "reason", "") or "Memory eligibility did not permit durable write."
    if any(marker in lowered for marker in DURABLE_MARKERS):
        return True, "Message contains explicit durable-memory marker or project milestone."
    if lane in {"BUSINESS_FORMATION", "LEGAL_CASE", "HORSE_STEWARDSHIP", "NVIDIA_PATHWAY"} and getattr(eligibility, "category", "") in {"PROJECT_MEMORY", "BUSINESS_MEMORY", "LEGAL_MEMORY"}:
        return True, "Lane and eligibility permit durable project memory."
    return False, "No durable memory write required."


def commit_if_needed(store: AREMemoryStore, user_id: str, session_id: str, message: str, lane: str, answer: str, eligibility: Any) -> tuple[bool, dict[str, Any] | None]:
    ok, reason = should_commit_memory(message, lane, eligibility)
    if not ok:
        return False, None
    entities = [item["name"] for item in identify_entities(message + " " + answer)]
    event = MemoryEvent(
        user_id=user_id,
        session_id=session_id,
        lane=lane,
        event_type="durable_exchange",
        summary=str(message or "")[:500],
        raw_excerpt=str(message or "")[:1200],
        source="chat_runtime",
        confidence=0.75,
        importance_score=float(getattr(eligibility, "importance_score", 0.5)),
        related_entities=entities,
        write_reason=reason,
    )
    return True, store.append_memory_event(event)
