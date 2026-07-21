#!/usr/bin/env python3
"""Optional FAISS analog recall helper.

The existing ARE/analog path remains the fallback. This module only uses FAISS
when the package is already available in the environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .veritas_paper_runtime import Candle, returns


@dataclass
class FaissStatus:
    available: bool
    reason: str


def faiss_status() -> FaissStatus:
    try:
        import faiss  # type: ignore  # noqa: F401
        import numpy  # type: ignore  # noqa: F401
    except Exception as exc:
        return FaissStatus(False, f"FAISS unavailable: {exc}")
    return FaissStatus(True, "FAISS available")


def query_faiss_analogs(candles: list[Candle], window: int = 8, top_k: int = 5) -> dict[str, Any]:
    status = faiss_status()
    if not status.available:
        return {"available": False, "reason": status.reason, "analogs": []}
    if len(candles) < window * 3:
        return {"available": True, "reason": "not enough candles", "analogs": []}

    import faiss  # type: ignore
    import numpy as np  # type: ignore

    vectors = []
    meta = []
    for idx in range(0, len(candles) - window - 1):
        segment = candles[idx : idx + window]
        vec = returns(segment)
        if len(vec) != window - 1:
            continue
        next_return = (candles[idx + window].close - segment[-1].close) / segment[-1].close if segment[-1].close else 0.0
        vectors.append(vec)
        meta.append(
            {
                "pair": segment[-1].pair,
                "start_ts": segment[0].timestamp,
                "end_ts": segment[-1].timestamp,
                "next_return": round(next_return, 8),
            }
        )
    query_vec = returns(candles[-window:])
    if not vectors or len(query_vec) != window - 1:
        return {"available": True, "reason": "no vectors", "analogs": []}
    matrix = np.array(vectors, dtype="float32")
    index = faiss.IndexFlatL2(matrix.shape[1])
    index.add(matrix)
    distances, indices = index.search(np.array([query_vec], dtype="float32"), min(top_k, len(vectors)))
    analogs = []
    for rank, (distance, idx) in enumerate(zip(distances[0], indices[0]), start=1):
        if idx < 0:
            continue
        analogs.append({"rank": rank, "distance": float(distance), **meta[int(idx)]})
    return {"available": True, "reason": "ok", "analogs": analogs}
