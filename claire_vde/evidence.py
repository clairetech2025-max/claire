from __future__ import annotations

import json
import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any, TYPE_CHECKING

from claire_are.core import AREStore

if TYPE_CHECKING:
    from claire_vde.storage import VentureRepository

VDE_LANE = "business"


@dataclass(frozen=True)
class EvidenceDraft:
    """Normalized collector output. Drafts are not allowed to orient or predict."""

    title: str
    text: str
    source: str
    collector: str
    plane: str
    value: float
    precision: float
    confidence: float
    provenance_url: str = ""
    entity_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    observed_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not str(self.text or "").strip():
            raise ValueError("EvidenceDraft text is required")
        if not str(self.source or "").strip():
            raise ValueError("EvidenceDraft source is required")
        if not str(self.collector or "").strip():
            raise ValueError("EvidenceDraft collector is required")
        if not str(self.plane or "").strip():
            raise ValueError("EvidenceDraft plane is required")
        if not -1.0 <= float(self.value) <= 1.0:
            raise ValueError("EvidenceDraft value must be in [-1, 1]")
        if float(self.precision) <= 0:
            raise ValueError("EvidenceDraft precision must be > 0")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("EvidenceDraft confidence must be in [0, 1]")


@dataclass(frozen=True)
class AdmittedEvidence:
    """ARE-recorded evidence. Only this object may orient Q Insight or FARE."""

    title: str
    text: str
    source: str
    collector: str
    plane: str
    value: float
    precision: float
    confidence: float
    are_hash: str
    checksum: str
    provenance_url: str = ""
    entity_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    admitted_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.are_hash:
            raise ValueError("AdmittedEvidence requires an ARE Truth Spine hash")
        if not self.checksum:
            raise ValueError("AdmittedEvidence requires a checksum")

    def citation(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "collector": self.collector,
            "are_hash": self.are_hash,
            "checksum": self.checksum,
            "provenance_url": self.provenance_url,
        }


def evidence_checksum(draft: EvidenceDraft) -> str:
    payload = {
        "title": draft.title,
        "text": draft.text,
        "source": draft.source,
        "collector": draft.collector,
        "plane": draft.plane,
        "provenance_url": draft.provenance_url,
        "entity_refs": list(draft.entity_refs),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class AdmissionGate:
    """Commits normalized venture evidence into ARE before downstream use."""

    def __init__(self, store: AREStore, repository: "VentureRepository | None" = None) -> None:
        self.store = store
        self.repository = repository

    def admit(self, draft: EvidenceDraft) -> AdmittedEvidence:
        checksum = evidence_checksum(draft)
        if self.repository:
            existing = self.repository.get_evidence_by_checksum(checksum)
            if existing:
                return existing
        payload = {
            "kind": "vde_evidence",
            "title": draft.title,
            "text": draft.text,
            "source": draft.source,
            "collector": draft.collector,
            "plane": draft.plane,
            "value": draft.value,
            "precision": draft.precision,
            "confidence": draft.confidence,
            "provenance_url": draft.provenance_url,
            "entity_refs": list(draft.entity_refs),
            "metadata": dict(draft.metadata),
            "observed_at": draft.observed_at,
        }
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        result = self.store.ingest(
            text=text,
            lane=VDE_LANE,
            source=draft.collector,
            metadata={
                "kind": "vde_evidence",
                "source": draft.source,
                "plane": draft.plane,
                "checksum": checksum,
                "provenance_url": draft.provenance_url,
                "entity_refs": list(draft.entity_refs),
            },
        )
        if not result.get("accepted"):
            raise ValueError(f"Evidence rejected by ARE admission: {result.get('reason')}")
        evidence = AdmittedEvidence(
            title=draft.title,
            text=draft.text,
            source=draft.source,
            collector=draft.collector,
            plane=draft.plane,
            value=draft.value,
            precision=draft.precision,
            confidence=draft.confidence,
            provenance_url=draft.provenance_url,
            entity_refs=list(draft.entity_refs),
            metadata=dict(draft.metadata),
            are_hash=str(result.get("truth_hash") or result.get("sha") or ""),
            checksum=checksum,
        )
        if self.repository:
            self.repository.insert_evidence(evidence)
        return evidence


def evidence_to_dict(evidence: AdmittedEvidence) -> dict[str, Any]:
    return asdict(evidence)
