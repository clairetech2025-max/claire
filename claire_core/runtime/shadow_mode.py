from __future__ import annotations

from dataclasses import asdict
from typing import Any

from claire_core.capability_registry import CapabilityRegistry
from claire_core.runtime.feature_flags import current_feature_flags


def evaluate_shadow(runtime_result: dict[str, Any]) -> dict[str, Any]:
    """Non-mutating parity packet for the current runtime output."""

    report = CapabilityRegistry.detect_default().report()
    return {
        "shadow_mode": current_feature_flags()["CLAIRE_CORE_SHADOW_MODE"],
        "authoritative_runtime": "existing_claire_runtime",
        "observed_lane": runtime_result.get("lane"),
        "observed_memory_written": bool(runtime_result.get("memory_written")),
        "observed_truth_spine": runtime_result.get("truth_spine") or {},
        "capability_count": len(report.capabilities),
        "capabilities": [asdict(item) for item in report.capabilities],
    }
