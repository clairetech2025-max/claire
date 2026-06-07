"""
ARE-FAISS Hybrid Memory Layer.

FAISS handles fast vector candidate retrieval. ARE logic reranks candidates with
time-aware and regime-aware orientation, then produces controlled prompt prefixes
and retrieval metrics for agent/LLM context control.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

try:
    import faiss
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "FAISS is required for ARE-FAISS Hybrid. Install with: pip install faiss-cpu"
    ) from exc


EMB_DIM = 384
DEFAULT_TIME_DECAY_LAMBDA = 0.015
DEFAULT_REGIME_BOOST = 1.15
DEFAULT_CANDIDATE_K = 500
DEFAULT_TOP_K = 8

_RNG = np.random.RandomState(42)
_PROJ = _RNG.randn(256, EMB_DIM).astype(np.float32)


def hash_embed_one(text: str) -> np.ndarray:
    """Return a deterministic normalized 384-d vector for text."""
    vec = np.zeros((256,), dtype=np.float32)
    for token in str(text or "").lower().split():
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        vec[h % 256] += 1.0

    out = vec @ _PROJ
    norm = np.linalg.norm(out) + 1e-8
    return (out / norm).astype(np.float32)


def embed_texts(texts: Iterable[str]) -> np.ndarray:
    """Embed text into a float32 matrix."""
    items = list(texts)
    if not items:
        return np.zeros((0, EMB_DIM), dtype=np.float32)
    return np.stack([hash_embed_one(text) for text in items], axis=0).astype(np.float32)


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    text: str
    regime: str | None = None
    timestamp: float | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RecallResult:
    id: str
    text: str
    similarity: float
    adjusted_score: float
    regime: str | None
    timestamp: float
    age_hours: float
    regime_match: bool
    metadata: dict[str, Any] | None = None


class AREFaissHybrid:
    """FAISS-accelerated ARE memory layer."""

    def __init__(
        self,
        dim: int = EMB_DIM,
        time_decay_lambda: float = DEFAULT_TIME_DECAY_LAMBDA,
        regime_boost: float = DEFAULT_REGIME_BOOST,
    ) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        if time_decay_lambda < 0:
            raise ValueError("time_decay_lambda must be non-negative")
        if regime_boost <= 0:
            raise ValueError("regime_boost must be positive")

        self.dim = dim
        self.time_decay_lambda = time_decay_lambda
        self.regime_boost = regime_boost
        self.records: list[MemoryRecord] = []
        self.index = faiss.IndexFlatIP(dim)

    def __len__(self) -> int:
        return len(self.records)

    def add_records(self, records: Iterable[MemoryRecord | dict[str, Any]]) -> int:
        """Add memory records to FAISS and the local metadata store."""
        normalized: list[MemoryRecord] = []
        now = time.time()

        for item in records:
            if isinstance(item, MemoryRecord):
                record = item
            else:
                record = MemoryRecord(
                    id=str(item["id"]),
                    text=str(item["text"]),
                    regime=item.get("regime"),
                    timestamp=item.get("timestamp"),
                    metadata=item.get("metadata"),
                )

            if not record.id:
                raise ValueError("record id cannot be empty")
            if not record.text.strip():
                raise ValueError("record text cannot be empty")
            if record.timestamp is None:
                record = MemoryRecord(
                    id=record.id,
                    text=record.text,
                    regime=record.regime,
                    timestamp=now,
                    metadata=record.metadata,
                )
            normalized.append(record)

        if not normalized:
            return 0

        embeddings = embed_texts([r.text for r in normalized])
        if embeddings.shape[1] != self.dim:
            raise ValueError(f"embedding dim mismatch: got {embeddings.shape[1]}, expected {self.dim}")

        self.index.add(embeddings)
        self.records.extend(normalized)
        return len(normalized)

    def search(
        self,
        query: str,
        current_regime: str | None = None,
        candidate_k: int = DEFAULT_CANDIDATE_K,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[RecallResult]:
        """Retrieve FAISS candidates and rerank with ARE time/regime weighting."""
        if not self.records or not str(query or "").strip():
            return []

        candidate_k = max(1, min(candidate_k, len(self.records)))
        top_k = max(1, min(top_k, candidate_k))
        q = embed_texts([query])
        scores, indexes = self.index.search(q, candidate_k)

        now = time.time()
        results: list[RecallResult] = []
        for base_sim, idx in zip(scores[0], indexes[0]):
            if idx < 0:
                continue

            record = self.records[int(idx)]
            ts = float(record.timestamp or now)
            age_hours = max(0.0, (now - ts) / 3600.0)
            decay = math.exp(-self.time_decay_lambda * age_hours)
            adjusted = float(base_sim) * decay

            regime_match = bool(current_regime and record.regime == current_regime)
            if regime_match:
                adjusted *= self.regime_boost

            results.append(
                RecallResult(
                    id=record.id,
                    text=record.text,
                    similarity=float(base_sim),
                    adjusted_score=float(adjusted),
                    regime=record.regime,
                    timestamp=ts,
                    age_hours=age_hours,
                    regime_match=regime_match,
                    metadata=record.metadata,
                )
            )

        results.sort(key=lambda r: r.adjusted_score, reverse=True)
        return results[:top_k]

    def metrics(self, results: list[RecallResult]) -> dict[str, float]:
        """Return entropy/concentration metrics for selected results."""
        scores = np.array([max(0.0, r.adjusted_score) for r in results], dtype=np.float64)
        if scores.size == 0 or float(np.sum(scores)) <= 0:
            return {
                "mean_score": 0.0,
                "top_score": 0.0,
                "entropy": 0.0,
                "concentration": 0.0,
                "regime_match_rate": 0.0,
            }

        probs = scores / (np.sum(scores) + 1e-8)
        return {
            "mean_score": float(np.mean(scores)),
            "top_score": float(np.max(scores)),
            "entropy": float(-np.sum(probs * np.log(probs + 1e-8))),
            "concentration": float(np.max(scores) / (np.sum(scores) + 1e-8)),
            "regime_match_rate": float(sum(1 for r in results if r.regime_match) / len(results)),
        }

    def prompt_prefix(self, results: list[RecallResult], max_chars: int = 1200) -> str:
        """Build a controlled ARE prompt prefix from selected memory."""
        if max_chars <= 0:
            return ""

        parts: list[str] = []
        total = 0
        for result in results:
            text = result.text.strip()
            if not text:
                continue
            block = (
                f"[memory id={result.id} "
                f"score={result.adjusted_score:.4f} "
                f"regime={result.regime or 'none'} "
                f"age_hours={result.age_hours:.2f}]\n"
                f"{text}"
            )
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)

        if not parts:
            return ""
        return "[ARE]\n" + "\n---\n".join(parts) + "\n[/ARE]\n"

    def recall_packet(
        self,
        query: str,
        current_regime: str | None = None,
        candidate_k: int = DEFAULT_CANDIDATE_K,
        top_k: int = DEFAULT_TOP_K,
        max_prefix_chars: int = 1200,
    ) -> dict[str, Any]:
        """Return results, metrics, and prompt prefix in one packet."""
        results = self.search(
            query=query,
            current_regime=current_regime,
            candidate_k=candidate_k,
            top_k=top_k,
        )
        return {
            "query": query,
            "current_regime": current_regime,
            "candidate_k": candidate_k,
            "top_k": top_k,
            "count": len(results),
            "metrics": self.metrics(results),
            "results": [asdict(r) for r in results],
            "prompt_prefix": self.prompt_prefix(results, max_chars=max_prefix_chars),
        }

    def save_records_jsonl(self, path: str | Path) -> Path:
        """Save records only. FAISS index is rebuilt on load."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            for record in self.records:
                f.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")
        return target

    @classmethod
    def load_records_jsonl(
        cls,
        path: str | Path,
        dim: int = EMB_DIM,
        time_decay_lambda: float = DEFAULT_TIME_DECAY_LAMBDA,
        regime_boost: float = DEFAULT_REGIME_BOOST,
    ) -> "AREFaissHybrid":
        """Load records from JSONL and rebuild the FAISS index."""
        engine = cls(dim=dim, time_decay_lambda=time_decay_lambda, regime_boost=regime_boost)
        source = Path(path)
        if not source.exists():
            return engine

        records: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except Exception as exc:
                    raise ValueError(f"Invalid JSONL line {line_num}: {exc}") from exc

        engine.add_records(records)
        return engine


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    idx = int((len(ordered) - 1) * p)
    return ordered[idx]


def _latency_stats_ms(samples_seconds: list[float]) -> dict[str, float]:
    ms = [s * 1000 for s in samples_seconds]
    return {
        "p50": _percentile(ms, 0.50),
        "p95": _percentile(ms, 0.95),
        "p99": _percentile(ms, 0.99),
        "min": min(ms),
        "mean": statistics.mean(ms),
        "max": max(ms),
        "requests_per_sec_from_mean": 1000.0 / statistics.mean(ms),
    }


def build_synthetic_records(n: int) -> list[MemoryRecord]:
    """Build synthetic records for smoke tests and benchmarks."""
    topics = [
        "truth spine deterministic recall capsule hmac sha384",
        "analog recall engine semantic prefetch vector memory",
        "session capsule continuity restore anti drift",
        "faiss vector search nearest neighbor index",
        "claire conversation routing build reply direct answer",
        "github public proof benchmark documentation",
        "regime boost time decay entropy concentration",
        "azure vm uvicorn fastapi service endpoint",
    ]
    regimes = ["legal", "architecture", "benchmark", "conversation", "github"]
    now = time.time()
    records: list[MemoryRecord] = []

    for i in range(n):
        regime = regimes[i % len(regimes)]
        records.append(
            MemoryRecord(
                id=f"rec-{i}",
                text=f"record {i}: {topics[i % len(topics)]}. regime {regime}. synthetic memory item {i}.",
                regime=regime,
                timestamp=now - ((i % 5000) * 60),
                metadata={"synthetic": True, "i": i},
            )
        )
    return records


def smoke_test() -> None:
    engine = AREFaissHybrid()
    engine.add_records(build_synthetic_records(10_000))
    packet = engine.recall_packet(
        query="truth spine hmac deterministic capsule",
        current_regime="architecture",
        candidate_k=500,
        top_k=8,
    )
    print(
        json.dumps(
            {
                "count": packet["count"],
                "metrics": packet["metrics"],
                "first_result": packet["results"][0] if packet["results"] else None,
                "prefix_preview": packet["prompt_prefix"][:500],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    smoke_test()
