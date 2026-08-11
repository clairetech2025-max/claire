"""CLAIRE Retrieval Bridge public acquisition interfaces."""

from .contracts import NormalizedDocument, ProvenanceSearchResult
from .pipeline import CRBPipeline

__all__ = ["CRBPipeline", "NormalizedDocument", "ProvenanceSearchResult"]
