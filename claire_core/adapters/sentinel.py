from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SentinelAction(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_RESTRICTIONS = "ALLOW_WITH_RESTRICTIONS"
    BLOCK = "BLOCK"
    QUARANTINE = "QUARANTINE"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
    RETRY_WITH_SAFE_CONTEXT = "RETRY_WITH_SAFE_CONTEXT"
    DEGRADE_MODE = "DEGRADE_MODE"


@dataclass(frozen=True)
class SentinelDecision:
    decision: SentinelAction
    reason: str
    restrictions: list[str] = field(default_factory=list)
    rules_triggered: list[str] = field(default_factory=list)
    policy_version: str = "sentinel.runtime.v1"

    @property
    def allowed(self) -> bool:
        return self.decision in {
            SentinelAction.ALLOW,
            SentinelAction.ALLOW_WITH_RESTRICTIONS,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        data["allowed"] = self.allowed
        return data


class RuntimeSentinel:
    """Pre-action Sentinel checks for live runtime gates."""

    def authorize_memory_write(
        self,
        *,
        lane: str,
        record_class: str,
        echo_classification: dict[str, Any],
        matter_id: str = "",
        target_matter_id: str = "",
    ) -> SentinelDecision:
        risks = echo_classification.get("detected_risks") or []
        risk_codes = [str(item.get("code") or "") for item in risks if isinstance(item, dict)]
        if echo_classification.get("quarantine"):
            return SentinelDecision(
                SentinelAction.QUARANTINE,
                "EchoShield classified the candidate record as quarantined.",
                ["block_durable_write", "preserve_turn_trace_only"],
                risk_codes,
            )
        if record_class == "model_output" and lane in {"LEGAL_CASE", "TRADING_STATION"}:
            return SentinelDecision(
                SentinelAction.REQUIRE_HUMAN_REVIEW,
                "High-assurance lanes require review before generated output becomes durable memory.",
                ["human_review_required"],
                ["generated_output_high_assurance_lane"],
            )
        if matter_id and target_matter_id and matter_id != target_matter_id:
            return SentinelDecision(
                SentinelAction.BLOCK,
                "Matter boundary mismatch blocks memory write.",
                ["block_durable_write"],
                ["matter_boundary_mismatch"],
            )
        if record_class == "verified_fact":
            return SentinelDecision(
                SentinelAction.REQUIRE_HUMAN_REVIEW,
                "Verified facts require evidence admission before durable classification.",
                ["require_evidence_record"],
                ["verified_fact_requires_evidence"],
            )
        return SentinelDecision(SentinelAction.ALLOW, "Sentinel allowed memory write candidate.")
