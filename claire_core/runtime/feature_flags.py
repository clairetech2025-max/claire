from __future__ import annotations

from claire_core.config import ClaireCoreConfig


def current_feature_flags() -> dict[str, bool]:
    config = ClaireCoreConfig.from_env()
    return {
        "CLAIRE_CORE_ENABLED": config.enabled,
        "CLAIRE_CORE_SHADOW_MODE": config.shadow_mode,
        "CLAIRE_CORE_CONTINUITY_ENABLED": config.continuity_enabled,
        "CLAIRE_CORE_TEMPORAL_ENABLED": config.temporal_enabled,
        "CLAIRE_CORE_COGNITIVE_ENABLED": config.cognitive_enabled,
        "CLAIRE_CORE_PROVENANCE_ENABLED": config.provenance_enabled,
        "CLAIRE_CORE_GOVERNANCE_ENABLED": config.governance_enabled,
    }
