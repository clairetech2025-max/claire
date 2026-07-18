from __future__ import annotations

from dataclasses import asdict
from typing import Any

from claire_core import ClaireCore
from claire_core.runtime.feature_flags import current_feature_flags


def core_health() -> dict[str, Any]:
    core = ClaireCore()
    return {
        "status": "AVAILABLE",
        "feature_flags": current_feature_flags(),
        "capabilities": [asdict(item) for item in core.capability_report().capabilities],
    }
