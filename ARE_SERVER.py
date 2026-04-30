import hashlib
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, Request
from pydantic import BaseModel

app = FastAPI(title="Claire ARE Brain - Sovereign Core")

VAULT_PATH = "/home/LuciusPrime/claire/data/memory_vault.jsonl"
os.makedirs(os.path.dirname(VAULT_PATH), exist_ok=True)

_RECORDS = []
_TOKEN_INDEX = defaultdict(set)
_EXACT_INDEX = defaultdict(set)


class QueryRequest(BaseModel):
    query: str


def _tokens(value: str):
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "about",
        "be",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "how",
        "morning",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "please",
        "should",
        "tell",
        "that",
        "the",
        "to",
        "what",
        "when",
        "where",
        "who",
        "why",
        "will",
        "would",
        "with",
        "you",
        "claire",
        "answer",
        "naturally",
        "need",
        "bit",
        "much",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]+", str(value or "").lower())
        if token not in stopwords and len(token) > 2
    }


def _flatten_record(value):
    if isinstance(value, dict):
        return " ".join(_flatten_record(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_record(v) for v in value)
    return str(value or "")


def _fingerprint(payload):
    clean = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def _prepare_record(payload):
    record = dict(payload)
    flat = _flatten_record(record).strip()
    record["_flat"] = flat
    record["_flat_lower"] = flat.lower()
    record["_tokens"] = sorted(_tokens(flat))
    record["_verify_hash"] = _fingerprint(record)
    return record


def _index_record(payload):
    prepared = _prepare_record(payload)
    idx = len(_RECORDS)
    _RECORDS.append(prepared)
    if prepared["_flat_lower"]:
        _EXACT_INDEX[prepared["_flat_lower"]].add(idx)
    for token in prepared["_tokens"]:
        _TOKEN_INDEX[token].add(idx)
    return prepared


def load_vault():
    _RECORDS.clear()
    _TOKEN_INDEX.clear()
    _EXACT_INDEX.clear()
    if not os.path.exists(VAULT_PATH):
        return 0
    loaded = 0
    with open(VAULT_PATH, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            _index_record(payload)
            loaded += 1
    return loaded


def append_to_vault(data: dict):
    payload = dict(data)
    payload["anchored_at"] = datetime.utcnow().isoformat()
    with open(VAULT_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    _index_record(payload)


def _candidate_indexes(query_lower, query_tokens):
    candidates = set(_EXACT_INDEX.get(query_lower, set()))
    for token in query_tokens:
        candidates.update(_TOKEN_INDEX.get(token, set()))
    return candidates


def _score_record(query_lower, query_tokens, record):
    score = 0.0
    flat_lower = record.get("_flat_lower", "")
    if len(query_lower) >= 8 and query_lower and query_lower in flat_lower:
        score += 100.0
    record_tokens = set(record.get("_tokens", []))
    if query_tokens and record_tokens:
        matches = len(query_tokens & record_tokens)
        if matches:
            score += matches * 10.0
            score += matches / max(len(query_tokens), 1)
    return score


def are_recall(query: str, top_k: int = 5):
    query = str(query or "").strip()
    query_lower = query.lower()
    if query_lower in {"hi", "hello", "hey", "yo", "sup", "thanks", "thank you"}:
        return []
    query_tokens = _tokens(query)
    if len(query_tokens) < 2 and len(query_lower) < 8:
        return []
    candidates = _candidate_indexes(query_lower, query_tokens)
    if not candidates:
        return []
    ranked = []
    for idx in candidates:
        record = _RECORDS[idx]
        score = _score_record(query_lower, query_tokens, record)
        if score >= 20.0:
            ranked.append((score, record))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            k: v
            for k, v in record.items()
            if not k.startswith("_")
        }
        | {
            "_score": round(score, 3),
            "_verify_hash": record.get("_verify_hash"),
        }
        for score, record in ranked[:top_k]
    ]


def verify(record: dict):
    payload = {k: v for k, v in record.items() if k not in {"_score", "verified", "verify_hash", "_verify_hash"}}
    expected = _fingerprint(payload)
    return {
        **payload,
        "_score": record.get("_score", 0.0),
        "verify_hash": expected,
        "verified": expected == record.get("_verify_hash"),
    }


def is_confident_match(verified):
    if not verified:
        return False
    top = float(verified[0].get("_score", 0.0))
    runner_up = float(verified[1].get("_score", 0.0)) if len(verified) > 1 else 0.0
    return top >= 30.0 and (top - runner_up) >= 5.0


def _guard_forbidden(endpoint_name: str):
    print(f"{endpoint_name}: GO not called")
    print(f"{endpoint_name}: Sentinel not called")
    print(f"{endpoint_name}: full pipeline not called")


@app.on_event("startup")
async def startup_event():
    loaded = load_vault()
    print(f"ARE startup indexed {loaded} vault records")


@app.post("/ingest")
async def ingest(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        background_tasks.add_task(append_to_vault, data)
        return {"status": "SUCCESS", "message": "Memory Anchored"}
    except Exception as exc:
        return {"status": "ERROR", "message": str(exc)}


@app.get("/are/raw")
async def are_raw(query: str, top_k: int = 5):
    print("ARE RAW PATH HIT")
    _guard_forbidden("ARE RAW")
    started = time.perf_counter()
    results = are_recall(query, top_k=top_k)
    verified = [verify(result) for result in results]
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "ms": round(elapsed_ms, 3),
        "count": len(verified),
        "confident_match": is_confident_match(verified),
        "generation_called": False,
        "sentinel_called": False,
        "full_pipeline_called": False,
        "results": verified,
    }


@app.post("/query")
async def query_memory(req: QueryRequest):
    print("ARE QUERY PATH HIT")
    _guard_forbidden("ARE QUERY")
    started = time.perf_counter()
    results = are_recall(req.query, top_k=5)
    verified = [verify(result) for result in results]
    confident = is_confident_match(verified)
    if confident:
        print("ARE FAST PATH USED")
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "results": verified,
        "count": len(verified),
        "ms": round(elapsed_ms, 3),
        "fast_path_used": confident,
        "generation_called": False,
        "sentinel_called": False,
        "full_pipeline_called": False,
    }


@app.get("/health")
async def health():
    return {
        "status": "online",
        "mode": "ARE_FAST_INDEXED",
        "vault_records": len(_RECORDS),
        "vault_path": VAULT_PATH,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
