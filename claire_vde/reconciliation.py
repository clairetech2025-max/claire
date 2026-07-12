from __future__ import annotations

import json
import time
from typing import Any

from claire_are.core import AREStore
from claire_vde.evidence import AdmittedEvidence
from claire_vde.storage import VentureRepository


RECONCILIATION_STATE_NAME = "orphaned_evidence"


def reconcile_orphaned_evidence(
    store: AREStore,
    repository: VentureRepository,
    *,
    since_sequence: int | None = None,
) -> dict[str, Any]:
    """
    Repair subordinate Venture rows that are missing after a successful ARE admission.

    The ARE Truth Spine remains authoritative. This job only backfills the derived
    SQLite projection and advances an idempotent checkpoint.
    """

    checkpoint = repository.get_reconciliation_checkpoint(RECONCILIATION_STATE_NAME)
    start_sequence = max(int(checkpoint), int(since_sequence or 0))
    repaired = 0
    scanned = 0
    skipped = 0
    max_sequence = start_sequence

    truth = getattr(store, "truth", None)
    envelopes = getattr(truth, "envelopes", None)
    if truth is None or envelopes is None:
        return {
            "status": "unavailable",
            "reason": "ARE Truth Spine unavailable",
            "checkpoint_before": start_sequence,
            "checkpoint_after": start_sequence,
            "scanned": 0,
            "repaired": 0,
            "skipped": 0,
        }

    for envelope in envelopes():
        sequence = int(envelope.get("sequence") or 0)
        if sequence <= start_sequence:
            continue
        max_sequence = max(max_sequence, sequence)
        payload = envelope.get("payload") or {}
        record_metadata = dict(payload.get("metadata") or {})
        if str(payload.get("event_type") or "") != "memory":
            continue
        try:
            body = json.loads(str(payload.get("text") or "{}"))
        except Exception:
            skipped += 1
            continue
        metadata = dict(body.get("metadata") or {})
        checksum = str(
            record_metadata.get("checksum")
            or record_metadata.get("content_hash")
            or metadata.get("checksum")
            or metadata.get("content_hash")
            or ""
        )
        if not checksum:
            skipped += 1
            continue
        scanned += 1
        existing = repository.get_evidence_by_checksum(checksum)
        if existing:
            skipped += 1
            continue
        try:
            evidence = AdmittedEvidence(
                title=str(body.get("title") or ""),
                text=str(body.get("text") or ""),
                source=str(body.get("source") or ""),
                collector=str(body.get("collector") or ""),
                plane=str(body.get("plane") or ""),
                value=float(body.get("value") or 0.0),
                precision=float(body.get("precision") or 1.0),
                confidence=float(body.get("confidence") or 0.0),
                are_hash=str(envelope.get("truth_hash") or ""),
                checksum=checksum,
                provenance_url=str(body.get("provenance_url") or ""),
                entity_refs=list(body.get("entity_refs") or []),
                metadata={**metadata, **record_metadata},
                admitted_at=float(body.get("observed_at") or time.time()),
            )
            repository.insert_evidence(evidence)
            repository.upsert_admission_claim(content_hash=checksum, status="committed", are_hash=evidence.are_hash)
            repaired += 1
        except Exception as exc:
            repository.upsert_admission_claim(content_hash=checksum, status="error", last_error=str(exc))
            raise

    repository.set_reconciliation_checkpoint(RECONCILIATION_STATE_NAME, max_sequence)
    return {
        "status": "ok",
        "checkpoint_before": start_sequence,
        "checkpoint_after": max_sequence,
        "scanned": scanned,
        "repaired": repaired,
        "skipped": skipped,
    }
