from __future__ import annotations

import json
import hashlib
import math
import re
from pathlib import Path
from typing import Any, Callable, Iterable


VECTOR_DIM = 384


def faiss_status() -> dict[str, Any]:
    try:
        import faiss  # type: ignore  # noqa: F401
        import numpy  # type: ignore  # noqa: F401
    except Exception as exc:
        return {"available": False, "reason": f"FAISS unavailable: {exc}"}
    return {"available": True, "reason": "FAISS available"}


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9']+", str(text or "").lower()) if len(token) > 2]


def deterministic_embedding(text: str, dim: int = VECTOR_DIM) -> list[float]:
    vector = [0.0] * dim
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        slot = int.from_bytes(digest[:4], "big") % dim
        sign = -1.0 if digest[4] % 2 else 1.0
        vector[slot] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class FaissAREIndex:
    """
    Optional semantic candidate finder for ARE records.

    The authoritative memory record stays in ARE/SQLite/JSONL. This index only
    proposes candidates; lane, scope, truth, and Sentinel checks still decide
    whether a candidate may influence generation.
    """

    def __init__(
        self,
        records: Iterable[dict[str, Any]],
        *,
        text_getter: Callable[[dict[str, Any]], str] | None = None,
        dim: int = VECTOR_DIM,
    ) -> None:
        self.records = [dict(record) for record in records]
        self.text_getter = text_getter or default_record_text
        self.dim = dim
        self._vectors = [deterministic_embedding(self.text_getter(record), dim=dim) for record in self.records]
        self._status = faiss_status()
        self._faiss_index = None
        if self._status["available"] and self._vectors:
            try:
                import faiss  # type: ignore
                import numpy as np  # type: ignore

                matrix = np.array(self._vectors, dtype="float32")
                index = faiss.IndexFlatIP(matrix.shape[1])
                index.add(matrix)
                self._faiss_index = index
            except Exception as exc:
                self._status = {"available": False, "reason": f"FAISS index build failed: {exc}"}
                self._faiss_index = None

    @property
    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def search(self, query: str, top_k: int = 8, min_score: float = 0.05) -> list[dict[str, Any]]:
        if not self.records or not str(query or "").strip():
            return []
        query_vector = deterministic_embedding(query, dim=self.dim)
        limit = max(1, min(int(top_k or 8), len(self.records)))
        if self._faiss_index is not None:
            try:
                import numpy as np  # type: ignore

                scores, indices = self._faiss_index.search(np.array([query_vector], dtype="float32"), limit)
                return self._shape_results(scores[0].tolist(), indices[0].tolist(), min_score)
            except Exception:
                pass
        scored = [(_dot(query_vector, vector), index) for index, vector in enumerate(self._vectors)]
        scored.sort(key=lambda item: item[0], reverse=True)
        return self._shape_results([score for score, _ in scored[:limit]], [index for _, index in scored[:limit]], min_score)

    def _shape_results(self, scores: list[float], indices: list[int], min_score: float) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for rank, (score, index) in enumerate(zip(scores, indices), start=1):
            if index < 0 or index >= len(self.records):
                continue
            if float(score) < min_score:
                continue
            record = dict(self.records[index])
            record["retrieval_source"] = "faiss_are_candidate" if self._faiss_index is not None else "deterministic_vector_candidate"
            record["candidate_rank"] = rank
            record["candidate_score"] = round(float(score), 6)
            record["faiss_available"] = bool(self._faiss_index is not None)
            results.append(record)
        return results


def default_record_text(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(key) or "") for key in ("summary", "raw_excerpt", "text", "source", "lane"))


def original_are_records(memory_path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = Path(memory_path)
    if not path.exists():
        return []
    all_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    first_line_number = 1
    lines = all_lines
    if limit is not None:
        keep = max(0, int(limit))
        first_line_number = max(1, len(all_lines) - keep + 1)
        lines = all_lines[-keep:]
    records: list[dict[str, Any]] = []
    for offset, line in enumerate(lines):
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        text = str(payload.get("text") or "")
        if not text:
            continue
        records.append(
            {
                "memory_id": f"original_are_{payload.get('sha') or first_line_number + offset}",
                "timestamp_ns": int(payload.get("ts") or 0) * 1_000_000_000,
                "lane": "ORIGINAL_ARE",
                "memory_scope": "PUBLIC",
                "summary": text[:500],
                "raw_excerpt": text[:2000],
                "source": "original_are",
                "provenance_hash": payload.get("sha"),
                "importance_score": 1.0,
            }
        )
    return records


def query_records(records: Iterable[dict[str, Any]], query: str, *, top_k: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index = FaissAREIndex(records)
    return index.search(query, top_k=top_k), index.status
