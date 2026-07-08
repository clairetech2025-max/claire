from __future__ import annotations

import hashlib
import json
from typing import Any

from are_memory_store import AREMemoryStore, MemoryEvent
from diode_protocol import DiodeProtocol

from .models import ActionResult

SENTINEL_MEMORY_LANE = "SENTINEL_SECURITY"


class SentinelARECapsuleWriter:
    """Writes safe security evidence summaries into governed ARE memory."""

    def __init__(self, memory_store: AREMemoryStore | None = None, user_id: str = "sentinel") -> None:
        self.memory_store = memory_store or AREMemoryStore()
        self.user_id = user_id

    def write_action_capsule(self, result: ActionResult) -> dict[str, Any]:
        request = result.request
        decision = result.decision
        summary = (
            f"Sentinel {request.tool} action for target '{request.target or 'local'}' "
            f"was {'allowed' if decision.allowed else 'blocked'}; "
            f"risk={decision.risk_level}; reason={decision.reason}; audit_id={result.audit_id}."
        )
        raw_excerpt = {
            "audit_id": result.audit_id,
            "tool": request.tool,
            "target": request.target or "local",
            "operator_reason": request.reason,
            "decision_allowed": decision.allowed,
            "decision_reason": decision.reason,
            "risk_level": str(decision.risk_level),
            "category": str(decision.category) if decision.category else None,
            "dry_run": request.dry_run,
            "returncode": result.returncode,
            "output_summary": result.output_summary,
            "command_shape": self._command_shape(result.command),
        }
        safe_excerpt = DiodeProtocol.redact(json.dumps(raw_excerpt, ensure_ascii=False, sort_keys=True))
        event = MemoryEvent(
            user_id=self.user_id,
            session_id="sentinel",
            lane=SENTINEL_MEMORY_LANE,
            event_type="sentinel_action_capsule",
            summary=DiodeProtocol.redact(summary),
            raw_excerpt=safe_excerpt,
            source="claire_sentinel",
            confidence=1.0,
            provenance_hash=hashlib.sha256(safe_excerpt.encode("utf-8", errors="ignore")).hexdigest(),
            importance_score=0.6 if decision.allowed else 0.4,
            related_entities=[request.tool, request.target or "local", str(decision.risk_level)],
            write_reason="security_action_audit_summary",
            memory_scope="COMPANY_INTERNAL",
        )
        return self.memory_store.append_memory_event(event)

    @staticmethod
    def _command_shape(command: list[str]) -> list[str]:
        shaped: list[str] = []
        for part in command:
            text = str(part)
            if "/" in text and not text.startswith("-"):
                shaped.append(text.rsplit("/", 1)[-1])
            else:
                shaped.append(text)
        return shaped[:20]
