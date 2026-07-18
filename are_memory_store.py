from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MemoryEvent:
    memory_id: str = ""
    timestamp_ns: int = 0
    user_id: str = "default"
    session_id: str = "default"
    lane: str = "GENERAL_CHAT"
    event_type: str = "message"
    summary: str = ""
    raw_excerpt: str = ""
    source: str = "user"
    confidence: float = 1.0
    provenance_hash: str = ""
    importance_score: float = 0.0
    expires_at: str | None = None
    related_entities: list[str] = field(default_factory=list)
    write_reason: str = ""
    memory_scope: str = "PUBLIC"

    def normalize(self) -> "MemoryEvent":
        if not self.memory_id:
            self.memory_id = f"mem_{uuid.uuid4().hex[:16]}"
        if not self.timestamp_ns:
            self.timestamp_ns = time.time_ns()
        if not self.provenance_hash:
            payload = f"{self.timestamp_ns}|{self.user_id}|{self.session_id}|{self.lane}|{self.raw_excerpt}"
            self.provenance_hash = hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()
        self.raw_excerpt = str(self.raw_excerpt or "")[:2000]
        self.summary = str(self.summary or self.raw_excerpt)[:800]
        return self

    def to_dict(self) -> dict[str, Any]:
        self.normalize()
        return asdict(self)


class AREMemoryStore:
    def __init__(self, db_path: str | Path = "claire_state/claire_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_events (
                    memory_id TEXT PRIMARY KEY,
                    timestamp_ns INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    lane TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT,
                    raw_excerpt TEXT,
                    source TEXT,
                    confidence REAL,
                    provenance_hash TEXT,
                    importance_score REAL,
                    expires_at TEXT,
                    related_entities TEXT,
                    write_reason TEXT,
                    memory_scope TEXT DEFAULT 'PUBLIC'
                )
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(memory_events)").fetchall()}
            if "memory_scope" not in columns:
                conn.execute("ALTER TABLE memory_events ADD COLUMN memory_scope TEXT DEFAULT 'PUBLIC'")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entities (
                    entity TEXT NOT NULL,
                    entity_type TEXT,
                    memory_id TEXT NOT NULL,
                    PRIMARY KEY(entity, memory_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_links (
                    source_memory_id TEXT NOT NULL,
                    target_memory_id TEXT NOT NULL,
                    relation TEXT,
                    created_ns INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_trace (
                    trace_id TEXT PRIMARY KEY,
                    timestamp_ns INTEGER NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    lane TEXT,
                    payload_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_ns INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    memory_id TEXT,
                    detail_json TEXT
                )
            """)

    def append_memory_event(self, event: MemoryEvent | dict[str, Any]) -> dict[str, Any]:
        if isinstance(event, dict):
            event = MemoryEvent(**{k: v for k, v in event.items() if k in MemoryEvent.__dataclass_fields__})
        event.normalize()
        data = event.to_dict()
        entities = list(data.get("related_entities") or [])
        data["related_entities"] = json.dumps(entities, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_events
                (memory_id, timestamp_ns, user_id, session_id, lane, event_type, summary, raw_excerpt, source,
                 confidence, provenance_hash, importance_score, expires_at, related_entities, write_reason, memory_scope)
                VALUES (:memory_id, :timestamp_ns, :user_id, :session_id, :lane, :event_type, :summary, :raw_excerpt,
                        :source, :confidence, :provenance_hash, :importance_score, :expires_at, :related_entities, :write_reason, :memory_scope)
            """, data)
            for entity in entities:
                conn.execute(
                    "INSERT OR IGNORE INTO memory_entities(entity, entity_type, memory_id) VALUES (?, ?, ?)",
                    (entity, None, event.memory_id),
                )
            conn.execute(
                "INSERT INTO memory_audit_log(timestamp_ns, action, memory_id, detail_json) VALUES (?, ?, ?, ?)",
                (time.time_ns(), "append_memory_event", event.memory_id, json.dumps({"lane": event.lane, "source": event.source})),
            )
        result = event.to_dict()
        result["related_entities"] = entities
        return result

    def _rows(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        for row in rows:
            try:
                row["related_entities"] = json.loads(row.get("related_entities") or "[]")
            except Exception:
                row["related_entities"] = []
        return rows

    def recall_recent(self, user_id: str, lane: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        if lane is None:
            return self._rows(
                """
                SELECT * FROM memory_events
                WHERE user_id = ?
                ORDER BY timestamp_ns DESC LIMIT ?
                """,
                (user_id, int(limit)),
            )[::-1]
        return self._rows(
            """
            SELECT * FROM memory_events
            WHERE user_id = ? AND (lane = ? OR lane = 'GENERAL_CHAT' OR event_type = 'session_turn')
            ORDER BY timestamp_ns DESC LIMIT ?
            """,
            (user_id, lane, int(limit)),
        )[::-1]

    def recall_for_lanes(self, user_id: str, lanes: list[str], limit: int = 200) -> list[dict[str, Any]]:
        clean_lanes = [str(lane) for lane in lanes if str(lane or "").strip()]
        if not clean_lanes:
            return []
        placeholders = ",".join("?" for _ in clean_lanes)
        return self._rows(
            f"""
            SELECT * FROM memory_events
            WHERE user_id = ? AND lane IN ({placeholders})
            ORDER BY timestamp_ns DESC LIMIT ?
            """,
            tuple([user_id, *clean_lanes, int(limit)]),
        )[::-1]

    def recall_by_entity(self, user_id: str, entities: list[str], lane: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if not entities:
            return []
        placeholders = ",".join("?" for _ in entities)
        params: list[Any] = [user_id, *entities]
        lane_clause = ""
        if lane:
            lane_clause = " AND me.lane = ?"
            params.append(lane)
        return self._rows(
            f"""
            SELECT DISTINCT me.* FROM memory_events me
            JOIN memory_entities ent ON ent.memory_id = me.memory_id
            WHERE me.user_id = ? AND ent.entity IN ({placeholders}){lane_clause}
            ORDER BY me.timestamp_ns DESC LIMIT {int(limit)}
            """,
            tuple(params),
        )[::-1]

    def recall_by_time_window(self, user_id: str, start: int, end: int, lane: str | None = None) -> list[dict[str, Any]]:
        if lane:
            return self._rows(
                "SELECT * FROM memory_events WHERE user_id = ? AND lane = ? AND timestamp_ns BETWEEN ? AND ? ORDER BY timestamp_ns ASC",
                (user_id, lane, int(start), int(end)),
            )
        return self._rows(
            "SELECT * FROM memory_events WHERE user_id = ? AND timestamp_ns BETWEEN ? AND ? ORDER BY timestamp_ns ASC",
            (user_id, int(start), int(end)),
        )

    def recall_project_context(self, project_name: str, limit: int = 20) -> list[dict[str, Any]]:
        term = f"%{project_name}%"
        return self._rows(
            "SELECT * FROM memory_events WHERE summary LIKE ? OR raw_excerpt LIKE ? ORDER BY timestamp_ns DESC LIMIT ?",
            (term, term, int(limit)),
        )[::-1]

    def summarize_memory_path(self, memory_ids: list[str]) -> list[dict[str, Any]]:
        if not memory_ids:
            return []
        placeholders = ",".join("?" for _ in memory_ids)
        rows = self._rows(f"SELECT * FROM memory_events WHERE memory_id IN ({placeholders})", tuple(memory_ids))
        order = {mid: i for i, mid in enumerate(memory_ids)}
        rows.sort(key=lambda row: order.get(row.get("memory_id"), 9999))
        return [{"memory_id": row["memory_id"], "timestamp_ns": row["timestamp_ns"], "lane": row["lane"], "summary": row["summary"], "source": row["source"]} for row in rows]

    def append_session_trace(self, trace_id: str, user_id: str, session_id: str, lane: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session_trace(trace_id, timestamp_ns, user_id, session_id, lane, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (trace_id, time.time_ns(), user_id, session_id, lane, json.dumps(payload, ensure_ascii=False)),
            )
