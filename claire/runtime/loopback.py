from __future__ import annotations

from typing import Any


GENERIC_FILLER = [
    "i can help with that. tell me the goal",
    "tell me the specific outcome you want",
    "as an ai language model",
    "i don't have enough context",
]


class LoopbackLayer:
    """Re-anchors unstable or drifting answers to the original request."""

    def pre_generation_response(
        self,
        *,
        prompt: str,
        gyro_bearing: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        mode = "clarify" if self._needs_clarification(gyro_bearing) else "bounded"
        if mode == "clarify":
            answer = self._clarifying_question(prompt, gyro_bearing)
        else:
            answer = self._bounded_answer(prompt, gyro_bearing, reason)
        return {"answer": answer, "answer_mode": mode, "loopback_reason": reason}

    def post_generation_check(
        self,
        *,
        prompt: str,
        answer: str,
        gyro_bearing: dict[str, Any],
        lane: str,
        risk_level: str,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        lowered_answer = str(answer or "").lower().strip()
        lowered_prompt = str(prompt or "").lower()
        if not lowered_answer:
            reasons.append("empty answer")
        if any(marker in lowered_answer for marker in GENERIC_FILLER):
            reasons.append("generic filler response detected")
        if lane == "TRADING_STATION" and any(term in lowered_answer for term in ["buy now", "sell now", "place a live trade"]):
            reasons.append("high-risk financial claim/action drift")
        if lane == "LEGAL_CASE" and any(term in lowered_answer for term in ["guarantee", "certainly win", "will win"]):
            reasons.append("high-risk legal certainty drift")
        if "officeai" in lowered_prompt and "office" not in lowered_answer:
            reasons.append("answer drift from original prompt")
        if "nvidia" in lowered_prompt and "technical gate:" in lowered_answer:
            reasons.append("internal gate leakage")

        if not reasons:
            return {"triggered": False, "reason": "", "answer": answer, "answer_mode": gyro_bearing.get("output_boundary", "direct")}

        reason = "; ".join(reasons)
        mode = "refuse" if "high-risk" in reason else "bounded"
        return {
            "triggered": True,
            "reason": reason,
            "answer": self._bounded_answer(prompt, gyro_bearing, reason),
            "answer_mode": mode,
        }

    def _needs_clarification(self, gyro_bearing: dict[str, Any]) -> bool:
        reasons = " ".join(str(x) for x in gyro_bearing.get("reasons", [])).lower()
        return "unclear lane" in reasons or "low confidence" in reasons

    def _clarifying_question(self, prompt: str, gyro_bearing: dict[str, Any]) -> str:
        lane = gyro_bearing.get("lane") or "UNKNOWN"
        return f"I need one clarification before answering: should I treat this as {lane} work, or is there a different lane/source you want me to use?"

    def _bounded_answer(self, prompt: str, gyro_bearing: dict[str, Any], reason: str) -> str:
        lane = str(gyro_bearing.get("lane") or "UNKNOWN")
        risk = str(gyro_bearing.get("risk") or "unknown")
        if lane == "TRADING_STATION":
            if "missing source authority" in reason:
                return "Veritas status requires trusted authority. From guest chat I can only explain the safety boundary: Veritas is a governed financial intelligence subsystem, not CLAIRE memory, and live execution is blocked here."
            return "I can discuss trading-system status and risk posture, but I cannot execute or authorize live trades from normal chat."
        if lane == "LEGAL_CASE":
            if "missing source authority" in reason:
                return "Legal-sensitive monitoring requires trusted authority. From guest chat I can only give public, cautious, non-filing guidance."
            return "I can give a cautious, source-bounded legal-monitoring answer, but I cannot guarantee an outcome or perform filing actions from chat."
        if "generic filler" in reason:
            return "I should answer the specific request instead of asking for a new goal. I can give a narrow answer using the current lane and available sources."
        return f"I am keeping this bounded because {reason}. The current lane is {lane}, risk is {risk}, and I can answer only within available authority and sources."
