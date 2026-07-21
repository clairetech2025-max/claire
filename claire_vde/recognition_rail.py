from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HistoricalAnalog:
    name: str
    pattern: str
    plane_weights: dict[str, float]
    failure_lessons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalogMatch:
    analog: str
    pattern: str
    score: float
    matched_planes: list[str]
    failure_lessons: list[str]
    are_hashes: list[str]


DEFAULT_ANALOGS = [
    HistoricalAnalog("AWS", "latent infrastructure demand becomes a platform market", {"demand_pressure": 0.8, "technology_maturity": 0.6, "capital_movement": 0.3}),
    HistoricalAnalog("Stripe", "developer pain plus regulatory/payment complexity creates an API wedge", {"demand_pressure": 0.7, "regulatory_pressure": 0.4, "technology_maturity": 0.5}),
    HistoricalAnalog("NVIDIA", "specialized compute becomes strategic infrastructure after workload inflection", {"technology_maturity": 0.8, "demand_pressure": 0.7, "capital_movement": 0.5}),
    HistoricalAnalog("OpenAI", "research capability crosses product and platform threshold", {"technology_maturity": 0.9, "capital_movement": 0.6, "execution_risk": -0.3}),
    HistoricalAnalog("Cloudflare", "security and network infrastructure compress into developer-accessible service", {"demand_pressure": 0.6, "technology_maturity": 0.5, "execution_risk": -0.2}),
    HistoricalAnalog("Snowflake", "cloud transition creates a new data-system buyer and architecture", {"demand_pressure": 0.7, "capital_movement": 0.5, "technology_maturity": 0.6}),
    HistoricalAnalog("Palantir", "high-stakes institutions buy evidence infrastructure when auditability matters", {"regulatory_pressure": 0.5, "demand_pressure": 0.6, "execution_risk": -0.5}),
    HistoricalAnalog("SpaceX", "government demand and technical maturity converge against incumbent cost structure", {"government_spending": 0.8, "technology_maturity": 0.7, "execution_risk": -0.8}),
    HistoricalAnalog("Tesla", "regulatory pressure and technology maturity reshape a capital-intensive market", {"regulatory_pressure": 0.6, "technology_maturity": 0.6, "capital_movement": 0.4, "execution_risk": -0.7}),
]


class RecognitionRail:
    def __init__(self, analogs: list[HistoricalAnalog] | None = None) -> None:
        self.analogs = analogs or DEFAULT_ANALOGS

    def match(self, orientation: dict[str, dict[str, Any]], limit: int = 5) -> list[AnalogMatch]:
        matches: list[AnalogMatch] = []
        for analog in self.analogs:
            total = 0.0
            matched_planes: list[str] = []
            hashes: list[str] = []
            for plane, expected in analog.plane_weights.items():
                state = orientation.get(plane) or {}
                if state.get("bearing") is None:
                    continue
                bearing = float(state.get("bearing") or 0.0)
                confidence = float(state.get("confidence") or 0.0)
                contribution = max(0.0, 1.0 - abs(expected - bearing)) * confidence
                if contribution > 0:
                    total += contribution
                    matched_planes.append(plane)
                    hashes.extend(str(item) for item in state.get("are_hashes") or [])
            if matched_planes:
                matches.append(AnalogMatch(
                    analog=analog.name,
                    pattern=analog.pattern,
                    score=round(total / max(1, len(analog.plane_weights)), 3),
                    matched_planes=matched_planes,
                    failure_lessons=list(analog.failure_lessons),
                    are_hashes=sorted(set(hashes)),
                ))
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[: max(0, int(limit))]
