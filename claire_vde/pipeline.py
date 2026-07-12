from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from typing import Any

from claire_are.core import AREStore
from claire_vde.collectors import CollectorRun, EvidenceCollector
from claire_vde.evidence import AdmissionGate, AdmittedEvidence
from claire_vde.fare import FAREProjector
from claire_vde.q_insight_venture import QInsightField
from claire_vde.recognition_rail import RecognitionRail
from claire_vde.sentinel import VDESentinel
from claire_vde.storage import VentureRepository


class VentureDiscoveryEngine:
    """Governed VDE pipeline. Collectors produce drafts; ARE admission comes first."""

    def __init__(
        self,
        store: AREStore,
        *,
        q_insight: QInsightField | None = None,
        recognition_rail: RecognitionRail | None = None,
        fare: FAREProjector | None = None,
        sentinel: VDESentinel | None = None,
        repository: VentureRepository | None = None,
    ) -> None:
        self.store = store
        self.repository = repository
        self.admission = AdmissionGate(store, repository=repository)
        self.q_insight = q_insight or QInsightField()
        self.recognition_rail = recognition_rail or RecognitionRail()
        self.fare = fare or FAREProjector()
        self.sentinel = sentinel or VDESentinel()
        self.admitted: list[AdmittedEvidence] = []

    def ingest_collector(self, collector: EvidenceCollector, run: CollectorRun | None = None) -> dict[str, Any]:
        started_at = time.time()
        run = run or collector.collect()
        admitted: list[AdmittedEvidence] = []
        errors = list(run.errors)
        for draft in run.evidence:
            try:
                evidence = self.admission.admit(draft)
                self.q_insight.admit(evidence)
                self.admitted.append(evidence)
                admitted.append(evidence)
            except Exception as exc:
                errors.append(str(exc))
        self.store.log_event(
            text=f"VDE collector run collector={run.collector} admitted={len(admitted)} errors={len(errors)}",
            lane="audit",
            source="vde_pipeline",
            event_type="vde_collector_run",
            metadata={
                "collector": run.collector,
                "admitted": len(admitted),
                "errors": errors,
                "error_details": run.error_details,
                "next_cursor": run.next_cursor,
                "collector_metadata": run.metadata,
            },
        )
        finished_at = time.time()
        if self.repository:
            self.repository.save_collector_run(
                run_id="vcr_" + uuid.uuid4().hex[:16],
                collector=run.collector,
                admitted_count=len(admitted),
                errors=errors,
                next_cursor=run.next_cursor,
                started_at=started_at,
                finished_at=finished_at,
            )
        return {
            "collector": run.collector,
            "admitted": [item.citation() for item in admitted],
            "errors": errors,
            "next_cursor": run.next_cursor,
        }

    def run(self, collectors: list[EvidenceCollector]) -> dict[str, Any]:
        collector_runs = [self.ingest_collector(collector) for collector in collectors]
        orientation = self.q_insight.orientation()
        analogs = self.recognition_rail.match(orientation)
        projections = self.fare.project(orientation, analogs)
        decisions = self.sentinel.validate_many(projections)
        allowed = [projection.to_dict() | {"sentinel": asdict(decision)} for projection, decision in decisions if decision.allowed]
        blocked = [projection.to_dict() | {"sentinel": asdict(decision)} for projection, decision in decisions if not decision.allowed]
        self.store.log_event(
            text=f"VDE run projections_allowed={len(allowed)} projections_blocked={len(blocked)}",
            lane="audit",
            source="vde_pipeline",
            event_type="vde_run",
            metadata={"allowed": len(allowed), "blocked": len(blocked)},
        )
        if self.repository:
            for projection in projections:
                payload = projection.to_dict()
                event = self.store.log_event(
                    text=f"VDE projection generated title={projection.title} confidence={projection.confidence}",
                    lane="audit",
                    source="vde_pipeline",
                    event_type="vde_projection",
                    metadata=payload,
                )
                self.repository.append_projection_event(
                    event_id="vpe_" + uuid.uuid4().hex[:16],
                    title=projection.title,
                    payload=payload,
                    truth_hash=str(event.get("truth_hash") or ""),
                )
        return {
            "collector_runs": collector_runs,
            "orientation": orientation,
            "analogs": [asdict(match) for match in analogs],
            "projections": allowed,
            "blocked_projections": blocked,
        }
