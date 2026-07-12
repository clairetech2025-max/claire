from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from claire_are.core import AREStore
from claire_vde.storage import VentureRepository


@dataclass(frozen=True)
class OpportunityHypothesis:
    hypothesis: str
    evidence_ids: list[str]
    confidence: float
    probability: float
    assumptions: list[str] = field(default_factory=list)
    falsification_conditions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class OpportunityLedger:
    """Append-only venture hypothesis and outcome ledger."""

    def __init__(self, store: AREStore, repository: VentureRepository) -> None:
        self.store = store
        self.repository = repository

    def create_hypothesis(self, hypothesis: OpportunityHypothesis) -> dict[str, Any]:
        opportunity_id = "opp_" + uuid.uuid4().hex[:16]
        return self._append(
            opportunity_id=opportunity_id,
            event_type="hypothesis_created",
            payload={
                "hypothesis": hypothesis.hypothesis,
                "evidence_ids": list(hypothesis.evidence_ids),
                "confidence": float(hypothesis.confidence),
                "probability": float(hypothesis.probability),
                "assumptions": list(hypothesis.assumptions),
                "falsification_conditions": list(hypothesis.falsification_conditions),
                "metadata": dict(hypothesis.metadata),
            },
        )

    def append_outcome(
        self,
        *,
        opportunity_id: str,
        outcome: str,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._append(
            opportunity_id=opportunity_id,
            event_type="outcome_recorded",
            payload={
                "outcome": outcome,
                "evidence_ids": list(evidence_ids or []),
                "metadata": dict(metadata or {}),
            },
        )

    def list_events(self, opportunity_id: str | None = None) -> list[dict[str, Any]]:
        return self.repository.list_opportunity_events(opportunity_id)

    def _append(self, *, opportunity_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = "ople_" + uuid.uuid4().hex[:16]
        text = json.dumps(
            {
                "kind": "venture_opportunity_event",
                "event_id": event_id,
                "opportunity_id": opportunity_id,
                "event_type": event_type,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        result = self.store.log_event(
            text=text,
            lane="business",
            source="venture_opportunity_ledger",
            event_type="venture_opportunity",
            metadata={"opportunity_id": opportunity_id, "event_id": event_id, "event_type": event_type},
        )
        truth_hash = str(result.get("truth_hash") or "")
        self.repository.append_opportunity_event(
            event_id=event_id,
            opportunity_id=opportunity_id,
            event_type=event_type,
            payload=payload,
            truth_hash=truth_hash,
            created_at=time.time(),
        )
        return {
            "event_id": event_id,
            "opportunity_id": opportunity_id,
            "event_type": event_type,
            "truth_hash": truth_hash,
            "payload": payload,
        }
