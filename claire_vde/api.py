from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde.collectors import NotConfiguredCollector, StaticEvidenceCollector, collector_registry
from claire_vde.evidence import AdmissionGate, EvidenceDraft, evidence_to_dict
from claire_vde.ledger import OpportunityHypothesis, OpportunityLedger
from claire_vde.pipeline import VentureDiscoveryEngine
from claire_vde.q_insight_venture import QInsightField
from claire_vde.recognition_rail import RecognitionRail
from claire_vde.schemas import CollectorRunRequest, EvidenceDraftRequest, OpportunityCreateRequest, OutcomeRequest
from claire_vde.storage import VentureRepository


app = FastAPI(title="CLAIRE Venture Intelligence Engine", version="0.1")
store = AREStore(AREConfig.from_env())
repository = VentureRepository()


def _engine() -> VentureDiscoveryEngine:
    field = QInsightField()
    for evidence in repository.list_evidence(limit=10000):
        try:
            field.admit(evidence)
        except KeyError:
            continue
    return VentureDiscoveryEngine(store, q_insight=field, repository=repository)


def _draft(req: EvidenceDraftRequest) -> EvidenceDraft:
    return EvidenceDraft(**req.model_dump())


@app.get("/v1/venture/health")
def health() -> dict:
    verify = store.verify()
    return {
        "status": "ok" if verify.get("valid") else "degraded",
        "truth_spine": verify,
        "database": str(repository.db_path),
        "doctrine": "ARE Truth Spine is authority; metadata and indexes are downstream.",
    }


@app.get("/v1/venture/collectors")
def collectors() -> dict:
    return {"collectors": collector_registry()}


@app.post("/v1/venture/evidence/admit")
def admit_evidence(req: EvidenceDraftRequest) -> dict:
    admitted = AdmissionGate(store, repository=repository).admit(_draft(req))
    return {"evidence": evidence_to_dict(admitted), "truth_spine_authority": admitted.are_hash}


@app.post("/v1/venture/run")
def run_static_collectors(req: CollectorRunRequest) -> dict:
    collector = StaticEvidenceCollector(req.collector, [_draft(item) for item in req.evidence])
    return _engine().run([collector])


@app.post("/v1/venture/collectors/{collector_name}/run")
def run_registered_collector(collector_name: str) -> dict:
    return _engine().ingest_collector(NotConfiguredCollector(collector_name))


@app.get("/v1/venture/orientation")
def orientation() -> dict:
    return {"orientation": _engine().q_insight.orientation()}


@app.get("/v1/venture/recognition")
def recognition(limit: int = 5) -> dict:
    engine = _engine()
    orientation_state = engine.q_insight.orientation()
    return {"analogs": [asdict(item) for item in RecognitionRail().match(orientation_state, limit=limit)]}


@app.get("/v1/venture/projections")
def projections() -> dict:
    engine = _engine()
    orientation_state = engine.q_insight.orientation()
    analogs = engine.recognition_rail.match(orientation_state)
    generated = engine.fare.project(orientation_state, analogs)
    decisions = engine.sentinel.validate_many(generated)
    return {
        "projections": [
            projection.to_dict() | {"sentinel": asdict(decision)}
            for projection, decision in decisions
        ]
    }


@app.post("/v1/venture/opportunities")
def create_opportunity(req: OpportunityCreateRequest) -> dict:
    ledger = OpportunityLedger(store, repository)
    return ledger.create_hypothesis(OpportunityHypothesis(**req.model_dump()))


@app.post("/v1/venture/opportunities/{opportunity_id}/outcomes")
def append_outcome(opportunity_id: str, req: OutcomeRequest) -> dict:
    return OpportunityLedger(store, repository).append_outcome(
        opportunity_id=opportunity_id,
        outcome=req.outcome,
        evidence_ids=req.evidence_ids,
        metadata=req.metadata,
    )


@app.get("/v1/venture/opportunities")
def list_opportunities(opportunity_id: str | None = None) -> dict:
    return {"events": OpportunityLedger(store, repository).list_events(opportunity_id)}
