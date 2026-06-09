from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class WriteBarrierDecision:
    allowed: bool
    target: str
    authoritative: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def writeback_decision(target: str, route_state: dict[str, Any] | None = None, source: str = "", query: str = "", output: str = "") -> WriteBarrierDecision:
    route_state = route_state or {}
    target = str(target or "unknown")

    if target in {"trace", "session_turn"}:
        return WriteBarrierDecision(
            allowed=True,
            target=target,
            authoritative=False,
            reason="Non-authoritative audit/session record.",
        )

    if target in {"durable_fact", "durable_preference", "document_context", "tmf_snapshot"}:
        approved = bool(route_state.get("writeback_approved"))
        return WriteBarrierDecision(
            allowed=approved,
            target=target,
            authoritative=True,
            reason="Authoritative memory write requires explicit WriteBarrier approval.",
        )

    return WriteBarrierDecision(
        allowed=False,
        target=target,
        authoritative=True,
        reason="Unknown write target blocked by WriteBarrier.",
    )


def writeback_allowed(target: str, route_state: dict[str, Any] | None = None, source: str = "", query: str = "", output: str = "") -> bool:
    return writeback_decision(target, route_state, source, query, output).allowed

