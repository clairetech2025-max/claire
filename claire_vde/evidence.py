from __future__ import annotations

import json
import hashlib
import time
import threading
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

    _lock_guard = threading.RLock()
    _content_locks: dict[str, threading.RLock] = {}

    def __init__(self, store: AREStore, repository: "VentureRepository | None" = None) -> None:
        self.store = store
        self.repository = repository

    def admit(self, draft: EvidenceDraft) -> AdmittedEvidence:
        checksum = evidence_checksum(draft)
        lock = self._content_lock(checksum)
        with lock:
            if self.repository:
                existing = self.repository.get_evidence_by_checksum(checksum)
                if existing:
                    return existing
            existing_are = self._find_existing_are_admission(checksum)
            if existing_are:
                if self.repository:
                    self.repository.insert_evidence(existing_are)
                    self.repository.upsert_admission_claim(
                        content_hash=checksum,
                        status="committed",
                        are_hash=existing_are.are_hash,
                    )
                return existing_are
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
                "metadata": {**dict(draft.metadata), "content_hash": checksum},
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
                    "content_hash": checksum,
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
                self.repository.upsert_admission_claim(
                    content_hash=checksum,
                    status="committed",
                    are_hash=evidence.are_hash,
                )
            return evidence

    @classmethod
    def _content_lock(cls, content_hash: str) -> threading.RLock:
        key = str(content_hash or "")
        with cls._lock_guard:
            lock = cls._content_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                cls._content_locks[key] = lock
            return lock

    def _find_existing_are_admission(self, checksum: str) -> AdmittedEvidence | None:
        truth = getattr(self.store, "truth", None)
        envelopes = getattr(truth, "envelopes", None)
        if truth is None or envelopes is None:
            return None
        for envelope in reversed(list(envelopes())):
            payload = envelope.get("payload") or {}
            decision = envelope.get("decision") or {}
            record_metadata = dict(payload.get("metadata") or {})
            if not decision.get("allowed"):
                continue
            if str(payload.get("event_type") or "") != "memory":
                continue
            try:
                body = json.loads(str(payload.get("text") or "{}"))
            except Exception:
                continue
            metadata = dict(body.get("metadata") or {})
            marker = str(record_metadata.get("kind") or metadata.get("kind") or "")
            if marker != "vde_evidence":
                continue
            fingerprint = str(
                record_metadata.get("checksum")
                or record_metadata.get("content_hash")
                or metadata.get("checksum")
                or metadata.get("content_hash")
                or ""
            )
            if fingerprint != str(checksum or ""):
                continue
            observed_at = body.get("observed_at")
            admitted_at = float(observed_at) if observed_at is not None else time.time()
            return AdmittedEvidence(
                title=str(body.get("title") or ""),
                text=str(body.get("text") or ""),
                source=str(body.get("source") or ""),
                collector=str(body.get("collector") or ""),
                plane=str(body.get("plane") or ""),
                value=float(body.get("value") or 0.0),
                precision=float(body.get("precision") or 1.0),
                confidence=float(body.get("confidence") or 0.0),
                are_hash=str(envelope.get("truth_hash") or ""),
                checksum=fingerprint or str(checksum or ""),
                provenance_url=str(body.get("provenance_url") or ""),
                entity_refs=list(body.get("entity_refs") or []),
                metadata={**metadata, **record_metadata},
                admitted_at=admitted_at,
            )
        return None


def evidence_to_dict(evidence: AdmittedEvidence) -> dict[str, Any]:
    return asdict(evidence)
