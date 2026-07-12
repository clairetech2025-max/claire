from __future__ import annotations

from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde.collectors import NotConfiguredCollector, StaticEvidenceCollector, collector_registry
from claire_vde.evidence import AdmissionGate, EvidenceDraft, evidence_to_dict
from claire_vde.federal_register import FederalRegisterCollector, FederalRegisterCollectorConfig
from claire_vde.ledger import OpportunityHypothesis, OpportunityLedger
from claire_vde.pipeline import VentureDiscoveryEngine
from claire_vde.reconciliation import reconcile_orphaned_evidence
from claire_vde.q_insight_venture import QInsightField
from claire_vde.recognition_rail import RecognitionRail
from claire_vde.security import AccessContext, VentureSecurity, security_from_env
from claire_vde.schemas import CollectorRunRequest, EvidenceDraftRequest, FederalRegisterRunRequest, OpportunityCreateRequest, OutcomeRequest
from claire_vde.storage import VentureRepository


app = FastAPI(title="CLAIRE Venture Intelligence Engine", version="0.1")
store = AREStore(AREConfig.from_env())
repository = VentureRepository()
security = security_from_env(repository)


def require_access(action: str):
    def _dependency(request: Request) -> AccessContext:
        return security.authorize(request, action)

    return Depends(_dependency)


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
    backend = repository.describe_backend()
    return {
        "status": "ok" if verify.get("valid") else "degraded",
        "truth_spine": verify,
        "backend": backend["backend"],
        "database": backend["locator"],
        "doctrine": "ARE Truth Spine is authority; metadata and indexes are downstream.",
    }


@app.get("/v1/venture/collectors")
def collectors() -> dict:
    return {"collectors": collector_registry()}


@app.post("/v1/venture/evidence/admit")
def admit_evidence(req: EvidenceDraftRequest, _auth: AccessContext = require_access("write")) -> dict:
    admitted = AdmissionGate(store, repository=repository).admit(_draft(req))
    return {"evidence": evidence_to_dict(admitted), "truth_spine_authority": admitted.are_hash}


@app.post("/v1/venture/run")
def run_static_collectors(req: CollectorRunRequest, _auth: AccessContext = require_access("write")) -> dict:
    collector = StaticEvidenceCollector(req.collector, [_draft(item) for item in req.evidence])
    return _engine().run([collector])


@app.post("/v1/venture/collectors/{collector_name}/run")
def run_registered_collector(collector_name: str, _auth: AccessContext = require_access("write")) -> dict:
    if collector_name == "federal_register":
        return run_federal_register(FederalRegisterRunRequest())
    return _engine().ingest_collector(NotConfiguredCollector(collector_name))


@app.post("/v1/venture/federal-register/run")
def run_federal_register(req: FederalRegisterRunRequest, _auth: AccessContext = require_access("write")) -> dict:
    config = FederalRegisterCollectorConfig(
        query=req.query,
        cutoff_date=req.cutoff_date,
        per_page=req.per_page,
        max_pages=req.max_pages,
        user_agent=req.user_agent,
        connect_timeout_s=req.connect_timeout_s,
        read_timeout_s=req.read_timeout_s,
        retries=req.retries,
        backoff_base_s=req.backoff_base_s,
        respectful_delay_s=req.respectful_delay_s,
        version=req.version,
    )
    collector = FederalRegisterCollector(repository=repository, config=config, cursor=repository.get_collector_cursor("federal_register"))
    run = collector.collect()
    pipeline_result = _engine().ingest_collector(collector, run=run) if req.admit else None
    return {
        "collector_run": {
            "collector": run.collector,
            "errors": run.errors,
            "error_details": run.error_details,
            "next_cursor": run.next_cursor,
            "metadata": run.metadata,
            "evidence": [evidence_to_dict(item) for item in run.evidence],
            "duplicates": run.metadata.get("duplicates", []),
        },
        "pipeline_result": pipeline_result,
    }


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
def create_opportunity(req: OpportunityCreateRequest, _auth: AccessContext = require_access("write")) -> dict:
    ledger = OpportunityLedger(store, repository)
    try:
        return ledger.create_hypothesis(OpportunityHypothesis(**req.model_dump()))
    except ValueError as exc:
        if str(exc).startswith("replayed_evidence"):
            raise HTTPException(status_code=409, detail=str(exc))
        raise


@app.post("/v1/venture/opportunities/{opportunity_id}/outcomes")
def append_outcome(opportunity_id: str, req: OutcomeRequest, _auth: AccessContext = require_access("write")) -> dict:
    return OpportunityLedger(store, repository).append_outcome(
        opportunity_id=opportunity_id,
        outcome=req.outcome,
        evidence_ids=req.evidence_ids,
        metadata=req.metadata,
    )


@app.get("/v1/venture/opportunities")
def list_opportunities(opportunity_id: str | None = None) -> dict:
    return {"events": OpportunityLedger(store, repository).list_events(opportunity_id)}


@app.post("/v1/venture/reconcile-orphans")
def reconcile_orphans(_auth: AccessContext = require_access("write")) -> dict:
    return reconcile_orphaned_evidence(store, repository)
