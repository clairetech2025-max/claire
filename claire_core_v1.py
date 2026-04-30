from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CLAIRE_CORE")

_EMB_DIM = 384

try:
    import torch
    from sentence_transformers import SentenceTransformer

    _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    _EMB_MODEL = SentenceTransformer("all-MiniLM-L6-v2", device=_DEVICE)
    logger.info("Embeddings loaded on device: %s", _DEVICE)

    def embed_text(texts: list[str]) -> np.ndarray:
        return _EMB_MODEL.encode(texts, normalize_embeddings=True, convert_to_numpy=True)

except Exception as exc:
    logger.warning("SentenceTransformer unavailable; using deterministic fallback embeddings: %s", exc)

    def embed_text(texts: list[str]) -> np.ndarray:
        vectors: list[np.ndarray] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
            seed = int.from_bytes(digest[:8], "big", signed=False)
            rng = np.random.default_rng(seed)
            vector = rng.normal(size=_EMB_DIM).astype(np.float32)
            norm = np.linalg.norm(vector) or 1.0
            vectors.append(vector / norm)
        return np.vstack(vectors).astype(np.float32)


def utc_ms() -> int:
    return int(time.time() * 1000)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def chunk_words(text: str, chunk_size: int = 160) -> list[str]:
    words = str(text or "").split()
    if not words:
        return []
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]


class Trace:
    def __init__(self, request_id: str | None = None):
        self.trace_id = request_id or f"trace_{utc_ms()}_{uuid.uuid4().hex[:8]}"
        self.created_ms = utc_ms()
        self.events: list[dict[str, Any]] = []

    def add(self, stage: str, payload: dict[str, Any]) -> None:
        self.events.append({"ts_ms": utc_ms(), "stage": stage, "payload": payload})

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "created_ms": self.created_ms, "events": self.events}


class DiodeLedger:
    """Append-only provenance ledger. Model output may be recorded, but never overwrites source memory."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.ledger_path = base_dir / "ledger" / "diode_ledger.jsonl"
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self.ledger_path.exists():
            return "0" * 64
        last = "0" * 64
        try:
            with self.ledger_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if line.strip():
                        obj = json.loads(line)
                        last = obj.get("chain_hash", last)
        except Exception:
            logger.exception("Failed to load ledger tail; using zero hash")
        return last

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            core = {
                "ts_ms": utc_ms(),
                "event_type": event_type,
                "payload": payload,
                "prev_hash": self._last_hash,
            }
            core_bytes = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
            core_hash = hashlib.sha256(core_bytes).hexdigest()
            chain_hash = hashlib.sha256(f"{self._last_hash}:{core_hash}".encode("utf-8")).hexdigest()
            record = {**core, "core_hash": core_hash, "chain_hash": chain_hash}
            with self.ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            self._last_hash = chain_hash
            return record


class MemoryStore:
    def __init__(self):
        self.ids: list[str] = []
        self.texts: list[str] = []
        self.hashes: list[str] = []
        self.sources: list[str] = []
        self.embs = np.zeros((0, _EMB_DIM), dtype=np.float32)
        self._lock = threading.Lock()

    def add(self, texts: list[str], source: str = "manual") -> int:
        clean = [text.strip() for text in texts if text and text.strip()]
        if not clean:
            return 0
        embs = embed_text(clean).astype(np.float32)
        with self._lock:
            start = len(self.ids)
            self.ids.extend([f"mem-{start + i:08d}" for i in range(len(clean))])
            self.texts.extend(clean)
            self.hashes.extend([sha256_text(text) for text in clean])
            self.sources.extend([source] * len(clean))
            self.embs = np.vstack([self.embs, embs])
        return len(clean)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        with self._lock:
            if not self.ids:
                return []
            q = embed_text([query])[0].astype(np.float32)
            sims = np.dot(self.embs, q)
            indexes = np.argsort(-sims)[:top_k]
            return [
                {
                    "id": self.ids[i],
                    "text": self.texts[i],
                    "hash": self.hashes[i],
                    "source": self.sources[i],
                    "score": float(sims[i]),
                }
                for i in indexes
            ]

    def count(self) -> int:
        with self._lock:
            return len(self.ids)


class Sentinel:
    def __init__(self, min_score: float = 0.20):
        self.min_score = min_score
        self.blocked_terms = {
            "ignore previous instructions",
            "override system",
            "delete ledger",
            "erase memory",
        }

    def filter_recall(self, results: list[dict[str, Any]], trace: Trace) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for result in results:
            text_l = result["text"].lower()
            reason = ""
            if result["score"] < self.min_score:
                reason = "low_score"
            elif len(result["text"]) < 20:
                reason = "too_short"
            elif any(term in text_l for term in self.blocked_terms):
                reason = "blocked_term"

            if reason:
                blocked.append({"id": result["id"], "reason": reason, "score": result["score"]})
            else:
                kept.append(result)
        trace.add("sentinel_filter", {"kept": len(kept), "blocked": blocked})
        return kept


class Gyro:
    """Gyro-lite response-lane orientation before generation."""

    def orient(self, query: str, recall: list[dict[str, Any]], trace: Trace) -> dict[str, Any]:
        q = query.lower()
        risk_terms = ["legal", "court", "threat", "harm", "delete", "bypass", "weapon"]
        technical_terms = ["code", "api", "runtime", "memory", "latency", "fastapi", "azure", "vm"]
        risk = sum(1 for term in risk_terms if term in q)
        technical = sum(1 for term in technical_terms if term in q)
        recall_strength = max([item["score"] for item in recall], default=0.0)

        if risk >= 2:
            lane = "careful_governed_response"
        elif technical >= 1:
            lane = "technical_runtime_response"
        elif recall_strength > 0.45:
            lane = "memory_grounded_response"
        else:
            lane = "general_response"

        orientation = {
            "lane": lane,
            "risk_score": risk,
            "technical_score": technical,
            "recall_strength": round(recall_strength, 4),
            "allowed_paths": ["answer", "trace", "memory_prefix"],
            "blocked_paths": ["memory_mutation_by_model", "unverified_action"],
        }
        trace.add("gyro_orientation", orientation)
        return orientation


class ClaireCore:
    def __init__(self, base_dir: Path | None = None):
        default_home = Path(os.environ.get("CLAIRE_CORE_HOME", "/home/LuciusPrime/claire/data/claire_core_v1"))
        self.base_dir = base_dir or default_home
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.memory = MemoryStore()
        self.diode = DiodeLedger(self.base_dir)
        self.sentinel = Sentinel()
        self.gyro = Gyro()
        self.context = ""
        self._lock = threading.Lock()

    def ingest_text(self, text: str, source: str = "live") -> dict[str, Any]:
        with self._lock:
            self.context = (self.context + " " + text.strip())[-4000:]

        chunks = chunk_words(text, chunk_size=160)
        added = self.memory.add(chunks, source=source)
        ledger = self.diode.append("INGEST", {"source": source, "chunks_added": added, "text_hash": sha256_text(text)})
        return {"ok": True, "chunks_added": added, "ledger_hash": ledger["chain_hash"]}

    def load_path(self, path: str, chunk: int = 160) -> dict[str, Any]:
        patterns = ["*.txt", "*.md", "*.json", "*.jsonl"]
        paths: list[str] = []
        for pattern in patterns:
            paths.extend(glob.glob(os.path.join(path, "**", pattern), recursive=True))

        total = 0
        loaded_files = 0
        for item in sorted(set(paths)):
            try:
                with open(item, "r", encoding="utf-8", errors="ignore") as handle:
                    content = handle.read()
                total += self.memory.add(chunk_words(content, chunk_size=chunk), source=item)
                loaded_files += 1
            except Exception as exc:
                logger.error("Error loading %s: %s", item, exc)

        ledger = self.diode.append("LOAD_PATH", {"path": path, "files": loaded_files, "chunks_added": total})
        return {"ok": True, "files": loaded_files, "chunks_added": total, "ledger_hash": ledger["chain_hash"]}

    def process(self, query: str, top_k: int = 8) -> dict[str, Any]:
        trace = Trace()
        started = time.perf_counter()
        with self._lock:
            self.context = (self.context + " " + query.strip())[-4000:]
            current_context = self.context

        trace.add("input", {"query": query, "context_chars": len(current_context)})
        raw = self.memory.search(current_context, top_k=top_k)
        trace.add(
            "are_recall",
            {
                "raw_count": len(raw),
                "top": [
                    {"id": r["id"], "score": round(r["score"], 4), "hash": r["hash"], "source": r["source"]}
                    for r in raw[:5]
                ],
            },
        )
        filtered = self.sentinel.filter_recall(raw, trace)
        orientation = self.gyro.orient(query, filtered, trace)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        ledger = self.diode.append(
            "PROCESS",
            {
                "query_hash": sha256_text(query),
                "recall_count": len(filtered),
                "lane": orientation["lane"],
                "elapsed_ms": elapsed_ms,
            },
        )
        trace.add("diode_commit", {"chain_hash": ledger["chain_hash"]})
        trace.add("runtime_timing", {"elapsed_ms": elapsed_ms})
        return {
            "ok": True,
            "lane": orientation["lane"],
            "prefix": self._format_prefix(filtered),
            "recall": filtered,
            "elapsed_ms": elapsed_ms,
            "ledger_hash": ledger["chain_hash"],
            "trace": trace.to_dict(),
        }

    def _format_prefix(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return ""
        blocks = [
            f"SOURCE={item['source']}\nHASH={item['hash']}\nSCORE={item['score']:.4f}\n{item['text']}"
            for item in results[:5]
        ]
        return "[ARE]\n" + "\n---\n".join(blocks) + "\n[/ARE]"

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "name": "CLAIRE_CORE_v1",
            "memory_chunks": self.memory.count(),
            "ledger": str(self.diode.ledger_path),
            "base_dir": str(self.base_dir),
        }


app = FastAPI(title="Claire Core v1", version="1.0")
CORE = ClaireCore()


class IngestReq(BaseModel):
    text: str
    source: str = "live"


class LoadReq(BaseModel):
    path: str
    chunk: int = 160


class QueryReq(BaseModel):
    query: str
    top_k: int = 8


@app.get("/health")
def health() -> dict[str, Any]:
    return CORE.status()


@app.get("/status")
def status() -> dict[str, Any]:
    return CORE.status()


@app.post("/load")
def load(req: LoadReq) -> dict[str, Any]:
    return CORE.load_path(req.path, chunk=req.chunk)


@app.post("/ingest")
def ingest(req: IngestReq) -> dict[str, Any]:
    return CORE.ingest_text(req.text, source=req.source)


@app.post("/process")
def process(req: QueryReq) -> dict[str, Any]:
    return CORE.process(req.query, top_k=req.top_k)


@app.get("/prefix")
def prefix(q: str = "", top_k: int = 8) -> dict[str, Any]:
    result = CORE.process(q or CORE.context or "status", top_k=top_k)
    return {
        "prefix": result["prefix"],
        "lane": result["lane"],
        "elapsed_ms": result["elapsed_ms"],
        "trace": result["trace"],
    }


@app.websocket("/ws/ingest")
async def ws_ingest(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            result = CORE.ingest_text(msg, source="websocket")
            await ws.send_text(json.dumps(result))
    except WebSocketDisconnect:
        return


@app.websocket("/ws/process")
async def ws_process(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            result = CORE.process(msg)
            await ws.send_text(json.dumps(result))
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("CLAIRE_CORE_PORT", "8001")))
