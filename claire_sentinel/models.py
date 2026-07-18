from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ToolCategory(StrEnum):
    PASSIVE_DISCOVERY = "passive_discovery"
    CONFIGURATION_AUDIT = "configuration_audit"
    LOG_ANALYSIS = "log_analysis"
    VULNERABILITY_SCANNING = "vulnerability_scanning"
    FORBIDDEN_HIGH_RISK = "forbidden_high_risk"


class ToolRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    category: ToolCategory
    risk: ToolRisk
    network_action: bool
    active_scan: bool
    command: str
    description: str
    allowed_args: tuple[str, ...] = ()
    forbidden_args: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = str(self.category)
        data["risk"] = str(self.risk)
        return data


@dataclass(frozen=True)
class ActionRequest:
    tool: str
    target: str = ""
    reason: str = ""
    args: tuple[str, ...] = ()
    operator_approved: bool = False
    dry_run: bool = False

    def command_preview(self, tool_command: str | None = None) -> list[str]:
        return [tool_command or self.tool, *self.args, *([self.target] if self.target else [])]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    risk_level: ToolRisk
    category: ToolCategory | None = None
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_level"] = str(self.risk_level)
        data["category"] = str(self.category) if self.category else None
        return data


@dataclass(frozen=True)
class ActionResult:
    request: ActionRequest
    decision: PolicyDecision
    command: list[str]
    returncode: int | None
    output_summary: str
    stdout: str = ""
    stderr: str = ""
    audit_id: str = ""


@dataclass
class SentinelFinding:
    title: str
    severity: str
    evidence: str
    recommended_remediation: str
    commands: list[str] = field(default_factory=list)
