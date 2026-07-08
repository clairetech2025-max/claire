from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import ActionRequest, PolicyDecision, ToolCategory, ToolDefinition, ToolRisk
from .registry import SentinelToolRegistry


@dataclass
class SentinelPolicy:
    allowlist: set[str] = field(default_factory=set)
    allow_loopback: bool = True
    require_approval_for_active_scans: bool = True

    @classmethod
    def from_json(cls, path: str | Path) -> "SentinelPolicy":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return cls(
            allowlist={str(item).lower() for item in data.get("allowlist", [])},
            allow_loopback=bool(data.get("allow_loopback", True)),
            require_approval_for_active_scans=bool(data.get("require_approval_for_active_scans", True)),
        )

    def evaluate(self, request: ActionRequest, registry: SentinelToolRegistry) -> PolicyDecision:
        tool = registry.get(request.tool)
        if tool is None:
            return PolicyDecision(False, f"Unknown or unregistered tool: {request.tool}", ToolRisk.FORBIDDEN)
        if tool.category == ToolCategory.FORBIDDEN_HIGH_RISK or tool.risk == ToolRisk.FORBIDDEN:
            return PolicyDecision(False, f"Tool is forbidden/high-risk by Sentinel policy: {tool.name}", ToolRisk.FORBIDDEN, tool.category)
        if not request.reason.strip():
            return PolicyDecision(False, "Operator reason is required for every security action.", tool.risk, tool.category)
        if tool.network_action and not self._target_allowed(request.target):
            return PolicyDecision(False, f"Target is not on the Sentinel allowlist: {request.target}", tool.risk, tool.category)
        if tool.active_scan and self.require_approval_for_active_scans and not request.operator_approved:
            return PolicyDecision(False, "Active scan requires explicit operator approval.", tool.risk, tool.category, requires_approval=True)
        arg_check = self._args_allowed(tool, request.args)
        if arg_check:
            return PolicyDecision(False, arg_check, tool.risk, tool.category)
        return PolicyDecision(True, "Allowed by Sentinel defensive policy.", tool.risk, tool.category)

    def _target_allowed(self, target: str) -> bool:
        normalized = str(target or "").strip().lower().rstrip(".")
        if not normalized:
            return False
        if normalized in self.allowlist:
            return True
        if self.allow_loopback and normalized in {"localhost", "ip6-localhost"}:
            return True
        try:
            ip = ipaddress.ip_address(normalized)
            if self.allow_loopback and ip.is_loopback:
                return True
            return normalized in self.allowlist
        except ValueError:
            return False

    @staticmethod
    def _args_allowed(tool: ToolDefinition, args: tuple[str, ...]) -> str:
        lowered = tuple(str(arg).lower() for arg in args)
        for forbidden in tool.forbidden_args:
            if forbidden.lower() in lowered:
                return f"Forbidden argument for {tool.name}: {forbidden}"
        if tool.allowed_args:
            for arg in lowered:
                if arg.startswith("-") and arg not in tool.allowed_args:
                    return f"Argument not allowed for {tool.name}: {arg}"
        return ""
