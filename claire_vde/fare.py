from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from claire_vde.recognition_rail import AnalogMatch


@dataclass(frozen=True)
class VentureProjection:
    title: str
    path: str
    confidence: float
    uncertainty: list[str]
    failure_conditions: list[str]
    analogs: list[str]
    are_hashes: list[str]
    citations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FAREProjector:
    """Forward Analog Recall Engine. Projects only from evidence-backed orientation."""

    def project(self, orientation: dict[str, dict[str, Any]], analogs: list[AnalogMatch], limit: int = 3) -> list[VentureProjection]:
        oriented = [state for state in orientation.values() if state.get("bearing") is not None]
        if not oriented or not analogs:
            return []
        pressure = self._plane(orientation, "demand_pressure")
        maturity = self._plane(orientation, "technology_maturity")
        capital = self._plane(orientation, "capital_movement")
        regulation = self._plane(orientation, "regulatory_pressure")
        execution = self._plane(orientation, "execution_risk")
        all_hashes = sorted({hash_ for state in oriented for hash_ in (state.get("are_hashes") or [])})
        confidence = round(max(0.0, min(0.95, sum(float(state.get("confidence") or 0.0) for state in oriented) / len(oriented))), 3)
        top = analogs[: max(1, int(limit))]
        projections: list[VentureProjection] = []
        if maturity > 0.2 and pressure > 0.2:
            projections.append(VentureProjection(
                title="Emerging platform wedge",
                path="Technology maturity and demand pressure are converging; look for a narrow workflow or infrastructure wedge that incumbents have not packaged yet.",
                confidence=confidence,
                uncertainty=["Buyer urgency may be overstated", "Evidence may reflect research interest rather than budget"],
                failure_conditions=["No paid pilots", "No repeatable distribution channel", "Incumbents bundle the feature before a startup can own it"],
                analogs=[match.analog for match in top],
                are_hashes=all_hashes,
            ))
        if regulation > 0.2 and pressure > 0.1:
            projections.append(VentureProjection(
                title="Regulation-forced market",
                path="Regulatory pressure and demand pressure suggest a compliance or auditability product could become mandatory infrastructure.",
                confidence=confidence,
                uncertainty=["Rule timing may slip", "Regulation may favor incumbents"],
                failure_conditions=["Regulation is delayed", "Customers solve with services instead of software"],
                analogs=[match.analog for match in top],
                are_hashes=all_hashes,
            ))
        if capital > 0.2 and execution < 0.4:
            projections.append(VentureProjection(
                title="Capital-backed category formation",
                path="Capital movement with manageable execution risk suggests a category may be forming before a dominant vendor is obvious.",
                confidence=confidence,
                uncertainty=["Capital may be momentum rather than customer pull", "Execution risk may be undermeasured"],
                failure_conditions=["Funding concentrates into incumbents", "Customer adoption lags financing"],
                analogs=[match.analog for match in top],
                are_hashes=all_hashes,
            ))
        return projections[: max(0, int(limit))]

    def _plane(self, orientation: dict[str, dict[str, Any]], name: str) -> float:
        state = orientation.get(name) or {}
        return float(state.get("bearing") or 0.0)
