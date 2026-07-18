from __future__ import annotations

import time
from pathlib import Path

from .audit import SentinelAuditLog


class SentinelReportGenerator:
    def __init__(self, audit_log: SentinelAuditLog | None = None) -> None:
        self.audit_log = audit_log or SentinelAuditLog()

    def build_markdown(self, title: str = "CLAIRE Sentinel Report", limit: int = 100) -> str:
        records = self.audit_log.recent(limit)
        lines = [
            f"# {title}",
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            "",
            "## Scope",
            "",
            "This report covers only policy-gated Sentinel actions recorded in the local audit log.",
            "",
            "## Findings",
            "",
            "- No findings are asserted automatically in this prototype. Review command evidence before assigning severity.",
            "",
            "## Commands Run",
            "",
        ]
        if not records:
            lines.append("- No Sentinel actions recorded.")
        for record in records:
            decision = record.get("decision", {})
            allowed = "allowed" if decision.get("allowed") else "blocked"
            lines.append(
                f"- `{record.get('audit_id')}` {allowed}: `{record.get('tool')}` target=`{record.get('target')}` "
                f"risk=`{record.get('risk_level')}` summary={record.get('output_summary')}"
            )
        lines.extend([
            "",
            "## What Was Not Tested",
            "",
            "- No unauthorized targets were tested.",
            "- No credential attacks, phishing, persistence, evasion, exploitation, or destructive actions were performed.",
            "- Any active scans require explicit operator approval and allowlisted targets.",
            "",
            "## Recommended Remediation",
            "",
            "- Review blocked attempts for scope errors.",
            "- Add only owned or explicitly authorized systems to the allowlist.",
            "- Convert confirmed evidence into tracked findings with severity and remediation owners.",
        ])
        return "\n".join(lines) + "\n"

    def write_markdown(self, path: str | Path, title: str = "CLAIRE Sentinel Report") -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.build_markdown(title=title), encoding="utf-8")
        return path
