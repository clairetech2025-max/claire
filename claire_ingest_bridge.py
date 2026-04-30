import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

BASE_DIR = Path("/home/LuciusPrime/claire")
SENTINEL_SPINE = BASE_DIR / "silo_data" / "sentinel_spine.jsonl"
ARE_INGEST_URL = os.getenv("CLAIRE_ARE_INGEST_URL", "http://127.0.0.1:8002/ingest")
INGEST_TOKEN = os.getenv("CLAIRE_INGEST_TOKEN", "")

app = FastAPI(title="Claire Parser/Sentinel Ingest Bridge")


class IngestPayload(BaseModel):
    text: Optional[str] = None
    payload: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    source_path: Optional[str] = None
    domain: Optional[str] = None
    doc_type: Optional[str] = None
    chunk_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


def _authorize(authorization: Optional[str], host: str) -> None:
    if host.startswith("127.") or host == "localhost":
        return
    if not INGEST_TOKEN:
        raise HTTPException(status_code=403, detail="External ingest disabled")
    expected = f"Bearer {INGEST_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=403, detail="Invalid ingest token")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _pick_text(data: Dict[str, Any]) -> str:
    for key in ("text", "payload", "content", "body", "query"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _source(data: Dict[str, Any]) -> str:
    return str(
        data.get("source")
        or data.get("source_path")
        or data.get("title")
        or data.get("chunk_id")
        or "8081_ingest"
    )


def _sentinel_record(data: Dict[str, Any], text: str) -> Dict[str, Any]:
    source = _source(data)
    return {
        "hg_id": _sha(text)[:16],
        "source": source,
        "ts": time.time(),
        "payload": text,
        "domain": data.get("domain") or data.get("doc_type") or "general",
        "chunk_id": data.get("chunk_id") or data.get("id"),
        "metadata": data.get("metadata") or {},
        "v_sig": "SENTINEL_INGEST_BRIDGE_V1",
    }


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _forward_to_are(record: Dict[str, Any]) -> Dict[str, Any]:
    are_payload = {
        "id": record.get("chunk_id") or record["hg_id"],
        "text": record["payload"],
        "source": record["source"],
        "domain": record["domain"],
        "hg_id": record["hg_id"],
        "v_sig": record["v_sig"],
        "sentinel_ts": record["ts"],
        "metadata": record.get("metadata", {}),
    }
    response = requests.post(ARE_INGEST_URL, json=are_payload, timeout=10)
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    return {"status_code": response.status_code, "body": body}


async def _ingest_request(request: Request, authorization: Optional[str]) -> Dict[str, Any]:
    client_host = request.client.host if request.client else ""
    _authorize(authorization, client_host)

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    text = _pick_text(data)
    if not text:
        raise HTTPException(status_code=400, detail="Missing text/payload/content")

    record = _sentinel_record(data, text)
    _append_jsonl(SENTINEL_SPINE, record)
    are_result = _forward_to_are(record)

    return {
        "ok": True,
        "lane": "parser_to_sentinel_to_are",
        "hg_id": record["hg_id"],
        "source": record["source"],
        "are": are_result,
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "claire-ingest",
        "port": 8081,
        "lane": "parser_to_sentinel_to_are",
        "are_ingest_url": ARE_INGEST_URL,
        "external_ingest": bool(INGEST_TOKEN),
    }


@app.post("/ingest")
async def ingest(request: Request, authorization: Optional[str] = Header(None)):
    return await _ingest_request(request, authorization)


@app.post("/parser/push")
async def parser_push(request: Request, authorization: Optional[str] = Header(None)):
    return await _ingest_request(request, authorization)


@app.post("/sentinel/push")
async def sentinel_push(request: Request, authorization: Optional[str] = Header(None)):
    return await _ingest_request(request, authorization)
