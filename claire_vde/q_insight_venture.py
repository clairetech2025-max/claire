from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from claire_vde.evidence import AdmittedEvidence

DEFAULT_PLANES = [
    "technology_maturity",
    "demand_pressure",
    "capital_movement",
    "regulatory_pressure",
    "execution_risk",
]


class Bearing(str, Enum):
    NOT_ORIENTED = "not_oriented"
    LOW_CONFIDENCE = "low_confidence"
    ORIENTED = "oriented"


@dataclass
class PlaneState:
    name: str
    drift: float = 0.0
    last_bearing: float = 0.0
    evidence_log: list[AdmittedEvidence] = field(default_factory=list)
    threshold: float = 0.15
    decay_halflife_s: float = 60 * 60 * 24 * 30


class QInsightField:
    """Evidence-gated venture orientation field. This module does not generate."""

    def __init__(self, planes: list[str] | None = None) -> None:
        names = planes or DEFAULT_PLANES
        self.planes: dict[str, PlaneState] = {name: PlaneState(name=name) for name in names}

    def register_plane(self, name: str, threshold: float = 0.15, decay_halflife_s: float = 60 * 60 * 24 * 30) -> None:
        if name in self.planes:
            raise KeyError(f"Plane '{name}' already registered")
        self.planes[name] = PlaneState(name=name, threshold=threshold, decay_halflife_s=decay_halflife_s)

    def admit(self, evidence: AdmittedEvidence) -> None:
        if evidence.plane not in self.planes:
            raise KeyError(f"Plane '{evidence.plane}' is not registered")
        plane = self.planes[evidence.plane]
        plane.evidence_log.append(evidence)
        self._update_drift(plane)

    def _weighted_evidence(self, plane: PlaneState) -> list[tuple[float, float]]:
        now = time.time()
        weighted: list[tuple[float, float]] = []
        for evidence in plane.evidence_log:
            age_s = max(0.0, now - evidence.admitted_at)
            decay = 0.5 ** (age_s / plane.decay_halflife_s)
            weighted.append((evidence.value, evidence.precision * decay))
        return weighted

    def _combined_estimate(self, plane: PlaneState) -> tuple[float, float] | None:
        weighted = self._weighted_evidence(plane)
        total_w = sum(weight for _, weight in weighted)
        if total_w <= 0:
            return None
        return sum(value * weight for value, weight in weighted) / total_w, total_w

    def _update_drift(self, plane: PlaneState) -> None:
        estimate = self._combined_estimate(plane)
        if estimate is None:
            return
        target, _ = estimate
        plane.drift = target
        if abs(plane.drift - plane.last_bearing) >= plane.threshold:
            plane.last_bearing = plane.drift

    def _confidence(self, plane: PlaneState) -> float:
        n = len(plane.evidence_log)
        if n == 0:
            return 0.0
        estimate = self._combined_estimate(plane)
        weighted = self._weighted_evidence(plane)
        total_w = sum(weight for _, weight in weighted)
        if estimate is None or total_w <= 0:
            return 0.0
        mean, _ = estimate
        variance = sum(weight * (value - mean) ** 2 for value, weight in weighted) / total_w
        agreement = 1.0 / (1.0 + variance * 4.0)
        diversity = min(1.0, len({evidence.source for evidence in plane.evidence_log}) / 3.0)
        volume = min(1.0, n / 5.0)
        return round(0.4 * agreement + 0.3 * diversity + 0.3 * volume, 3)

    def read(self, plane_name: str) -> dict[str, Any]:
        plane = self.planes[plane_name]
        if not plane.evidence_log:
            return {
                "plane": plane_name,
                "bearing_state": Bearing.NOT_ORIENTED.value,
                "bearing": None,
                "confidence": 0.0,
                "evidence_count": 0,
                "note": "No admitted evidence. This plane makes no claim.",
            }
        confidence = self._confidence(plane)
        state = Bearing.ORIENTED if confidence >= 0.4 else Bearing.LOW_CONFIDENCE
        return {
            "plane": plane_name,
            "bearing_state": state.value,
            "bearing": round(plane.last_bearing, 4),
            "raw_drift": round(plane.drift, 4),
            "confidence": confidence,
            "evidence_count": len(plane.evidence_log),
            "sources": sorted({evidence.source for evidence in plane.evidence_log}),
            "are_hashes": [evidence.are_hash for evidence in plane.evidence_log],
        }

    def orientation(self) -> dict[str, dict[str, Any]]:
        return {name: self.read(name) for name in self.planes}
