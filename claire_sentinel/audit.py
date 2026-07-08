from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*['\"]?[^'\"\s]+"),
)


def redact_text(text: str) -> str:
    safe = str(text or "")
    for pattern in SECRET_PATTERNS:
        safe = pattern.sub("[REDACTED_SECRET]", safe)
    return safe


class SentinelAuditLog:
    def __init__(self, path: str | Path = "claire_state/sentinel/actions.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        safe = json.loads(redact_text(json.dumps(record, ensure_ascii=False, default=str)))
        safe.setdefault("audit_id", f"sentinel_audit_{uuid.uuid4().hex[:12]}")
        safe.setdefault("timestamp_ns", time.time_ns())
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, ensure_ascii=False) + "\n")
        return safe

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
