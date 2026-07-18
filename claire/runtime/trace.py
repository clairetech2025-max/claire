from __future__ import annotations

from typing import Any


def gyro_trace_object(
    *,
    gyro_bearing: dict[str, Any],
    loopback_triggered: bool,
    loopback_reason: str,
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "lane": gyro_bearing.get("lane"),
        "intent": gyro_bearing.get("intent"),
        "authority": gyro_bearing.get("authority"),
        "risk": gyro_bearing.get("risk"),
        "memory_eligibility": gyro_bearing.get("memory_eligibility"),
        "source_provenance": gyro_bearing.get("source_provenance"),
        "continuity": gyro_bearing.get("continuity"),
        "output_boundary": gyro_bearing.get("output_boundary"),
        "loopback_triggered": bool(loopback_triggered),
        "loopback_reason": str(loopback_reason or ""),
        "answer_mode": answer_mode,
    }
