from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

LANES = {
    "CLAIRE_SYSTEM_ARCHITECTURE",
    "LEGAL_CASE",
    "HORSE_STEWARDSHIP",
    "BUSINESS_FORMATION",
    "NVIDIA_PATHWAY",
    "TRADING_STATION",
    "PERSONAL_SUPPORT",
    "GENERAL_CHAT",
    "UNKNOWN",
}


@dataclass
class LaneResult:
    lane: str
    confidence: float
    reason: str
    allowed_memory_lanes: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    requires_strict_provenance: bool = False
    caution: str = "normal"
    output_style: str = "direct"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HORSE_STEWARDSHIP_MARKERS = [
    "horse",
    "horses",
    "hoof",
    "hooves",
    "farrier",
    "molding kit",
    "mold kit",
    "hoof mold",
    "hoof impression",
    "hoof casting",
    "softshoe",
    "horse boot",
    "equine",
    "pastern",
    "fetlock",
    "lameness",
    "padding",
    "sole",
    "frog",
    "tire tread",
    "louie",
    "louis",
    "pedro",
    "hay",
    "rescue horse",
    "trail horse",
    "stewardship",
    "veterinary",
    "vet",
    "wyoming",
    "seahorse",
    "rescue",
    "trail riding",
]

TRADING_STATION_MARKERS = [
    "crypto",
    "kraken",
    "veritas",
    "btc",
    "eth",
    "ohlcv",
    "market data",
    "trade",
    "trading",
    "paper trade",
    "live trade",
    "order",
    "position",
    "exchange",
    "risk governor",
    "kill switch",
    "portfolio",
    "backtest",
    "financial intelligence",
]


def _contains(text: str, markers: list[str]) -> bool:
    for marker in markers:
        marker = str(marker or "").lower().strip()
        if not marker:
            continue
        if " " not in marker and len(marker) <= 4:
            import re

            if re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", text):
                return True
        elif marker in text:
            return True
    return False


def classify_lane(message: str, recent_context: list[dict[str, Any]] | None = None) -> LaneResult:
    text = " ".join(str(message or "").lower().split())
    recent_context = recent_context or []

    if not text:
        return LaneResult("UNKNOWN", 0.2, "Empty input.")

    if _contains(text, ["nvidia", "nemotron", "nim", "cuda", "cuvs", "triton", "guardrails"]):
        return LaneResult(
            "NVIDIA_PATHWAY",
            0.86,
            "NVIDIA-facing technical or business pathway markers found.",
            ["NVIDIA_PATHWAY", "CLAIRE_SYSTEM_ARCHITECTURE", "BUSINESS_FORMATION"],
            ["repo_status", "benchmark_status"],
            True,
            "technical_business",
            "engineer_founder",
        )

    if _contains(text, TRADING_STATION_MARKERS):
        return LaneResult(
            "TRADING_STATION",
            0.84,
            "Trading station / Veritas markers found.",
            ["TRADING_STATION", "CLAIRE_SYSTEM_ARCHITECTURE", "BUSINESS_FORMATION"],
            ["veritas_status"],
            True,
            "financial_cautious",
            "technical_risk",
        )

    if _contains(text, ["claire systems", "llc", "ein", "operating agreement", "founder", "ceo", "chief architect", "member", "officer", "brisa", "jason"]):
        return LaneResult(
            "BUSINESS_FORMATION",
            0.82,
            "Business formation or role markers found.",
            ["BUSINESS_FORMATION", "NVIDIA_PATHWAY", "HORSE_STEWARDSHIP"],
            ["truth_files"],
            True,
            "business_cautious",
            "business",
        )

    if _contains(text, HORSE_STEWARDSHIP_MARKERS):
        return LaneResult(
            "HORSE_STEWARDSHIP",
            0.82,
            "Horse stewardship markers found.",
            ["HORSE_STEWARDSHIP", "BUSINESS_FORMATION", "PERSONAL_SUPPORT"],
            ["truth_files"],
            False,
            "mission_care",
            "practical_support",
        )

    if _contains(text, ["federal complaint", "court", "lawsuit", "legal", "case", "filing", "complaint", "pleading", "jurisdiction", "statute"]):
        return LaneResult(
            "LEGAL_CASE",
            0.78,
            "Legal-case markers found.",
            ["LEGAL_CASE"],
            ["legal_research"],
            True,
            "legal_cautious",
            "legal_precision",
        )

    if _contains(text, ["architecture", "runtime", "are", "analog recall", "gyro", "q insight", "sentinel", "diode", "writebarrier", "trace", "pipeline", "repository"]):
        return LaneResult(
            "CLAIRE_SYSTEM_ARCHITECTURE",
            0.78,
            "CLAIRE architecture markers found.",
            ["CLAIRE_SYSTEM_ARCHITECTURE", "NVIDIA_PATHWAY"],
            ["repo_status", "truth_files"],
            True,
            "technical",
            "technical",
        )

    if _contains(text, ["i feel", "i'm worried", "im worried", "stress", "tired", "overwhelmed", "thank you", "you there", "where were we"]):
        return LaneResult(
            "PERSONAL_SUPPORT",
            0.66,
            "Personal support or continuity markers found.",
            ["PERSONAL_SUPPORT", "BUSINESS_FORMATION", "HORSE_STEWARDSHIP"],
            ["session_continuity"],
            False,
            "supportive",
            "grounded_support",
        )

    if len(recent_context) and _contains(text, ["that", "earlier", "where were we", "what did i ask", "how many", "the question"]):
        return LaneResult(
            "GENERAL_CHAT",
            0.62,
            "Follow-up phrasing with recent context available.",
            ["GENERAL_CHAT", "SESSION"],
            ["session_continuity"],
            False,
            "normal",
            "direct",
        )

    return LaneResult("GENERAL_CHAT", 0.55, "Default general conversation lane.", ["GENERAL_CHAT", "SESSION"], [], False, "normal", "direct")
