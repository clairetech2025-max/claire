from __future__ import annotations

import json
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

CREATE TABLE IF NOT EXISTS opportunity_events (
    event_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    truth_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_opportunity_events_opportunity
    ON opportunity_events(opportunity_id, created_at);

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

    def get_evidence_by_checksum(self, checksum: str) -> AdmittedEvidence | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM admitted_evidence WHERE checksum = ?", (checksum,)).fetchone()
        return self._evidence_from_row(row) if row else None

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
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO opportunity_events (
                    event_id, opportunity_id, event_type, payload_json, truth_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, opportunity_id, event_type, json.dumps(payload, sort_keys=True), truth_hash, created_at or time.time()),
            )

    def list_opportunity_events(self, opportunity_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM opportunity_events"
        params: tuple[Any, ...] = ()
        if opportunity_id:
            query += " WHERE opportunity_id = ?"
            params = (opportunity_id,)
        query += " ORDER BY created_at ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "opportunity_id": row["opportunity_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "truth_hash": row["truth_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def append_projection_event(self, *, event_id: str, title: str, payload: dict[str, Any], truth_hash: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO projection_events (event_id, title, payload_json, truth_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (event_id, title, json.dumps(payload, sort_keys=True), truth_hash, time.time()),
            )

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
