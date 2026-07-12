from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from claire_vde.evidence import AdmittedEvidence


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS admitted_evidence (
    are_hash TEXT PRIMARY KEY,
    checksum TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    collector TEXT NOT NULL,
    plane TEXT NOT NULL,
    value REAL NOT NULL,
    precision REAL NOT NULL,
    confidence REAL NOT NULL,
    provenance_url TEXT NOT NULL DEFAULT '',
    entity_refs_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    admitted_at REAL NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_admitted_evidence_plane ON admitted_evidence(plane);
CREATE INDEX IF NOT EXISTS idx_admitted_evidence_collector ON admitted_evidence(collector);
CREATE INDEX IF NOT EXISTS idx_admitted_evidence_source ON admitted_evidence(source);

CREATE TABLE IF NOT EXISTS collector_state (
    collector TEXT PRIMARY KEY,
    last_cursor TEXT,
    last_run_at REAL,
    status TEXT NOT NULL,
    error_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS collector_runs (
    run_id TEXT PRIMARY KEY,
    collector TEXT NOT NULL,
    admitted_count INTEGER NOT NULL,
    error_json TEXT NOT NULL DEFAULT '[]',
    next_cursor TEXT,
    started_at REAL NOT NULL,
    finished_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS admission_claims (
    content_hash TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    are_hash TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL,
    last_error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reconciliation_state (
    name TEXT PRIMARY KEY,
    last_sequence INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_events (
    ledger_seq INTEGER NOT NULL UNIQUE,
    event_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    truth_hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL DEFAULT '0',
    event_hash TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS projection_events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    truth_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class VentureRepository:
    """Subordinate Venture Intelligence metadata store."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.environ.get("CLAIRE_VDE_DB_PATH", "data/venture_intelligence.sqlite")).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_opportunity_events(conn)

    def _migrate_opportunity_events(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(opportunity_events)").fetchall()
        }
        additions = []
        if "ledger_seq" not in columns:
            additions.append("ALTER TABLE opportunity_events ADD COLUMN ledger_seq INTEGER")
        if "previous_hash" not in columns:
            additions.append("ALTER TABLE opportunity_events ADD COLUMN previous_hash TEXT NOT NULL DEFAULT '0'")
        if "event_hash" not in columns:
            additions.append("ALTER TABLE opportunity_events ADD COLUMN event_hash TEXT NOT NULL DEFAULT ''")
        for statement in additions:
            conn.execute(statement)
        if "ledger_seq" not in columns or "previous_hash" not in columns or "event_hash" not in columns:
            rows = conn.execute(
                "SELECT event_id, opportunity_id, event_type, payload_json, truth_hash, created_at FROM opportunity_events ORDER BY created_at ASC, event_id ASC"
            ).fetchall()
            previous_hash = "0"
            for seq, row in enumerate(rows, start=1):
                payload = json.loads(row["payload_json"])
                event_hash = self._ledger_event_hash(
                    ledger_seq=seq,
                    event_id=row["event_id"],
                    opportunity_id=row["opportunity_id"],
                    event_type=row["event_type"],
                    payload=payload,
                    truth_hash=row["truth_hash"],
                    previous_hash=previous_hash,
                    created_at=float(row["created_at"]),
                )
                conn.execute(
                    """
                    UPDATE opportunity_events
                    SET ledger_seq = ?, previous_hash = ?, event_hash = ?
                    WHERE event_id = ?
                    """,
                    (seq, previous_hash, event_hash, row["event_id"]),
                )
                previous_hash = event_hash
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_opportunity_events_ledger_seq_unique ON opportunity_events(ledger_seq)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_opportunity_events_opportunity ON opportunity_events(opportunity_id, ledger_seq)"
        )

    def get_evidence_by_checksum(self, checksum: str) -> AdmittedEvidence | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM admitted_evidence WHERE checksum = ?", (checksum,)).fetchone()
        return self._evidence_from_row(row) if row else None

    def get_evidence_by_source_record_id(self, source_record_id: str) -> AdmittedEvidence | None:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM admitted_evidence ORDER BY admitted_at DESC").fetchall()
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except Exception:
                metadata = {}
            if str(metadata.get("source_record_id") or "") == str(source_record_id or ""):
                return self._evidence_from_row(row)
        return None

    def get_evidence_by_content_hash(self, content_hash: str) -> AdmittedEvidence | None:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM admitted_evidence ORDER BY admitted_at DESC").fetchall()
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except Exception:
                metadata = {}
            if str(metadata.get("content_hash") or "") == str(content_hash or ""):
                return self._evidence_from_row(row)
        return None

    def insert_evidence(self, evidence: AdmittedEvidence) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO admitted_evidence (
                    are_hash, checksum, title, text, source, collector, plane,
                    value, precision, confidence, provenance_url, entity_refs_json,
                    metadata_json, admitted_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.are_hash,
                    evidence.checksum,
                    evidence.title,
                    evidence.text,
                    evidence.source,
                    evidence.collector,
                    evidence.plane,
                    float(evidence.value),
                    float(evidence.precision),
                    float(evidence.confidence),
                    evidence.provenance_url,
                    json.dumps(evidence.entity_refs, sort_keys=True),
                    json.dumps(evidence.metadata, sort_keys=True),
                    float(evidence.admitted_at),
                    time.time(),
                ),
            )

    def upsert_admission_claim(self, *, content_hash: str, status: str, are_hash: str = "", last_error: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO admission_claims (content_hash, status, are_hash, updated_at, last_error)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(content_hash) DO UPDATE SET
                    status = excluded.status,
                    are_hash = excluded.are_hash,
                    updated_at = excluded.updated_at,
                    last_error = excluded.last_error
                """,
                (content_hash, status, are_hash, time.time(), last_error),
            )

    def try_claim_admission(self, content_hash: str) -> bool:
        with self.connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO admission_claims (content_hash, status, updated_at) VALUES (?, 'claiming', ?)",
                    (content_hash, time.time()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def mark_admission_committed(self, content_hash: str, are_hash: str) -> None:
        self.upsert_admission_claim(content_hash=content_hash, status="committed", are_hash=are_hash)

    def mark_admission_error(self, content_hash: str, error: str) -> None:
        self.upsert_admission_claim(content_hash=content_hash, status="error", last_error=error)

    def get_admission_claim(self, content_hash: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT content_hash, status, are_hash, updated_at, last_error FROM admission_claims WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
        if not row:
            return None
        return {
            "content_hash": row["content_hash"],
            "status": row["status"],
            "are_hash": row["are_hash"],
            "updated_at": row["updated_at"],
            "last_error": row["last_error"],
        }

    def get_admission_claim_status(self, content_hash: str) -> str | None:
        claim = self.get_admission_claim(content_hash)
        return str(claim["status"]) if claim else None

    def wait_for_admission_resolution(self, content_hash: str, timeout: float = 5.0) -> str | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.get_admission_claim_status(content_hash)
            if status in {"committed", "error"}:
                return status
            time.sleep(0.02)
        return None

    def list_admission_claims(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT content_hash, status, are_hash, updated_at, last_error FROM admission_claims ORDER BY updated_at ASC"
            ).fetchall()
        return [
            {
                "content_hash": row["content_hash"],
                "status": row["status"],
                "are_hash": row["are_hash"],
                "updated_at": row["updated_at"],
                "last_error": row["last_error"],
            }
            for row in rows
        ]

    def get_reconciliation_checkpoint(self, name: str) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT last_sequence FROM reconciliation_state WHERE name = ?", (name,)).fetchone()
        return int(row["last_sequence"]) if row else 0

    def set_reconciliation_checkpoint(self, name: str, last_sequence: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reconciliation_state (name, last_sequence, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    last_sequence = excluded.last_sequence,
                    updated_at = excluded.updated_at
                """,
                (name, int(last_sequence), time.time()),
            )

    def list_evidence(self, limit: int = 100) -> list[AdmittedEvidence]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM admitted_evidence ORDER BY admitted_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def save_collector_run(
        self,
        *,
        run_id: str,
        collector: str,
        admitted_count: int,
        errors: list[str],
        next_cursor: str | None,
        started_at: float,
        finished_at: float,
    ) -> None:
        status = "ok" if not errors else "error"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO collector_runs (
                    run_id, collector, admitted_count, error_json, next_cursor, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, collector, int(admitted_count), json.dumps(errors), next_cursor, started_at, finished_at),
            )
            conn.execute(
                """
                INSERT INTO collector_state (collector, last_cursor, last_run_at, status, error_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(collector) DO UPDATE SET
                    last_cursor = excluded.last_cursor,
                    last_run_at = excluded.last_run_at,
                    status = excluded.status,
                    error_json = excluded.error_json
                """,
                (collector, next_cursor, finished_at, status, json.dumps(errors)),
            )

    def get_collector_cursor(self, collector: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT last_cursor FROM collector_state WHERE collector = ?", (collector,)).fetchone()
        return str(row["last_cursor"]) if row and row["last_cursor"] is not None else None

    def append_opportunity_event(
        self,
        *,
        event_id: str,
        opportunity_id: str,
        event_type: str,
        payload: dict[str, Any],
        truth_hash: str,
        created_at: float | None = None,
    ) -> None:
        created_at = created_at or time.time()
        with self.connect() as conn:
            last_row = conn.execute(
                "SELECT ledger_seq, event_hash FROM opportunity_events ORDER BY ledger_seq DESC LIMIT 1"
            ).fetchone()
            ledger_seq = int(last_row["ledger_seq"]) + 1 if last_row else 1
            previous_hash = str(last_row["event_hash"]) if last_row else "0"
            event_hash = self._ledger_event_hash(
                ledger_seq=ledger_seq,
                event_id=event_id,
                opportunity_id=opportunity_id,
                event_type=event_type,
                payload=payload,
                truth_hash=truth_hash,
                previous_hash=previous_hash,
                created_at=created_at,
            )
            conn.execute(
                """
                INSERT INTO opportunity_events (
                    ledger_seq, event_id, opportunity_id, event_type, payload_json, truth_hash, previous_hash, event_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ledger_seq,
                    event_id,
                    opportunity_id,
                    event_type,
                    json.dumps(payload, sort_keys=True),
                    truth_hash,
                    previous_hash,
                    event_hash,
                    created_at,
                ),
            )

    def list_opportunity_events(self, opportunity_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM opportunity_events"
        params: tuple[Any, ...] = ()
        if opportunity_id:
            query += " WHERE opportunity_id = ?"
            params = (opportunity_id,)
        query += " ORDER BY ledger_seq ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "ledger_seq": row["ledger_seq"],
                "event_id": row["event_id"],
                "opportunity_id": row["opportunity_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "truth_hash": row["truth_hash"],
                "previous_hash": row["previous_hash"],
                "event_hash": row["event_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def verify_opportunity_ledger(self) -> dict[str, Any]:
        previous_hash = "0"
        rows = self.list_opportunity_events()
        for index, row in enumerate(rows):
            expected_hash = self._ledger_event_hash(
                ledger_seq=int(row["ledger_seq"]),
                event_id=str(row["event_id"]),
                opportunity_id=str(row["opportunity_id"]),
                event_type=str(row["event_type"]),
                payload=row["payload"],
                truth_hash=str(row["truth_hash"]),
                previous_hash=previous_hash,
                created_at=float(row["created_at"]),
            )
            if str(row["previous_hash"]) != previous_hash:
                return {
                    "valid": False,
                    "reason": "previous_hash_mismatch",
                    "index": index,
                    "event_id": row["event_id"],
                }
            if str(row["event_hash"]) != expected_hash:
                return {
                    "valid": False,
                    "reason": "event_hash_mismatch",
                    "index": index,
                    "event_id": row["event_id"],
                }
            previous_hash = expected_hash
        return {"valid": True, "records": len(rows), "previous_hash": previous_hash}

    def append_projection_event(self, *, event_id: str, title: str, payload: dict[str, Any], truth_hash: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO projection_events (event_id, title, payload_json, truth_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (event_id, title, json.dumps(payload, sort_keys=True), truth_hash, time.time()),
            )

    def _ledger_event_hash(
        self,
        *,
        ledger_seq: int,
        event_id: str,
        opportunity_id: str,
        event_type: str,
        payload: dict[str, Any],
        truth_hash: str,
        previous_hash: str,
        created_at: float,
    ) -> str:
        body = {
            "ledger_seq": int(ledger_seq),
            "event_id": str(event_id),
            "opportunity_id": str(opportunity_id),
            "event_type": str(event_type),
            "payload": payload,
            "truth_hash": str(truth_hash),
            "previous_hash": str(previous_hash),
            "created_at": float(created_at),
        }
        return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _evidence_from_row(self, row: sqlite3.Row) -> AdmittedEvidence:
        return AdmittedEvidence(
            title=str(row["title"]),
            text=str(row["text"]),
            source=str(row["source"]),
            collector=str(row["collector"]),
            plane=str(row["plane"]),
            value=float(row["value"]),
            precision=float(row["precision"]),
            confidence=float(row["confidence"]),
            are_hash=str(row["are_hash"]),
            checksum=str(row["checksum"]),
            provenance_url=str(row["provenance_url"] or ""),
            entity_refs=list(json.loads(row["entity_refs_json"] or "[]")),
            metadata=dict(json.loads(row["metadata_json"] or "{}")),
            admitted_at=float(row["admitted_at"]),
        )
