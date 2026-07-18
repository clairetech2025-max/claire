from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from are_memory_store import AREMemoryStore
from diode_protocol import DiodeProtocol
from faiss_memory_index import FaissMemoryIndex
from original_are_bridge import read_original_are_history


class GovernedARE:
    """
    Non-destructive coordinator for CLAIRE memory recall.

    Original ARE JSONL remains chronological authority. AREMemoryStore remains
    metadata / scope / lane / audit authority. FAISS is only an optional
    relevance layer over already-allowed candidates.
    """

    def __init__(
        self,
        *,
        memory_store: AREMemoryStore | None = None,
        original_memory_path: str | Path | None = None,
        index: FaissMemoryIndex | None = None,
    ) -> None:
        self.memory_store = memory_store
        self.original_memory_path = Path(original_memory_path) if original_memory_path is not None else None
        self.index = index or FaissMemoryIndex()

    def chronological_records(self, *, limit: int = 50) -> list[dict[str, Any]]:
        history = read_original_are_history(limit=limit, memory_path=self.original_memory_path, create=False)
        memory_file = history.get("memory_file") or str(self.original_memory_path or "")
        records: list[dict[str, Any]] = []
        for item in history.get("records", []):
            text = str(item.get("text") or "")
            sha = str(item.get("sha") or hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:10])
            records.append(
                {
                    "memory_id": f"original_are_{sha}",
                    "timestamp_ns": int(item.get("ts") or 0) * 1_000_000_000,
                    "lane": "ORIGINAL_ARE",
                    "memory_scope": "PUBLIC",
                    "summary": DiodeProtocol.redact(text)[:500],
                    "raw_excerpt": DiodeProtocol.redact(text)[:2000],
                    "source": "original_are",
                    "source_path": memory_file,
                    "sha": sha,
                    "provenance_hash": sha,
                    "line_number": item.get("line_number"),
                }
            )
        return records

    def governed_records(
        self,
        *,
        user_id: str,
        allowed_lanes: list[str],
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        if self.memory_store is None:
            return []
        records = self.memory_store.recall_for_lanes(user_id, allowed_lanes, limit=limit)
        safe_records: list[dict[str, Any]] = []
        for record in records:
            safe = dict(record)
            for key in ("summary", "raw_excerpt", "text"):
                if key in safe:
                    safe[key] = DiodeProtocol.redact(str(safe.get(key) or ""))
            safe_records.append(safe)
        return safe_records

    def recall(
        self,
        *,
        query: str,
        user_id: str = "default",
        lane: str = "GENERAL_CHAT",
        allowed_lanes: list[str] | None = None,
        allowed_scopes: list[str] | None = None,
        limit: int = 5,
        include_original_are: bool = True,
        persist_index: bool = False,
    ) -> dict[str, Any]:
        safe_query = DiodeProtocol.redact(query)
        lane_set = set(allowed_lanes or [lane])
        scope_set = set(allowed_scopes or ["PUBLIC"])

        candidates: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        if include_original_are and "PUBLIC" in scope_set:
            candidates.extend(self.chronological_records(limit=200))

        candidates.extend(
            self.governed_records(
                user_id=user_id,
                allowed_lanes=sorted(lane_set),
                limit=200,
            )
        )

        allowed: list[dict[str, Any]] = []
        for memory in candidates:
            memory_id = str(memory.get("memory_id") or memory.get("sha") or "")
            memory_lane = str(memory.get("lane") or "")
            memory_scope = str(memory.get("memory_scope") or "PUBLIC")

            if memory_scope not in scope_set:
                rejected.append({"memory_id": memory_id, "lane": memory_lane, "reason": "scope_not_allowed"})
                continue

            if memory_lane != "ORIGINAL_ARE" and memory_lane not in lane_set:
                rejected.append({"memory_id": memory_id, "lane": memory_lane, "reason": "lane_not_allowed"})
                continue

            if DiodeProtocol.contains_secret(str(memory.get("summary") or "") + " " + str(memory.get("raw_excerpt") or "")):
                rejected.append({"memory_id": memory_id, "lane": memory_lane, "reason": "secret_like_memory_excluded"})
                continue

            allowed.append(memory)

        build_status = self.index.build(allowed, persist=persist_index)
        ranked = self.index.search(safe_query, top_k=limit)
        ranked_ids = {item["memory_id"] for item in ranked}
        chronology = sorted(
            [
                {
                    "memory_id": memory.get("memory_id"),
                    "sha": memory.get("sha") or memory.get("provenance_hash"),
                    "timestamp_ns": memory.get("timestamp_ns"),
                    "lane": memory.get("lane"),
                    "memory_scope": memory.get("memory_scope"),
                    "source": memory.get("source"),
                }
                for memory in allowed
            ],
            key=lambda item: int(item.get("timestamp_ns") or 0),
        )

        return {
            "query_hash": DiodeProtocol.request_hash(safe_query),
            "lane": lane,
            "allowed_lanes": sorted(lane_set),
            "allowed_scopes": sorted(scope_set),
            "source_of_truth": {
                "chronology": "original_are_jsonl",
                "metadata": "governed_sqlite_store",
                "relevance": "faiss_optional_index",
            },
            "faiss": build_status,
            "memory_leads": [item for item in ranked if item["memory_id"] in ranked_ids],
            "chronology": chronology,
            "rejected": rejected,
        }

