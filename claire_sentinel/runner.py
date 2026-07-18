from __future__ import annotations

import shutil
import subprocess

from .audit import SentinelAuditLog, redact_text
from .are_capsules import SentinelARECapsuleWriter
from .models import ActionRequest, ActionResult
from .policy import SentinelPolicy
from .registry import SentinelToolRegistry


class ClaireSentinelRunner:
    """Policy-gated security tool runner. Default use should be dry-run/reporting."""

    def __init__(
        self,
        registry: SentinelToolRegistry | None = None,
        policy: SentinelPolicy | None = None,
        audit_log: SentinelAuditLog | None = None,
        are_writer: SentinelARECapsuleWriter | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.registry = registry or SentinelToolRegistry()
        self.policy = policy or SentinelPolicy()
        self.audit_log = audit_log or SentinelAuditLog()
        self.are_writer = are_writer
        self.timeout_seconds = timeout_seconds

    def inventory(self) -> list[dict[str, object]]:
        return self.registry.installed_inventory()

    def run(self, request: ActionRequest) -> ActionResult:
        tool = self.registry.get(request.tool)
        decision = self.policy.evaluate(request, self.registry)
        command = request.command_preview(tool.command if tool else request.tool)
        returncode: int | None = None
        stdout = ""
        stderr = ""
        output_summary = decision.reason

        if decision.allowed:
            executable = shutil.which(command[0])
            if not executable:
                decision = type(decision)(False, f"Tool is registered but not installed: {command[0]}", decision.risk_level, decision.category)
                output_summary = decision.reason
            elif request.dry_run:
                command[0] = executable
                output_summary = "Dry run only; command not executed."
            else:
                command[0] = executable
                try:
                    completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
                    returncode = completed.returncode
                    stdout = redact_text(completed.stdout or "")
                    stderr = redact_text(completed.stderr or "")
                    output_summary = self._summarize(stdout, stderr, returncode)
                except subprocess.TimeoutExpired:
                    returncode = 124
                    output_summary = f"Command timed out after {self.timeout_seconds} seconds."

        audit_record = self.audit_log.append({
            "tool": request.tool,
            "target": request.target,
            "reason": request.reason,
            "command": command,
            "decision": decision.to_dict(),
            "returncode": returncode,
            "output_summary": output_summary,
            "risk_level": str(decision.risk_level),
            "dry_run": request.dry_run,
        })
        result = ActionResult(request, decision, command, returncode, output_summary, stdout, stderr, audit_record["audit_id"])
        if self.are_writer is not None:
            self.are_writer.write_action_capsule(result)
        return result

    @staticmethod
    def _summarize(stdout: str, stderr: str, returncode: int | None) -> str:
        text = "\n".join(part for part in [stdout, stderr] if part).strip()
        if not text:
            return f"Command exited with code {returncode}; no output."
        lines = text.splitlines()
        preview = " | ".join(lines[:5])
        if len(preview) > 600:
            preview = preview[:597] + "..."
        return f"Command exited with code {returncode}; output preview: {preview}"
