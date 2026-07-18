from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from claire_vde.evidence import AdmittedEvidence


SQLITE_SCHEMA_SQL = """
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

CREATE TABLE IF NOT EXISTS api_rate_limits (
    client_key TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    request_count INTEGER NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (client_key, window_start)
);

CREATE TABLE IF NOT EXISTS api_request_audit (
    audit_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    method TEXT NOT NULL,
    route TEXT NOT NULL,
    action TEXT NOT NULL,
    client_key TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL
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

POSTGRES_MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / "venture_intelligence_postgres.sql"
SQLITE_PLACEHOLDER_RE = re.compile(r"\?")


def _split_sql_script(script: str) -> list[str]:
    statements: list[str] = []
    for chunk in script.split(";"):
        statement = chunk.strip()
        if not statement:
            continue
        lines = [line for line in statement.splitlines() if not line.lstrip().startswith("--")]
        cleaned = "\n".join(lines).strip()
        if cleaned:
            statements.append(cleaned)
    return statements


def _render_sql(sql: str, backend: str) -> str:
    if backend == "postgresql":
        return SQLITE_PLACEHOLDER_RE.sub("%s", sql)
    return sql


def _load_postgres_schema_sql() -> str:
    return POSTGRES_MIGRATION_PATH.read_text(encoding="utf-8")


def _coerce_json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except Exception:
            return default
    return default


@dataclass
class _ConnectionProxy:
    conn: Any
    backend: str

    def execute(self, sql: str, params: Any | None = None) -> Any:
        rendered = _render_sql(sql, self.backend)
        if params is None:
            return self.conn.execute(rendered)
        return self.conn.execute(rendered, params)

    def executemany(self, sql: str, params_seq: Any) -> Any:
        rendered = _render_sql(sql, self.backend)
        return self.conn.executemany(rendered, params_seq)

    def executescript(self, script: str) -> None:
        if self.backend == "sqlite":
            self.conn.executescript(script)
            return
        for statement in _split_sql_script(script):
            self.execute(statement)

    def __getattr__(self, item: str) -> Any:
        return getattr(self.conn, item)


class _SQLiteBackend:
    kind = "sqlite"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def locator(self) -> str:
        return str(self.db_path)

    @contextmanager
    def connect(self) -> Iterator[_ConnectionProxy]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield _ConnectionProxy(conn=conn, backend=self.kind)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SQLITE_SCHEMA_SQL)

    def column_names(self, table: str) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    def close(self) -> None:
        return None


class _PostgresBackend:
    kind = "postgresql"

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - dependency enforced by runtime build
            raise RuntimeError("PostgreSQL backend requires psycopg[binary,pool]") from exc

        self._dict_row = dict_row
        self._pool = ConnectionPool(
            conninfo=self.database_url,
            min_size=1,
            max_size=4,
            timeout=5.0,
            kwargs={
                "row_factory": self._dict_row,
                "autocommit": False,
                "prepare_threshold": 0,
            },
        )

    @property
    def locator(self) -> str:
        return _redact_database_url(self.database_url)

    @contextmanager
    def connect(self) -> Iterator[_ConnectionProxy]:
        with self._pool.connection() as conn:
            conn.row_factory = self._dict_row
            yield _ConnectionProxy(conn=conn, backend=self.kind)

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_load_postgres_schema_sql())

    def column_names(self, table: str) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = ?
                ORDER BY ordinal_position
                """,
                (table,),
            ).fetchall()
        return {str(row["column_name"]) for row in rows}

    def close(self) -> None:
        self._pool.close()


def _redact_database_url(database_url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    split = urlsplit(database_url)
    if "@" not in split.netloc:
        return database_url
    userinfo, hostinfo = split.netloc.rsplit("@", 1)
    if ":" in userinfo:
        username, _password = userinfo.split(":", 1)
        redacted = f"{username}:***"
    else:
        redacted = userinfo
    return urlunsplit((split.scheme, f"{redacted}@{hostinfo}", split.path, split.query, split.fragment))


class VentureRepository:
    """Subordinate Venture Intelligence metadata store."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        database_url = os.environ.get("CLAIRE_VDE_DATABASE_URL", "").strip() or None
        sqlite_path = Path(db_path or os.environ.get("CLAIRE_VDE_DB_PATH", "data/venture_intelligence.sqlite")).resolve()
        if database_url and db_path is None:
            self._backend = _PostgresBackend(database_url)
            self.database_url = database_url
            self.db_path = None
        else:
            self._backend = _SQLiteBackend(sqlite_path)
            self.database_url = None
            self.db_path = sqlite_path
        self._init_schema()

    @property
    def backend_name(self) -> str:
        return self._backend.kind

    @property
    def backend_locator(self) -> str:
        return self._backend.locator

    def describe_backend(self) -> dict[str, str]:
        return {"backend": self.backend_name, "locator": self.backend_locator}

    def connect(self):
        return self._backend.connect()

    def _init_schema(self) -> None:
        deadline = time.monotonic() + 30.0 if self.backend_name == "postgresql" else time.monotonic()
        last_error: Exception | None = None
        while True:
            try:
                self._backend.init_schema()
                with self.connect() as conn:
                    self._migrate_opportunity_events(conn)
                return
            except Exception as exc:
                last_error = exc
                if self.backend_name != "postgresql" or time.monotonic() >= deadline:
                    raise
                time.sleep(1.0)
        if last_error is not None:  # pragma: no cover - defensive
            raise last_error

    def _migrate_opportunity_events(self, conn: sqlite3.Connection) -> None:
        if self.backend_name == "postgresql":
            columns = self._backend.column_names("opportunity_events")
        else:
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
                payload = _coerce_json_value(row["payload_json"], {})
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
                metadata = _coerce_json_value(row["metadata_json"], {})
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
                metadata = _coerce_json_value(row["metadata_json"], {})
            except Exception:
                metadata = {}
            if str(metadata.get("content_hash") or "") == str(content_hash or ""):
                return self._evidence_from_row(row)
        return None

    def insert_evidence(self, evidence: AdmittedEvidence) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO admitted_evidence (
                    are_hash, checksum, title, text, source, collector, plane,
                    value, precision, confidence, provenance_url, entity_refs_json,
                    metadata_json, admitted_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(checksum) DO NOTHING
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

    def try_claim_admission(self, content_hash: str, *, stale_after_s: float = 30.0) -> bool:
        now = time.time()
        cutoff = now - max(0.0, float(stale_after_s))
        with self.connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO admission_claims (content_hash, status, updated_at) VALUES (?, 'claiming', ?)",
                    (content_hash, now),
                )
                return True
            except sqlite3.IntegrityError:
                result = conn.execute(
                    """
                    UPDATE admission_claims
                    SET status = 'claiming',
                        are_hash = '',
                        updated_at = ?,
                        last_error = ''
                    WHERE content_hash = ?
                      AND status = 'claiming'
                      AND updated_at < ?
                    """,
                    (now, content_hash, cutoff),
                )
                return bool(result.rowcount)

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

    def record_api_audit(
        self,
        *,
        trace_id: str,
        method: str,
        route: str,
        action: str,
        client_key: str,
        decision: str,
        reason: str,
    ) -> None:
        audit_id = "audit_" + uuid.uuid4().hex[:16]
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO api_request_audit (
                    audit_id, trace_id, method, route, action, client_key,
                    decision, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    trace_id,
                    method,
                    route,
                    action,
                    client_key,
                    decision,
                    reason,
                    time.time(),
                ),
            )

    def record_rate_limit_hit(self, *, client_key: str, window_start: int) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO api_rate_limits (client_key, window_start, request_count, updated_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(client_key, window_start) DO UPDATE SET
                    request_count = api_rate_limits.request_count + 1,
                    updated_at = excluded.updated_at
                RETURNING request_count
                """,
                (client_key, int(window_start), time.time()),
            ).fetchone()
        return int(row["request_count"]) if row else 0

    def get_rate_limit_count(self, *, client_key: str, window_start: int) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT request_count
                FROM api_rate_limits
                WHERE client_key = ? AND window_start = ?
                """,
                (client_key, int(window_start)),
            ).fetchone()
        return int(row["request_count"]) if row else 0

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
                "payload": _coerce_json_value(row["payload_json"], {}),
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
            entity_refs=list(_coerce_json_value(row["entity_refs_json"], [])),
            metadata=dict(_coerce_json_value(row["metadata_json"], {})),
            admitted_at=float(row["admitted_at"]),
        )
