from __future__ import annotations

from enum import Enum
from pathlib import Path

from claire_core.models import CapabilityReport, EngineStatus, utc_now_iso


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, EngineStatus] = {}

    def register(self, status: EngineStatus) -> None:
        self._items[status.name] = status

    def report(self) -> CapabilityReport:
        return CapabilityReport(
            generated_at=utc_now_iso(),
            capabilities=sorted(self._items.values(), key=lambda item: item.name),
        )

    @classmethod
    def detect_default(cls) -> "CapabilityRegistry":
        registry = cls()
        specs = [
            ("ARE", "Continuity", "claire_are/core.py", CapabilityStatus.AVAILABLE, True),
            ("Ember", "Continuity", "claire_continuity/core.py", CapabilityStatus.PARTIAL, False),
            ("Chronos", "Temporal", "temporal_engine.py", CapabilityStatus.AVAILABLE, True),
            ("Recognition Rail", "Cognitive", "claire_runtime_truth.py", CapabilityStatus.PARTIAL, True),
            ("Q Insight 360x360", "Cognitive", "claire_runtime_truth.py", CapabilityStatus.PARTIAL, True),
            ("Gyro", "Cognitive", "claire/runtime/gyro.py", CapabilityStatus.AVAILABLE, True),
            ("TrailLink", "Provenance", "claire_runtime_truth.py", CapabilityStatus.PARTIAL, True),
            ("Truth Spine", "Provenance", "claire_runtime_truth.py", CapabilityStatus.AVAILABLE, True),
            ("3CRP", "Governance", "claire_runtime_truth.py", CapabilityStatus.PARTIAL, True),
            ("Sentinel", "Governance", "claire_sentinel/policy.py", CapabilityStatus.PARTIAL, False),
            ("EchoShield", "Governance", "claire_core/adapters/echoshield.py", CapabilityStatus.AVAILABLE, True),
            ("Lycanthrope", "Governance", "claire_core/adapters/lycanthrope.py", CapabilityStatus.AVAILABLE, False),
            ("SweeperBots", "Governance", "claire_core/adapters/sweeperbots.py", CapabilityStatus.AVAILABLE, False),
        ]
        for name, engine, path, status, active in specs:
            exists = Path(path).exists()
            registry.register(
                EngineStatus(
                    name=name,
                    public_engine=engine,
                    status=status.value if exists else CapabilityStatus.UNAVAILABLE.value,
                    implementation_path=path,
                    active=active and exists,
                    production_permission=active and exists and status == CapabilityStatus.AVAILABLE,
                    limitations=() if status == CapabilityStatus.AVAILABLE else ("partial integration",),
                    last_successful_health_check=utc_now_iso() if exists else "",
                )
            )
        return registry
