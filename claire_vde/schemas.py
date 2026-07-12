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
