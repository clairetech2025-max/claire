from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedDocument:
    """Provider-independent, immutable acquisition result presented to CLAIRE's parser."""

    provider: str
    provider_document_id: str
    original_uri: str
    original_path: str
    title: str
    filename: str
    mime_type: str
    staged_extension: str
    content: bytes = field(repr=False)
    content_hash: str = ""
    created_time: str = ""
    modified_time: str = ""
    acquired_at: str = ""
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def provenance(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("content", None)
        return data


@dataclass(frozen=True)
class ProvenanceSearchResult:
    query: str
    matched_excerpt: str
    provider: str
    provider_document_id: str
    original_uri: str
    original_path: str
    title: str
    filename: str
    mime_type: str
    source_content_hash: str
    parser_chunk_id: str
    parser_chunk_hash: str
    extraction_method: str
    source_created_time: str
    source_modified_time: str
    retrieval_timestamp: str
    are_truth_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
