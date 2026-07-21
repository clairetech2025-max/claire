from __future__ import annotations

from dataclasses import dataclass, field

from claire_vde.fare import VentureProjection


@dataclass(frozen=True)
class SentinelDecision:
    allowed: bool
    summary: str
    rules_triggered: list[str] = field(default_factory=list)


class VDESentinel:
    """Blocks unsupported venture conclusions before human decision."""

    def validate_projection(self, projection: VentureProjection) -> SentinelDecision:
        rules: list[str] = []
        if not projection.are_hashes:
            rules.append("missing_are_evidence")
        if not projection.analogs:
            rules.append("missing_historical_analog")
        if projection.confidence <= 0:
            rules.append("missing_confidence")
        if not projection.failure_conditions:
            rules.append("missing_failure_conditions")
        if rules:
            return SentinelDecision(False, "Projection blocked; required support is missing.", rules)
        return SentinelDecision(True, "Projection allowed for human review.", [])

    def validate_many(self, projections: list[VentureProjection]) -> list[tuple[VentureProjection, SentinelDecision]]:
        return [(projection, self.validate_projection(projection)) for projection in projections]
