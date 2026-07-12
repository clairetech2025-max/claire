from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceDraftRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    text: str = Field(..., min_length=1, max_length=8000)
    source: str = Field(..., min_length=1, max_length=200)
    collector: str = Field(..., min_length=1, max_length=100)
    plane: str = Field(..., min_length=1, max_length=100)
    value: float = Field(..., ge=-1.0, le=1.0)
    precision: float = Field(..., gt=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance_url: str = ""
    entity_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectorRunRequest(BaseModel):
    collector: str
    evidence: list[EvidenceDraftRequest] = Field(default_factory=list)


class OpportunityCreateRequest(BaseModel):
    hypothesis: str = Field(..., min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    probability: float = Field(..., ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    falsification_conditions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutcomeRequest(BaseModel):
    outcome: str = Field(..., min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FederalRegisterRunRequest(BaseModel):
    query: str = Field("artificial intelligence", min_length=1, max_length=500)
    cutoff_date: str = Field("2024-01-01", min_length=8, max_length=10)
    per_page: int = Field(20, ge=1, le=100)
    max_pages: int = Field(1, ge=1, le=20)
    user_agent: str = Field(
        "CLAIRE Venture Intelligence Federal Register Collector/1.0 (respectful; contact local-dev)",
        min_length=1,
        max_length=200,
    )
    connect_timeout_s: float = Field(5.0, gt=0)
    read_timeout_s: float = Field(30.0, gt=0)
    retries: int = Field(3, ge=0, le=10)
    backoff_base_s: float = Field(0.5, gt=0)
    respectful_delay_s: float = Field(0.2, ge=0)
    version: str = Field("federal_register_collector_v1", min_length=1, max_length=100)
    admit: bool = True
