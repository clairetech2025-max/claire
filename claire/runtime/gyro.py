from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


HIGH_RISK_LANES = {"LEGAL_CASE", "TRADING_STATION"}


@dataclass
class GyroBearing:
    intent: str
    lane: str
    authority: str
    risk: str
    memory_eligibility: str
    source_provenance: str
    continuity: str
    output_boundary: str
    stable: bool
    confidence: float
    reasons: list[str] = field(default_factory=list)

    def to_trace(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "lane": self.lane,
            "authority": self.authority,
            "risk": self.risk,
            "memory_eligibility": self.memory_eligibility,
            "source_provenance": self.source_provenance,
            "continuity": self.continuity,
            "output_boundary": self.output_boundary,
            "stable": self.stable,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


class GyroOrientationLayer:
    """Computes CLAIRE's pre-generation bearing."""

    def orient(
        self,
        *,
        prompt: str,
        lane_result: Any,
        c3rp_route: dict[str, Any],
        authority_capsule: Any,
        memory_eligibility: Any,
        risk_level: str,
        risks: list[str],
        current_truth: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> GyroBearing:
        metadata = metadata or {}
        lane = str(getattr(lane_result, "lane", "") or "UNKNOWN")
        confidence = float(getattr(lane_result, "confidence", 0.0) or 0.0)
        intent = self._intent(prompt, c3rp_route)
        authority = self._authority(authority_capsule)
        memory_state = self._memory_state(memory_eligibility)
        source_state = self._source_state(lane, current_truth, authority_capsule, risk_level, risks)
        continuity = self._continuity(metadata)
        output_boundary = self._output_boundary(lane, risk_level, risks, authority_capsule)

        reasons: list[str] = []
        if lane in {"UNKNOWN", ""}:
            reasons.append("unclear lane")
        if confidence < 0.5:
            reasons.append("low confidence")
        if source_state == "missing_source_authority":
            reasons.append("missing source authority")
        if self._memory_conflict_hint(prompt):
            reasons.append("memory conflict")
        if risk_level == "high" and lane in HIGH_RISK_LANES and output_boundary not in {"refuse", "bounded"}:
            reasons.append("high-risk answer lacks boundary")

        stable = not reasons
        return GyroBearing(
            intent=intent,
            lane=lane,
            authority=authority,
            risk=str(risk_level or "unknown"),
            memory_eligibility=memory_state,
            source_provenance=source_state,
            continuity=continuity,
            output_boundary=output_boundary,
            stable=stable,
            confidence=confidence,
            reasons=reasons,
        )

    def _intent(self, prompt: str, c3rp_route: dict[str, Any]) -> str:
        legacy = c3rp_route.get("legacy_intent") or {}
        primary = str(legacy.get("primary_intent") or "").strip()
        if primary:
            return primary
        text = str(prompt or "").lower()
        if "?" in text or any(marker in text for marker in ["explain", "what", "who", "how", "why"]):
            return "answer_question"
        if any(marker in text for marker in ["place", "execute", "file", "submit"]):
            return "action_request"
        return "general"

    def _authority(self, capsule: Any) -> str:
        role = str(getattr(capsule, "role", "") or "guest")
        strength = str(getattr(capsule, "auth_strength", "") or "guest_public")
        return f"{role}:{strength}"

    def _memory_state(self, eligibility: Any) -> str:
        mode = getattr(getattr(eligibility, "mode", None), "value", None) or getattr(eligibility, "mode", "unknown")
        category = getattr(eligibility, "category", "unknown")
        return f"{mode}:{category}"

    def _source_state(self, lane: str, current_truth: dict[str, Any], capsule: Any, risk_level: str, risks: list[str]) -> str:
        if lane == "LEGAL_CASE" and "LEGAL_SENSITIVE" not in set(getattr(capsule, "allowed_memory_scopes", []) or []):
            return "public_only_legal"
        if lane == "TRADING_STATION" and risk_level == "high":
            return "source_not_required_for_refusal"
        if lane == "TRADING_STATION" and "veritas_status" not in set(getattr(capsule, "allowed_tools", []) or []):
            return "missing_source_authority"
        if current_truth:
            return "current_truth_available"
        return "general_reasoning_only"

    def _continuity(self, metadata: dict[str, Any]) -> str:
        if metadata.get("recent_context"):
            return "recent_context_available"
        return "single_turn"

    def _output_boundary(self, lane: str, risk_level: str, risks: list[str], capsule: Any) -> str:
        if any("blocked" in str(risk).lower() for risk in risks):
            return "refuse"
        if risk_level == "high":
            return "bounded"
        if lane in HIGH_RISK_LANES:
            return "bounded"
        return "direct"

    def _memory_conflict_hint(self, prompt: str) -> bool:
        text = str(prompt or "").lower()
        return any(marker in text for marker in ["conflicting memory", "memory conflict", "which memory is true"])
