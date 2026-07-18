from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class RuntimeMode(str, Enum):
    NORMAL = "NORMAL"
    LEGAL_HIGH_ASSURANCE = "LEGAL_HIGH_ASSURANCE"
    HOSTILE_INPUT = "HOSTILE_INPUT"
    OFFLINE = "OFFLINE"
    RESOURCE_CONSTRAINED = "RESOURCE_CONSTRAINED"
    RECOVERY = "RECOVERY"
    READ_ONLY = "READ_ONLY"
    DEGRADED = "DEGRADED"
    SAFE_SHUTDOWN = "SAFE_SHUTDOWN"


@dataclass(frozen=True)
class ModePermissions:
    model_available: bool
    tool_available: bool
    recall_depth: int
    source_required: bool
    memory_write_allowed: bool
    external_action_allowed: bool
    human_review_required: bool
    logging_level: str
    concurrency: int
    timeout_seconds: int


MODE_MATRIX: dict[RuntimeMode, ModePermissions] = {
    RuntimeMode.NORMAL: ModePermissions(True, True, 8, False, True, False, False, "standard", 4, 60),
    RuntimeMode.LEGAL_HIGH_ASSURANCE: ModePermissions(True, True, 12, True, True, False, True, "evidence", 2, 90),
    RuntimeMode.HOSTILE_INPUT: ModePermissions(True, False, 3, True, False, False, True, "security", 1, 45),
    RuntimeMode.OFFLINE: ModePermissions(True, False, 5, False, True, False, False, "standard", 2, 60),
    RuntimeMode.RESOURCE_CONSTRAINED: ModePermissions(True, False, 3, False, False, False, False, "minimal", 1, 30),
    RuntimeMode.RECOVERY: ModePermissions(False, False, 10, True, False, False, True, "recovery", 1, 60),
    RuntimeMode.READ_ONLY: ModePermissions(True, False, 8, True, False, False, False, "audit", 2, 60),
    RuntimeMode.DEGRADED: ModePermissions(True, False, 3, False, False, False, False, "degraded", 1, 30),
    RuntimeMode.SAFE_SHUTDOWN: ModePermissions(False, False, 0, True, False, False, True, "shutdown", 1, 10),
}


class Lycanthrope:
    def __init__(self, mode: RuntimeMode = RuntimeMode.NORMAL) -> None:
        self.mode = mode

    def permissions(self, mode: RuntimeMode | str | None = None) -> dict[str, Any]:
        selected = RuntimeMode(mode or self.mode)
        return asdict(MODE_MATRIX[selected])

    def transition(
        self,
        requested_mode: RuntimeMode | str,
        *,
        sentinel_decision: dict[str, Any],
        trigger: str,
    ) -> dict[str, Any]:
        requested = RuntimeMode(requested_mode)
        allowed = bool(sentinel_decision.get("allowed") or sentinel_decision.get("decision") in {"ALLOW", "ALLOW_WITH_RESTRICTIONS"})
        prior = self.mode
        if not allowed:
            return {
                "allowed": False,
                "prior_mode": prior.value,
                "requested_mode": requested.value,
                "active_mode": prior.value,
                "trigger": trigger,
                "reason": sentinel_decision.get("reason") or "Sentinel denied mode transition.",
                "changed_permissions": {},
            }
        self.mode = requested
        return {
            "allowed": True,
            "prior_mode": prior.value,
            "requested_mode": requested.value,
            "active_mode": self.mode.value,
            "trigger": trigger,
            "reason": sentinel_decision.get("reason") or "Sentinel authorized mode transition.",
            "changed_permissions": self.permissions(self.mode),
        }
