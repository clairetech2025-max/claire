from __future__ import annotations

import re
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
    "we decided",
    "we're going to",
    "we re going to",
    "we are going to",
    "leave creator mode alone",
    "after claire is stable",
    "correction:",
    "actually supersedes",
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
    continuity = continuity_summary(message)
    event = MemoryEvent(
        user_id=user_id,
        session_id=session_id,
        lane="SESSION" if continuity else lane,
        event_type="continuity_fact" if continuity else "durable_exchange",
        summary=(continuity or str(message or ""))[:800],
        raw_excerpt=str(message or "")[:1200],
        source="chat_runtime",
        confidence=0.75,
        importance_score=float(getattr(eligibility, "importance_score", 0.5)),
        related_entities=entities,
        write_reason=reason,
        memory_scope=_scope_for_lane(lane),
    )
    return True, store.append_memory_event(event)


def continuity_summary(message: str) -> str:
    """Extract only narrow, meaningful state; never copy arbitrary chat."""
    text = " ".join(str(message or "").split())
    lowered = text.lower()
    facts: list[str] = []
    if "leave creator mode alone" in lowered or (
        "creator mode" in lowered and any(marker in lowered for marker in ["we decided", "we're going to leave", "we are going to leave"])
    ):
        facts.append("continuity_fact: creator_mode.decision = intentionally left alone until CLAIRE testing is finished")
    if "veritas" in lowered and "after claire is stable" in lowered:
        facts.append("continuity_fact: roadmap.next_after_claire = Veritas")
    generic = re.search(
        r"(?:correction:\s*)?remember this:\s*([a-z][a-z0-9 _-]{2,60})\s+(?:is|=)\s+([A-Za-z0-9_.: -]{2,100})",
        text,
        re.IGNORECASE,
    )
    if generic:
        subject = "_".join(generic.group(1).lower().split())
        value = generic.group(2).strip().rstrip(". ")
        prefix = "correction " if lowered.startswith("correction:") else ""
        facts.append(f"continuity_fact: {subject}.value = {prefix}{value}")
    return "\n".join(facts)


def _scope_for_lane(lane: str) -> str:
    lane = str(lane or "").upper()
    if lane == "LEGAL_CASE":
        return "LEGAL_SENSITIVE"
    if lane == "TRADING_STATION":
        return "TRADING_SENSITIVE"
    if lane == "HORSE_STEWARDSHIP":
        return "HORSE_STEWARDSHIP"
    if lane in {"BUSINESS_FORMATION", "CLAIRE_SYSTEM_ARCHITECTURE", "NVIDIA_PATHWAY"}:
        return "COMPANY_INTERNAL"
    return "PUBLIC"
