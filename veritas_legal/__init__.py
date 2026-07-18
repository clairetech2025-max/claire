"""Veritas Legal evidence organization prototype.

This package is local-only and research-support only. It does not provide legal
advice, file documents, contact courts, or perform real-world legal actions.
"""

from .engine import (
    Contradiction,
    EvidenceEngine,
    EvidenceRecord,
    claire_explains_summary,
    detect_contradictions,
    generate_review_packet,
    safe_id,
    source_doc_id_for,
)

__all__ = [
    "Contradiction",
    "EvidenceEngine",
    "EvidenceRecord",
    "claire_explains_summary",
    "detect_contradictions",
    "generate_review_packet",
    "safe_id",
    "source_doc_id_for",
]
