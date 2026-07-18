from __future__ import annotations

from claire_core.capability_registry import CapabilityRegistry
from claire_core.config import ClaireCoreConfig
from claire_core.models import CapabilityReport


class ClaireCore:
    """Thin coordination wrapper around the existing CLAIRE runtime modules."""

    def __init__(
        self,
        *,
        config: ClaireCoreConfig | None = None,
        registry: CapabilityRegistry | None = None,
    ) -> None:
        self.config = config or ClaireCoreConfig.from_env()
        self.config.ensure()
        self.registry = registry or CapabilityRegistry.detect_default()

    def capability_report(self) -> CapabilityReport:
        return self.registry.report()
