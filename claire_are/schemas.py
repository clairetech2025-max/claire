from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

LaneName = Literal["legal", "architecture", "business", "general"]


class IngestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    lane: LaneName = "general"
    source: str = Field("unknown", min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    ts: int
    sha: str
    text: str
    lane: str
    source: str
    truth_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    status: str
    lane: str
    source: str
    sha: str
    truth_hash: str
    accepted: bool
    reason: str


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    lane: LaneName = "general"
    limit: int = Field(8, ge=1, le=50)


class RecallResponse(BaseModel):
    query: str
    lane: str
    recall_event_sha: str
    memories: list[MemoryRecord]


class CompleteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    lane: LaneName = "general"
    model: str = Field("local/stub", min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompleteResponse(BaseModel):
    prompt: str
    lane: str
    model: str
    recall_event_sha: str
    completion_event_sha: str
    memories_used: list[MemoryRecord]
    answer: str


class VerifyResponse(BaseModel):
    valid: bool
    records: int = 0
    previous_hash: str = ""
    reason: str | None = None
    index: int | None = None


class HealthResponse(BaseModel):
    status: str
    root: str
    records: int


class AuditResponse(BaseModel):
    events: list[dict[str, Any]]
