from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from diode_protocol import DiodeProtocol


VECTOR_DIM = 384


@dataclass
class MemoryIndexRecord:
    memory_id: str
    text: str
    sha: str = ""
    timestamp_ns: int = 0
    lane: str = "GENERAL_CHAT"
    memory_scope: str = "PUBLIC"
    source_path: str = ""
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def safe_text(self) -> str:
        return DiodeProtocol.redact(str(self.text or ""))[:2000]

    def map_row(self, row: int) -> dict[str, Any]:
        return {
            "row": row,
            "memory_id": self.memory_id,
            "sha": self.sha,
            "timestamp_ns": self.timestamp_ns,
            "lane": self.lane,
            "memory_scope": self.memory_scope,
            "source_path": self.source_path,
            "source": self.source,
            "diode_redacted": DiodeProtocol.contains_secret(str(self.text or "")),
        }


def faiss_dependency_status() -> dict[str, Any]:
    try:
        import faiss  # type: ignore  # noqa: F401
        import numpy  # type: ignore  # noqa: F401
    except Exception as exc:
        return {"available": False, "reason": f"FAISS unavailable: {exc}"}
    return {"available": True, "reason": "FAISS available"}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_'-]+", str(text or "").lower())
        if len(token) > 2
    ]


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


def record_from_memory(memory: dict[str, Any]) -> MemoryIndexRecord:
    text = " ".join(
        str(memory.get(key) or "")
        for key in ("summary", "raw_excerpt", "text")
        if memory.get(key)
    ).strip()
    memory_id = str(
        memory.get("memory_id")
        or memory.get("sha")
        or hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    )
    return MemoryIndexRecord(
        memory_id=memory_id,
        text=text,
        sha=str(memory.get("sha") or memory.get("provenance_hash") or ""),
        timestamp_ns=int(memory.get("timestamp_ns") or 0),
        lane=str(memory.get("lane") or "GENERAL_CHAT"),
        memory_scope=str(memory.get("memory_scope") or "PUBLIC"),
        source_path=str(memory.get("source_path") or memory.get("memory_file") or ""),
        source=str(memory.get("source") or "unknown"),
        metadata={k: v for k, v in memory.items() if k not in {"summary", "raw_excerpt", "text"}},
    )


class FaissMemoryIndex:
    """
    Optional relevance index for ARE memory records.

    This class never becomes the source of truth. It stores row mappings back to
    memory IDs / hashes / timestamps, and search returns memory references plus
    redacted previews. Durable memory remains in original ARE JSONL and/or the
    governed SQLite metadata store.
    """

    def __init__(
        self,
        *,
        index_path: str | Path = "claire_state/faiss_memory.index",
        map_path: str | Path = "claire_state/faiss_memory_map.jsonl",
        dim: int = VECTOR_DIM,
    ) -> None:
        self.index_path = Path(index_path)
        self.map_path = Path(map_path)
        self.dim = dim
        self.records: list[MemoryIndexRecord] = []
        self.vectors: list[list[float]] = []
        self.status = faiss_dependency_status()
        self._faiss_index = None

    @property
    def faiss_available(self) -> bool:
        return bool(self.status.get("available") and self._faiss_index is not None)

    def build(self, memories: Iterable[dict[str, Any] | MemoryIndexRecord], *, persist: bool = False) -> dict[str, Any]:
        self.records = []
        self.vectors = []
        for item in memories:
            record = item if isinstance(item, MemoryIndexRecord) else record_from_memory(item)
            safe_text = record.safe_text().strip()
            if not safe_text:
                continue
            self.records.append(record)
            self.vectors.append(deterministic_embedding(safe_text, dim=self.dim))

        self._build_optional_faiss()
        if persist:
            self.persist()
        return {
            "records_indexed": len(self.records),
            "faiss_available": self.faiss_available,
            "status": dict(self.status),
            "index_path": str(self.index_path),
            "map_path": str(self.map_path),
        }

    def _build_optional_faiss(self) -> None:
        self._faiss_index = None
        if not self.status.get("available") or not self.vectors:
            return
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore

            matrix = np.array(self.vectors, dtype="float32")
            index = faiss.IndexFlatIP(matrix.shape[1])
            index.add(matrix)
            self._faiss_index = index
        except Exception as exc:
            self.status = {"available": False, "reason": f"FAISS index build failed: {exc}"}
            self._faiss_index = None

    def persist(self) -> None:
        self.map_path.parent.mkdir(parents=True, exist_ok=True)
        with self.map_path.open("w", encoding="utf-8") as handle:
            for row, record in enumerate(self.records):
                handle.write(json.dumps(record.map_row(row), ensure_ascii=False) + "\n")

        if self._faiss_index is not None:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import faiss  # type: ignore

                faiss.write_index(self._faiss_index, str(self.index_path))
            except Exception as exc:
                self.status = {"available": False, "reason": f"FAISS index persist failed: {exc}"}

    def search(self, query: str, *, top_k: int = 5, min_score: float = 0.01) -> list[dict[str, Any]]:
        if not self.records or not str(query or "").strip():
            return []
        limit = max(1, min(int(top_k or 5), len(self.records)))
        query_vector = deterministic_embedding(DiodeProtocol.redact(query), dim=self.dim)
        if self._faiss_index is not None:
            try:
                import numpy as np  # type: ignore

                scores, indices = self._faiss_index.search(np.array([query_vector], dtype="float32"), limit)
                return self._shape_results(scores[0].tolist(), indices[0].tolist(), min_score)
            except Exception:
                pass

        scored = [(_dot(query_vector, vector), idx) for idx, vector in enumerate(self.vectors)]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return self._shape_results(
            [score for score, _idx in scored[:limit]],
            [idx for _score, idx in scored[:limit]],
            min_score,
        )

    def _shape_results(self, scores: list[float], indices: list[int], min_score: float) -> list[dict[str, Any]]:
        shaped: list[dict[str, Any]] = []
        for rank, (score, index) in enumerate(zip(scores, indices), start=1):
            if index < 0 or index >= len(self.records):
                continue
            numeric_score = float(score)
            if numeric_score < min_score:
                continue
            record = self.records[index]
            shaped.append(
                {
                    "rank": rank,
                    "score": round(numeric_score, 6),
                    "memory_id": record.memory_id,
                    "sha": record.sha,
                    "timestamp_ns": record.timestamp_ns,
                    "lane": record.lane,
                    "memory_scope": record.memory_scope,
                    "source": record.source,
                    "source_path": record.source_path,
                    "retrieval_source": "faiss_memory_index" if self.faiss_available else "deterministic_memory_index",
                    "faiss_available": self.faiss_available,
                    "memory_lead": record.safe_text()[:500],
                }
            )
        return shaped

