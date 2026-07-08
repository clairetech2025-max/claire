from __future__ import annotations

from dataclasses import dataclass, field


VALID_LANES = {"legal", "architecture", "business", "general", "audit"}


@dataclass
class DiodeDecision:
    allowed: bool
    reason: str
    rules_triggered: list[str] = field(default_factory=list)


class DiodeGuard:
    """
    Lane-scoped admission and read rules.

    Default policy is conservative: memories are readable only from the same
    lane. The audit lane is internal and is never returned as user memory.
    """

    def __init__(self, *, allowed_sources: set[str] | None = None) -> None:
        self.allowed_sources = set(allowed_sources or set())

    def check_write(self, *, lane: str, source: str, text: str) -> DiodeDecision:
        if lane not in VALID_LANES:
            return DiodeDecision(False, f"lane not allowed: {lane}", ["invalid_lane"])
        if self.allowed_sources and source not in self.allowed_sources:
            return DiodeDecision(False, f"source not allowed: {source}", ["invalid_source"])
        if not text.strip():
            return DiodeDecision(False, "empty memory rejected", ["empty_text"])
        lowered = text.lower()
        if any(marker in lowered for marker in ("api_key=", "password=", "private key", "bearer ")):
            return DiodeDecision(False, "secret-like content rejected", ["secret_like_content"])
        return DiodeDecision(True, "accepted", [])

    def can_read(self, *, requesting_lane: str, record_lane: str) -> bool:
        if record_lane == "audit":
            return False
        return requesting_lane == record_lane
