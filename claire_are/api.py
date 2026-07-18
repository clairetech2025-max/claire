from __future__ import annotations

from fastapi import FastAPI

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_are.gateway import GovernedGateway
from claire_are.schemas import (
    AuditResponse,
    CompleteRequest,
    CompleteResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    RecallRequest,
    RecallResponse,
    VerifyResponse,
)

app = FastAPI(title="CLAIRE ARE Memory Module", version="1.1")
store = AREStore(AREConfig.from_env())
gateway = GovernedGateway(store)


@app.get("/v1/health", response_model=HealthResponse)
def health() -> dict:
    verify = store.verify()
    return {"status": "ok", "root": str(store.config.root), "records": int(verify.get("records") or 0)}


@app.post("/v1/memory/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> dict:
    return store.ingest(text=req.text, lane=req.lane, source=req.source, metadata=req.metadata)


@app.post("/v1/memory/recall", response_model=RecallResponse)
def recall(req: RecallRequest) -> dict:
    return store.recall(query=req.query, lane=req.lane, limit=req.limit)


@app.post("/v1/llm/complete", response_model=CompleteResponse)
def complete(req: CompleteRequest) -> dict:
    return gateway.complete(prompt=req.prompt, lane=req.lane, model=req.model, metadata=req.metadata)


@app.get("/v1/audit/recent", response_model=AuditResponse)
def audit_recent(limit: int = 25) -> dict:
    return {"events": store.audit_recent(limit=limit)}


@app.get("/v1/memory/verify", response_model=VerifyResponse)
def verify() -> dict:
    return store.verify()
