"""Session-scoped Analog Recall Engine demo store.

This module is intentionally small and public-safe. It demonstrates the Original
ARE memory-lane idea without production CLAIRE internals, private memory,
Sentinel, Diode, Veritas, vector search, or external persistence.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


MAX_MEMORY_CHARS = 500
SECRET_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in [
        r"api[_-]?key",
        r"secret",
        r"password",
        r"passphrase",
        r"token",
        r"private[_-]?key",
        r"access[_-]?token",
        r"refresh[_-]?token",
        r"bearer\s+[a-z0-9._-]+",
        r"sk-[a-z0-9_-]{12,}",
    ]
]


@dataclass
class AREDemoStore:
    """Append-first, lane-scoped memory state for one Gradio session."""

    lane_code: str | None = None
    created_at: str | None = None
    memories: list[dict[str, Any]] = field(default_factory=list)
    ledger: list[dict[str, Any]] = field(default_factory=list)


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean_text(text: str) -> str:
    return " ".join(str(text or "").split())[:MAX_MEMORY_CHARS]


def contains_secret_risk(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def checksum(text: str, length: int = 12) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:length]


def lane_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = uuid.uuid4().hex.upper()
    chars = [alphabet[int(raw[idx * 2 : idx * 2 + 2], 16) % len(alphabet)] for idx in range(6)]
    return "ARE-LANE-" + "".join(chars)


def preview(text: str, limit: int = 120) -> str:
    cleaned = clean_text(text)
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def new_store() -> AREDemoStore:
    return AREDemoStore()


def create_lane(store: AREDemoStore | None) -> tuple[AREDemoStore, str]:
    store = store or new_store()
    store.lane_code = lane_code()
    store.created_at = utc_ts()
    store.memories = []
    store.ledger = []
    append_ledger(store, "lane_created")
    return store, store.lane_code


def require_lane(store: AREDemoStore | None) -> None:
    if not store or not store.lane_code:
        raise ValueError("Create a Memory Lane first.")


def append_ledger(
    store: AREDemoStore,
    event_type: str,
    checksum_value: str | None = None,
    memory_preview: str | None = None,
    recall_query: str | None = None,
    recall_result: str | None = None,
) -> dict[str, Any]:
    row = {
        "timestamp": utc_ts(),
        "event_type": event_type,
        "lane_code": store.lane_code or "",
        "checksum": checksum_value or "",
        "memory_preview": memory_preview or "",
        "recall_query": recall_query or "",
        "recall_result": recall_result or "",
        "expiration": "session end",
    }
    store.ledger.append(row)
    return row


def save_memory(store: AREDemoStore | None, memory_text: str) -> tuple[AREDemoStore, dict[str, Any]]:
    require_lane(store)
    assert store is not None
    cleaned = clean_text(memory_text)
    if not cleaned:
        raise ValueError("Type a safe demo memory first.")
    if contains_secret_risk(cleaned):
        raise ValueError("This looks like it may contain a secret. Demo memories cannot store secrets, passwords, tokens, or private keys.")
    record = {
        "created_at": utc_ts(),
        "checksum": checksum(cleaned),
        "memory_text": cleaned,
        "memory_preview": preview(cleaned),
    }
    store.memories.append(record)
    append_ledger(store, "memory_saved", checksum_value=record["checksum"], memory_preview=record["memory_preview"])
    return store, record


def score_memory(query: str, memory: str) -> tuple[int, bool]:
    q = clean_text(query).lower()
    m = clean_text(memory).lower()
    if not q or not m:
        return 0, False
    if q in m or m in q:
        return max(len(q), len(m)), True
    query_terms = {term for term in re.findall(r"[a-z0-9]+", q) if len(term) >= 3}
    memory_terms = {term for term in re.findall(r"[a-z0-9]+", m) if len(term) >= 3}
    overlap = query_terms & memory_terms
    return len(overlap), bool(overlap)


def recall_memory(store: AREDemoStore | None, query: str) -> tuple[AREDemoStore, dict[str, Any]]:
    require_lane(store)
    assert store is not None
    cleaned = clean_text(query)
    if not cleaned:
        raise ValueError("Ask a recall question first.")
    if contains_secret_risk(cleaned):
        raise ValueError("Recall questions cannot include secrets, passwords, tokens, or private keys.")
    append_ledger(store, "recall_requested", recall_query=cleaned)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, memory in enumerate(store.memories):
        score, matched = score_memory(cleaned, memory["memory_text"])
        if matched:
            scored.append((score, index, memory))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if scored:
        best = scored[0][2]
        result = f'You previously saved: "{best["memory_text"]}"'
        response = {"found": True, "recall_result": result, "matched_memory": best}
        append_ledger(
            store,
            "memory_recalled",
            checksum_value=best["checksum"],
            memory_preview=best["memory_preview"],
            recall_query=cleaned,
            recall_result=result,
        )
    else:
        result = "No matching prior memory was found in this lane."
        response = {"found": False, "recall_result": result, "matched_memory": None}
        append_ledger(store, "memory_recalled", recall_query=cleaned, recall_result=result)
    return store, response


def memory_rows(store: AREDemoStore | None) -> list[list[str]]:
    if not store:
        return []
    return [[row["created_at"], row["checksum"], row["memory_preview"]] for row in store.memories]


def ledger_rows(store: AREDemoStore | None) -> list[list[str]]:
    if not store:
        return []
    return [
        [
            row["timestamp"],
            row["event_type"],
            row["lane_code"],
            row["checksum"],
            row["memory_preview"],
            row["recall_query"],
            row["recall_result"],
            row["expiration"],
        ]
        for row in store.ledger
    ]
