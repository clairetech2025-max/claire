from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

TRACE_PATH = Path("data/claire_runtime_traces.jsonl")
TRACE_DB_PATH = Path("claire_state/claire_runtime_traces.db")


def new_trace_id() -> str:
    return f"trace_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def sha_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()


class TraceLogger:
    def __init__(self, path: str | Path = TRACE_PATH, db_path: str | Path = TRACE_DB_PATH):
        self.path = Path(path)
        self.db_path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_traces (
                    trace_id TEXT PRIMARY KEY,
                    timestamp_ns INTEGER NOT NULL,
                    user_message_hash TEXT NOT NULL,
                    lane TEXT NOT NULL,
                    memories_recalled TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    validator_result TEXT NOT NULL,
                    final_answer_hash TEXT NOT NULL,
                    memory_written INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)

    def log(self, record: dict[str, Any]) -> dict[str, Any]:
        record = dict(record)
        record.setdefault("trace_id", new_trace_id())
        record.setdefault("timestamp_ns", time.time_ns())
        if record["timestamp_ns"] is None:
            record["timestamp_ns"] = time.time_ns()
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO runtime_traces (
                    trace_id, timestamp_ns, user_message_hash, lane, memories_recalled,
                    prompt_hash, model_used, risk_level, validator_result,
                    final_answer_hash, memory_written, payload_json
                ) VALUES (
                    :trace_id, :timestamp_ns, :user_message_hash, :lane, :memories_recalled,
                    :prompt_hash, :model_used, :risk_level, :validator_result,
                    :final_answer_hash, :memory_written, :payload_json
                )
            """, {
                "trace_id": record["trace_id"],
                "timestamp_ns": int(record["timestamp_ns"]),
                "user_message_hash": str(record.get("user_message_hash") or ""),
                "lane": str(record.get("lane") or "UNKNOWN"),
                "memories_recalled": json.dumps(record.get("memories_recalled") or [], ensure_ascii=False),
                "prompt_hash": str(record.get("prompt_hash") or ""),
                "model_used": str(record.get("model_used") or "unknown"),
                "risk_level": str(record.get("risk_level") or "unknown"),
                "validator_result": json.dumps(record.get("validator_result") or {}, ensure_ascii=False),
                "final_answer_hash": str(record.get("final_answer_hash") or ""),
                "memory_written": 1 if record.get("memory_written") else 0,
                "payload_json": json.dumps(record, ensure_ascii=False),
            })
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def get(self, trace_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_traces WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
        if row:
            return json.loads(row["payload_json"])
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("trace_id") == trace_id:
                    return record
        return None
