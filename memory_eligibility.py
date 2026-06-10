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


@dataclass
class MemoryEligibility:
    mode: MemoryMode
    allowed_stores: list[str] = field(default_factory=list)
    allowed_lanes: list[str] = field(default_factory=list)
    required_evidence: bool = False
    reason: str = ""

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

