from __future__ import annotations

from typing import Any


def validate_response(answer: str, context_packet: dict[str, Any], lane: str) -> dict[str, Any]:
    text = str(answer or "")
    lowered = text.lower()
    issues: list[str] = []
    lane = str(lane or "UNKNOWN")

    if not text.strip():
        issues.append("empty_answer")
    if lane in {"LEGAL_CASE", "TRADING_STATION"} and any(term in lowered for term in ["guarantee", "certainly", "risk-free", "sure profit"]):
        issues.append("overconfident_high_stakes_claim")
    if lane == "TRADING_STATION" and any(term in lowered for term in ["place a live trade", "execute a live trade", "buy now", "sell now"]):
        issues.append("unsafe_live_trading_advice")
    if lane != "LEGAL_CASE" and any(term in lowered for term in ["federal complaint", "court pleading", "paloma", "spca", "california state parks"]):
        issues.append("cross_lane_legal_leakage")
    if "just an idea" in lowered or "if this becomes real" in lowered:
        issues.append("weak_invention_language")

    approved = not issues
    revised = None
    if not approved:
        revised = "I need to correct that answer before showing it: " + "; ".join(issues) + "."
    return {"approved": approved, "issues": issues, "revised_answer": revised}
