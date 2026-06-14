from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MemoryMode(str, Enum):
    OFF = "OFF"
    SUPPORT = "SUPPORT"
    STRICT = "STRICT"
    REQUIRED = "REQUIRED"
    QUARANTINED = "QUARANTINED"


MEMORY_CATEGORIES = {
    "EPHEMERAL",
    "SESSION_ONLY",
    "PROJECT_MEMORY",
    "BUSINESS_MEMORY",
    "LEGAL_MEMORY",
    "PERSONAL_MEMORY",
    "SENSITIVE_MEMORY",
}


@dataclass
class MemoryEligibility:
    mode: MemoryMode
    allowed_stores: list[str] = field(default_factory=list)
    allowed_lanes: list[str] = field(default_factory=list)
    required_evidence: bool = False
    reason: str = ""
    category: str = "EPHEMERAL"
    should_consider_write: bool = False
    requires_confirmation: bool = False
    importance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data


def determine_memory_eligibility(normalized_input: dict[str, Any], lane_result: dict[str, Any], authority_result: dict[str, Any]) -> MemoryEligibility:
    lane = str(lane_result.get("lane") or "").upper()
    text = str(normalized_input.get("text") or "")
    cleaned = str(normalized_input.get("cleaned") or "")

    if authority_result.get("restricted"):
        return MemoryEligibility(
            mode=MemoryMode.QUARANTINED,
            reason="Authority is restricted; memory may be preserved for trace only.",
        )

    if lane == "CASUAL":
        return MemoryEligibility(mode=MemoryMode.OFF, reason="Casual interaction does not need long-term recall.")

    if lane == "SAFETY_SENSITIVE":
        return MemoryEligibility(mode=MemoryMode.QUARANTINED, reason="Safety-sensitive request requires containment.")

    if lane == "DOCUMENT_QA":
        return MemoryEligibility(
            mode=MemoryMode.STRICT,
            allowed_stores=["document"],
            allowed_lanes=["document_upload"],
            required_evidence=True,
            reason="Document question must stay inside selected or latest document evidence.",
        )

    if lane == "PROJECT_STATE":
        return MemoryEligibility(
            mode=MemoryMode.REQUIRED,
            allowed_stores=["project_state"],
            required_evidence=True,
            reason="Project-state question requires verified local evidence.",
        )

    if lane == "LEGAL_RESEARCH":
        return MemoryEligibility(
            mode=MemoryMode.SUPPORT,
            allowed_stores=["are"],
            allowed_lanes=["legal_case", "legal_theory", "compliance"],
            reason="Explicit legal question may use eligible legal evidence only.",
        )

    if lane == "ACTION_REQUEST":
        return MemoryEligibility(mode=MemoryMode.OFF, reason="Action requests must not be driven by recalled memory in Phase One.")

    explicit_memory = any(
        marker in cleaned
        for marker in [
            "search memory",
            "find in memory",
            "what do you remember",
            "what did i say before",
            "from my docs",
            "from my documents",
            "uploaded document",
        ]
    )
    if explicit_memory:
        return MemoryEligibility(
            mode=MemoryMode.SUPPORT,
            allowed_stores=["are"],
            allowed_lanes=list(lane_result.get("allowed_lanes") or []),
            reason="User explicitly requested memory support.",
        )

    if lane == "CONCEPTUAL":
        return MemoryEligibility(mode=MemoryMode.OFF, reason="Conceptual question should be answered through reasoning first.")

    return MemoryEligibility(mode=MemoryMode.OFF, reason=f"No eligible memory needed for {lane or 'unknown'} lane.")


def evaluate_memory_eligibility(message: str, lane: str, importance_score: float = 0.5) -> MemoryEligibility:
    text = str(message or "").lower()
    lane = str(lane or "UNKNOWN").upper()
    explicit = any(marker in text for marker in ["remember this", "save this", "note this", "log this"])
    sensitive = any(marker in text for marker in ["ssn", "social security", "password", "passphrase", "private key", "api key", "bank account", "battleborn_"])
    explanatory = any(
        marker in text
        for marker in [
            "explain",
            "what is",
            "what are",
            "what does",
            "which of",
            "tell me which",
            "difference between",
            "before you answer",
            "orient first",
        ]
    )

    if sensitive:
        return MemoryEligibility(
            mode=MemoryMode.QUARANTINED,
            reason="Sensitive content requires confirmation before durable memory.",
            category="SENSITIVE_MEMORY",
            should_consider_write=False,
            requires_confirmation=True,
            importance_score=0.1,
        )

    durable_markers = [
        "remember this",
        "save this",
        "milestone",
        "confirmed",
        "role",
        "officer",
        "member",
        "filed",
        "incorporated",
        "ein",
        "operating agreement",
        "nvidia",
        "nemotron",
        "veritas",
        "are",
        "horse",
        "pedro",
        "wyoming",
        "benchmark",
        "commit",
    ]
    if explanatory and not explicit:
        return MemoryEligibility(
            mode=MemoryMode.OFF,
            reason="Explanatory/orientation request should not create durable memory by itself.",
            category="EPHEMERAL",
            should_consider_write=False,
            requires_confirmation=False,
            importance_score=min(importance_score, 0.4),
        )

    durable = explicit or any(marker in text for marker in durable_markers)

    if lane == "LEGAL_CASE" and durable:
        category = "LEGAL_MEMORY"
    elif lane == "BUSINESS_FORMATION" and durable:
        category = "BUSINESS_MEMORY"
    elif lane in {"CLAIRE_SYSTEM_ARCHITECTURE", "NVIDIA_PATHWAY", "TRADING_STATION", "HORSE_STEWARDSHIP"} and durable:
        category = "PROJECT_MEMORY"
    elif explicit:
        category = "PROJECT_MEMORY"
    elif lane == "PERSONAL_SUPPORT":
        category = "PERSONAL_MEMORY"
    else:
        category = "EPHEMERAL"

    should_write = category in {"PROJECT_MEMORY", "BUSINESS_MEMORY", "LEGAL_MEMORY"} and durable
    return MemoryEligibility(
        mode=MemoryMode.SUPPORT if should_write else MemoryMode.OFF,
        allowed_stores=["are"] if should_write else [],
        allowed_lanes=[lane] if should_write else [],
        reason="Durable governed memory signal found." if should_write else "No durable memory write required.",
        category=category,
        should_consider_write=should_write,
        requires_confirmation=False,
        importance_score=max(importance_score, 0.65) if should_write else min(importance_score, 0.4),
    )
