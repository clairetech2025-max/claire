from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EngineDecision:
    allowed: bool
    reason: str
    restrictions: tuple[str, ...] = ()
    policy_version: str = "claire-core.v1"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineStatus:
    name: str
    public_engine: str
    status: str
    implementation_path: str
    version: str = "0.1.0"
    active: bool = False
    degraded_reason: str = ""
    limitations: tuple[str, ...] = ()
    production_permission: bool = False
    last_successful_health_check: str = ""


@dataclass(frozen=True)
class CapabilityReport:
    generated_at: str
    capabilities: list[EngineStatus]


@dataclass
class ClaireCoreContext:
    user_id: str
    session_id: str
    turn_id: str
    lane: str
    matter_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
