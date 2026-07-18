from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ClaireCoreConfig:
    data_dir: Path = Path("data/claire_core")
    enabled: bool = False
    shadow_mode: bool = True
    continuity_enabled: bool = True
    temporal_enabled: bool = True
    cognitive_enabled: bool = True
    provenance_enabled: bool = True
    governance_enabled: bool = True

    @classmethod
    def from_env(cls) -> "ClaireCoreConfig":
        return cls(
            data_dir=Path(os.environ.get("CLAIRE_CORE_DATA_DIR", "data/claire_core")),
            enabled=env_bool("CLAIRE_CORE_ENABLED", False),
            shadow_mode=env_bool("CLAIRE_CORE_SHADOW_MODE", True),
            continuity_enabled=env_bool("CLAIRE_CORE_CONTINUITY_ENABLED", True),
            temporal_enabled=env_bool("CLAIRE_CORE_TEMPORAL_ENABLED", True),
            cognitive_enabled=env_bool("CLAIRE_CORE_COGNITIVE_ENABLED", True),
            provenance_enabled=env_bool("CLAIRE_CORE_PROVENANCE_ENABLED", True),
            governance_enabled=env_bool("CLAIRE_CORE_GOVERNANCE_ENABLED", True),
        )

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
