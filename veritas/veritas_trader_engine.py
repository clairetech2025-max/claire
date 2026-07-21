#!/usr/bin/env python3
"""
VERITAS TRADER ENGINE (AZURE FINANCIAL INTELLIGENCE STATION)
------------------------------------------------------------
Paper-first trading framework for Claire / VERITAS.

Safety contract:
  - Defaults to paper mode.
  - Never sends real exchange orders.
  - Live mode fails closed until a real live broker is deliberately implemented.
  - Simulated data is labeled as simulated unless Kraken historical candles are used
    for backtesting.
"""

import csv
import getpass
import gc
import hashlib
import hmac
import json
import math
import os
import queue
import random
import sqlite3
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =====================================================================
# 0. CONFIGURATION, FLAGS & INTEGRITY GATES
# =====================================================================

STRATEGY_NAME = "Claire_Core_Analog_Recall"
STRATEGY_VERSION = "2.2.0"
STRATEGY_PARAMS_HASH = hashlib.sha256(b"claire_default_v2.2").hexdigest()[:12]

SUPPORTED_MODES = {"paper", "backtest", "live_dry_run", "live"}
TRADING_MODE = os.environ.get("VERITAS_TRADING_MODE", "paper").strip().lower() or "paper"
if TRADING_MODE not in SUPPORTED_MODES:
    TRADING_MODE = "paper"

ENABLE_LIVE_TRADING = os.environ.get("VERITAS_ENABLE_LIVE_TRADING", "false").lower() == "true"
LIVE_PASSPHRASE_HASH = os.environ.get("VERITAS_LIVE_PASSPHRASE_HASH", "")
SECRET_KEY_RAW = os.environ.get("VERITAS_HMAC_KEY", "veritas-paper-default-hmac-key")
SECRET_INTEGRITY_KEY = SECRET_KEY_RAW.encode("utf-8")

TRADEABLE_ASSETS = ["XAUUSD", "USOUSD", "EURUSD", "SPY", "XBTUSD", "ETHUSD"]
MAX_STALE_AGE_MS = int(os.environ.get("VERITAS_MAX_SIGNAL_AGE_MS", "5000"))
MAX_MARKET_PRICE_AGE_MS = int(os.environ.get("VERITAS_MAX_PRICE_AGE_MS", "10000"))
DB_PATH = Path(os.environ.get("VERITAS_DB_PATH", "veritas_system_ledger.db"))
KILL_SWITCH_FILE = Path(os.environ.get("VERITAS_KILL_SWITCH_FILE", "VERITAS_KILL_SWITCH"))
BACKTEST_REPORT_FILE = Path(".veritas_backtest_report.json")
VERITAS_TEST_PASSED_FILE = Path(".veritas_test_passed.json")
VERITAS_PAPER_BURN_IN_FILE = Path(".veritas_paper_burn_in.json")

DEFAULT_ORDER_QTY = float(os.environ.get("VERITAS_DEFAULT_ORDER_QTY", "1"))
INITIAL_BALANCE = float(os.environ.get("VERITAS_INITIAL_BALANCE", "100000"))

MICRO_LIVE_LIMITS = {
    "max_order_notional": 10.0,
    "max_daily_loss": 25.0,
    "max_open_orders": 1,
    "max_trades_per_day": 3,
    "max_position_size": 1.0,
    "max_notional_exposure": 10.0,
    "max_trades_per_hour": 3,
    "allow_leverage": False,
    "allow_margin": False,
    "allow_short_selling": False,
    "allow_market_orders": False,
}


def now_ns() -> int:
    return time.time_ns()


def redact_secrets(text: str) -> str:
    """Redact credentials and sensitive authorization material from logs."""
    if not text:
        return ""
    lowered = text.lower()
    sensitive_markers = [
        "api_key",
        "api secret",
        "api_secret",
        "passphrase",
        "authorization",
        "auth header",
        "bearer ",
        "token",
        "password",
        "credential",
        "signature",
    ]
    if any(marker in lowered for marker in sensitive_markers):
        return "[REDACTED_SECRET]"
    return text


def print_banner() -> None:
    print("=" * 80)
    print("       CLAIRE / VERITAS AZURE FINANCIAL INTELLIGENCE STATION")
    print(f"       System Mode: {TRADING_MODE.upper()}")
    if TRADING_MODE == "backtest":
        print("       DATA HONESTY INDICATOR:")
        print("       >> HISTORICAL KRAKEN CANDLES — BACKTEST MODE ACTIVE")
    else:
        print("       DATA HONESTY INDICATOR:")
        print("       >> SIMULATED DATA ONLY — NOT LIVE MARKET DATA")
    if TRADING_MODE == "live":
        print("       LIVE MODE REQUESTED — GATES REQUIRED — REAL EXECUTION NOT IMPLEMENTED")
    else:
        print("       PAPER MODE ONLY — NO LIVE ORDERS ENABLED")
    print("=" * 80)


def is_fresh_json_file(path: Path, max_age_seconds: int = 24 * 3600) -> bool:
    if not path.exists():
        return False
    try:
        if time.time() - path.stat().st_mtime > max_age_seconds:
            return False
        with path.open("r", encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception:
        return False


def stable_action_key(capsule_id: str, asset: str, direction: str, strategy_version: str = STRATEGY_VERSION) -> str:
    return hashlib.sha256(f"{capsule_id}|{asset}|{direction}|{strategy_version}".encode("utf-8")).hexdigest()


def market_price_record(price: float, source: str, max_age_ms: int = MAX_MARKET_PRICE_AGE_MS, timestamp_ns: Optional[int] = None) -> Dict[str, Any]:
    return {
        "price": float(price),
        "source": source,
        "timestamp_ns": int(timestamp_ns if timestamp_ns is not None else now_ns()),
        "max_age_ms": int(max_age_ms),
    }


def extract_price(price_obj: Any) -> float:
    if isinstance(price_obj, dict):
        return float(price_obj.get("price", 0.0))
    return float(price_obj or 0.0)


def is_market_price_fresh(price_obj: Any, at_ns: Optional[int] = None) -> bool:
    if not isinstance(price_obj, dict):
        return False
    ts_ns = int(price_obj.get("timestamp_ns", 0))
    max_age_ms = int(price_obj.get("max_age_ms", MAX_MARKET_PRICE_AGE_MS))
    if ts_ns <= 0:
        return False
    return ((at_ns or now_ns()) - ts_ns) / 1_000_000.0 <= max_age_ms


# =====================================================================
# 1. DATABASE AUDIT LEDGER
# =====================================================================


class AuditLedger:
    """SQLite audit ledger with explicit INSERT column lists."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_signals (
                    capsule_id TEXT PRIMARY KEY,
                    received_ts_ns INTEGER,
                    source_node TEXT,
                    raw_payload TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clean_signals (
                    capsule_id TEXT PRIMARY KEY,
                    received_ts_ns INTEGER,
                    sanitized_payload TEXT,
                    entropy REAL,
                    confidence REAL,
                    cryptographic_signature TEXT,
                    FOREIGN KEY(capsule_id) REFERENCES raw_signals(capsule_id)
                )
                """
            )
            self._ensure_column(conn, "clean_signals", "cryptographic_signature", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_signal_actions (
                    action_key TEXT PRIMARY KEY,
                    capsule_id TEXT,
                    asset TEXT,
                    direction TEXT,
                    strategy_version TEXT,
                    timestamp_ns INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_decisions (
                    decision_id TEXT PRIMARY KEY,
                    capsule_id TEXT,
                    timestamp_ns INTEGER,
                    asset TEXT,
                    direction TEXT,
                    confidence REAL,
                    reason TEXT,
                    is_actionable INTEGER,
                    strategy_name TEXT,
                    strategy_version TEXT,
                    parameters_hash TEXT,
                    FOREIGN KEY(capsule_id) REFERENCES raw_signals(capsule_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_checks (
                    check_id TEXT PRIMARY KEY,
                    decision_id TEXT,
                    timestamp_ns INTEGER,
                    approved INTEGER,
                    reason TEXT,
                    snapshot_json TEXT,
                    FOREIGN KEY(decision_id) REFERENCES signal_decisions(decision_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS order_intents (
                    intent_id TEXT PRIMARY KEY,
                    decision_id TEXT,
                    idempotency_key TEXT UNIQUE,
                    timestamp_ns INTEGER,
                    asset TEXT,
                    direction TEXT,
                    quantity REAL,
                    price REAL,
                    FOREIGN KEY(decision_id) REFERENCES signal_decisions(decision_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_orders (
                    order_id TEXT PRIMARY KEY,
                    intent_id TEXT,
                    state TEXT,
                    asset TEXT,
                    direction TEXT,
                    quantity REAL,
                    price REAL,
                    filled_qty REAL,
                    avg_fill_price REAL,
                    updated_ts_ns INTEGER,
                    FOREIGN KEY(intent_id) REFERENCES order_intents(intent_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_orders (
                    order_id TEXT PRIMARY KEY,
                    intent_id TEXT,
                    state TEXT,
                    asset TEXT,
                    direction TEXT,
                    quantity REAL,
                    price REAL,
                    filled_qty REAL,
                    avg_fill_price REAL,
                    broker_order_ref TEXT,
                    updated_ts_ns INTEGER,
                    FOREIGN KEY(intent_id) REFERENCES order_intents(intent_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_order_events (
                    event_id TEXT PRIMARY KEY,
                    order_id TEXT,
                    timestamp_ns INTEGER,
                    event_type TEXT,
                    event_payload TEXT,
                    FOREIGN KEY(order_id) REFERENCES live_orders(order_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_fills (
                    fill_id TEXT PRIMARY KEY,
                    order_id TEXT,
                    timestamp_ns INTEGER,
                    quantity REAL,
                    price REAL,
                    slippage REAL,
                    fee REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS system_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_ns INTEGER,
                    level TEXT,
                    category TEXT,
                    message TEXT
                )
                """
            )
            conn.commit()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
        cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def log_event(self, level: str, category: str, message: str) -> None:
        safe_message = redact_secrets(message)
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO system_logs (timestamp_ns, level, category, message) VALUES (?, ?, ?, ?)",
                (now_ns(), level, category, safe_message),
            )
            conn.commit()

    def has_duplicate_action(self, capsule_id: str, asset: str, direction: str) -> bool:
        action_key = stable_action_key(capsule_id, asset, direction)
        with self.lock, sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_signal_actions WHERE action_key = ?",
                (action_key,),
            ).fetchone()
        return row is not None

    def register_signal_action(self, capsule_id: str, asset: str, direction: str) -> None:
        action_key = stable_action_key(capsule_id, asset, direction)
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_signal_actions
                (action_key, capsule_id, asset, direction, strategy_version, timestamp_ns)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (action_key, capsule_id, asset, direction, STRATEGY_VERSION, now_ns()),
            )
            conn.commit()


# =====================================================================
# 2. TRAILLINK PROVENANCE TRACER
# =====================================================================


class TrailLinkTracer:
    """Cryptographic chain custody layer for signal provenance."""

    def __init__(self, ledger: AuditLedger, secret_key: bytes):
        self.ledger = ledger
        self.secret_key = secret_key
        self.counter_lock = threading.Lock()
        self.counter = 0

    def generate_capsule_id(self, source_node: str, timestamp_ns: int, payload: str) -> str:
        with self.counter_lock:
            self.counter += 1
            current_counter = self.counter
        entropy_base = f"{source_node}|{timestamp_ns}|{current_counter}|{payload}"
        sha_digest = hashlib.sha256(entropy_base.encode("utf-8")).hexdigest()[:32].upper()
        return f"TL-{sha_digest}"

    def calculate_signature(self, capsule_id: str, clean_payload: str) -> str:
        message = f"{capsule_id}||{clean_payload}".encode("utf-8")
        return hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()

    def register_raw_signal(self, source: str, raw_payload: str, received_ts_ns: Optional[int] = None) -> Tuple[str, int]:
        ts_ns = int(received_ts_ns if received_ts_ns is not None else now_ns())
        capsule_id = self.generate_capsule_id(source, ts_ns, raw_payload)
        with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO raw_signals
                (capsule_id, received_ts_ns, source_node, raw_payload)
                VALUES (?, ?, ?, ?)
                """,
                (capsule_id, ts_ns, source, raw_payload),
            )
            conn.commit()
        return capsule_id, ts_ns

    def register_clean_signal(self, capsule_id: str, clean_payload: str, entropy: float, confidence: float, received_ts_ns: Optional[int] = None) -> str:
        ts_ns = int(received_ts_ns if received_ts_ns is not None else now_ns())
        sig = self.calculate_signature(capsule_id, clean_payload)
        with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO clean_signals
                (capsule_id, received_ts_ns, sanitized_payload, entropy, confidence, cryptographic_signature)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (capsule_id, ts_ns, clean_payload, entropy, confidence, sig),
            )
            conn.commit()
        return sig

    def fetch_clean_signal(self, capsule_id: str) -> Optional[Tuple[str, str]]:
        with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
            return conn.execute(
                "SELECT sanitized_payload, cryptographic_signature FROM clean_signals WHERE capsule_id = ?",
                (capsule_id,),
            ).fetchone()

    def verify_signal_provenance(self, capsule_id: str) -> bool:
        try:
            row = self.fetch_clean_signal(capsule_id)
            if not row:
                self.ledger.log_event("WARNING", "PROVENANCE", f"No clean signal record for capsule {capsule_id}")
                return False
            payload, db_signature = row
            expected_sig = self.calculate_signature(capsule_id, payload)
            if hmac.compare_digest(expected_sig, db_signature or ""):
                return True
            self.ledger.log_event("CRITICAL", "PROVENANCE_VIOLATION", f"Signature mismatch for capsule_id {capsule_id}")
            return False
        except Exception as exc:
            self.ledger.log_event("ERROR", "PROVENANCE_FAIL", f"Signature verification error: {exc}")
            return False


# =====================================================================
# 3. VERITAS PARSER
# =====================================================================


class VeritasParser:
    @staticmethod
    def clean_digital_lint(raw_blob: str) -> str:
        cleaned = raw_blob.replace("<script>", "").replace("</script>", "")
        cleaned = cleaned.replace("<div>", "").replace("</div>", "")
        cleaned = " ".join(cleaned.split())
        return cleaned[:8000]

    @staticmethod
    def extract_metrics(clean_text: str) -> Dict[str, Any]:
        words = clean_text.lower().split()
        if not words:
            return {"confidence": 0.0, "entropy": 0.0, "contains_impact_keywords": False}
        unique_words = set(words)
        entropy = len(unique_words) / len(words)
        impact_keywords = [
            "interest rate",
            "fed hike",
            "arbitrage",
            "crude supply",
            "acquisition",
            "sanctions",
            "strike",
            "surges",
            "spikes",
            "approved",
            "cooler",
            "stall",
            "ban",
            "restrictions",
        ]
        contains_impact = any(keyword in clean_text.lower() for keyword in impact_keywords)
        return {
            "entropy": round(entropy, 4),
            "confidence": 1.0 if contains_impact else round(entropy * 0.7, 4),
            "contains_impact_keywords": contains_impact,
        }


# =====================================================================
# 4. ANALOG RECALL ENGINE
# =====================================================================


class AREStore:
    """Atomic JSONL memory queue with clean shutdown drain."""

    def __init__(self, fpath: Path, ledger: AuditLedger, critical_ram_kb: int = 350000):
        self.fpath = Path(fpath)
        self.ledger = ledger
        self.critical_ram_kb = critical_ram_kb
        self.lock = threading.RLock()
        self.q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._stop_event = threading.Event()
        self.max_lines = 5000
        self.fpath.parent.mkdir(parents=True, exist_ok=True)
        self.fpath.touch(exist_ok=True)
        self._bg_writer = threading.Thread(target=self._writer_loop, daemon=False)
        self._bg_gov = threading.Thread(target=self._memory_watchdog, daemon=False)
        self._bg_writer.start()
        self._bg_gov.start()

    def _get_avail_kb(self) -> int:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if "MemAvailable" in line:
                        return int(line.split()[1])
        except Exception as exc:
            self.ledger.log_event("ERROR", "MEMINFO_READ", f"Unable to read memory info: {exc}")
        return 1_000_000

    def _memory_watchdog(self) -> None:
        while not self._stop_event.is_set():
            try:
                avail = self._get_avail_kb()
                with self.lock:
                    if avail < self.critical_ram_kb:
                        self.max_lines = 500
                        gc.collect()
                        self.ledger.log_event("WARNING", "RESOURCES", f"RAM low: {avail}kB. Compress window.")
                    elif avail < 600000:
                        self.max_lines = 2000
                    else:
                        self.max_lines = 5000
            except Exception as exc:
                self.ledger.log_event("ERROR", "WATCHDOG_LOOP_ERR", str(exc))
            self._stop_event.wait(2.0)

    def _writer_loop(self) -> None:
        while not self._stop_event.is_set() or not self.q.empty():
            try:
                item = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                with self.lock:
                    with self.fpath.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                self._trim_if_needed()
            except Exception as exc:
                self.ledger.log_event("CRITICAL", "ARE_WRITER_ERR", str(exc))
            finally:
                self.q.task_done()

    def _trim_if_needed(self) -> None:
        with self.lock:
            try:
                lines = self.fpath.read_text(encoding="utf-8").splitlines()
                if len(lines) > self.max_lines:
                    trimmed_content = "\n".join(lines[-self.max_lines:]) + "\n"
                    with tempfile.NamedTemporaryFile("w", delete=False, dir=self.fpath.parent, suffix=".tmp", encoding="utf-8") as temp_f:
                        temp_f.write(trimmed_content)
                        temp_f.flush()
                        os.fsync(temp_f.fileno())
                        temp_name = temp_f.name
                    os.replace(temp_name, self.fpath)
            except Exception as exc:
                self.ledger.log_event("CRITICAL", "ARE_DISK", f"Atomic trim failure: {exc}")

    def ingest(self, capsule_id: str, clean_text: str, metrics: dict, node_name: str, source_ts_ns: int, received_ts_ns: int) -> None:
        self.q.put(
            {
                "source_ts_ns": source_ts_ns,
                "received_ts_ns": received_ts_ns,
                "latency_ms": round((received_ts_ns - source_ts_ns) / 1_000_000, 2),
                "capsule_id": capsule_id,
                "origin": node_name,
                "metrics": metrics,
                "payload": clean_text,
            }
        )

    def recall_recent_signals(self, limit: int) -> List[Dict[str, Any]]:
        with self.lock:
            try:
                if not self.fpath.exists():
                    return []
                lines = self.fpath.read_text(encoding="utf-8").splitlines()
                return [json.loads(line) for line in lines[-limit:]]
            except Exception as exc:
                self.ledger.log_event("ERROR", "ARE_RECALL", f"Failed recall stream: {exc}")
                return []

    def shutdown(self) -> None:
        self._stop_event.set()
        try:
            self.q.join()
            self._bg_writer.join(timeout=5.0)
            self._bg_gov.join(timeout=5.0)
            if self._bg_writer.is_alive() or self._bg_gov.is_alive():
                self.ledger.log_event("WARNING", "SHUTDOWN", "ARE Store shutdown timed out with thread still alive.")
            else:
                self.ledger.log_event("INFO", "SHUTDOWN", "ARE Store drained queue and exited cleanly.")
        except Exception as exc:
            self.ledger.log_event("ERROR", "ARE_SHUTDOWN_ERR", str(exc))


# =====================================================================
# 5. KRAKEN HISTORICAL CANDLE DATASET
# =====================================================================


class KrakenCandleDataset:
    """Load Kraken OHLCV candle data from JSON or CSV, with deterministic fallback."""

    def __init__(self, filepath: Optional[Path] = None):
        self.filepath = Path(filepath) if filepath else None
        self.candles: List[Dict[str, Any]] = []
        self.source = "synthetic_fallback"
        self._load_dataset()

    def _load_dataset(self) -> None:
        if self.filepath and self.filepath.exists():
            suffix = self.filepath.suffix.lower()
            if suffix == ".json":
                self._load_json(self.filepath)
            elif suffix == ".csv":
                self._load_csv(self.filepath)
            else:
                raise ValueError(f"Unsupported Kraken candle file type: {self.filepath}")
            self.candles.sort(key=lambda c: c["timestamp_ns"])
            self.source = f"kraken_file:{self.filepath}"
            return
        self._load_synthetic_fallback()

    def _normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        ts_raw = item.get("timestamp", item.get("time", item.get("timestamp_ns")))
        ts_float = float(ts_raw)
        timestamp_ns = int(ts_float if ts_float > 10_000_000_000_000 else ts_float * 1_000_000_000)
        return {
            "timestamp_ns": timestamp_ns,
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "volume": float(item.get("volume", item.get("vwap", 0.0))),
            "pair": item.get("pair", item.get("symbol", "XBTUSD")),
            "timeframe": item.get("timeframe", "15m"),
        }

    def _load_json(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("candles", data.get("data", []))
        self.candles = [self._normalize_item(item) for item in data]

    def _load_csv(self, path: Path) -> None:
        with path.open("r", encoding="utf-8", newline="") as f:
            first = f.readline()
            f.seek(0)
            first_cells = [cell.strip().lower() for cell in first.split(",")]
            if first_cells and first_cells[0] in {"timestamp", "time", "timestamp_ns"}:
                reader = csv.DictReader(f)
                self.candles = [self._normalize_item(row) for row in reader]
                return
            candles = []
            for row in csv.reader(f):
                if not row:
                    continue
                if len(row) < 6:
                    continue
                item = {
                    "timestamp": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                    "trades": row[6] if len(row) > 6 else 0,
                    "pair": path.name.split("_", 1)[0],
                    "timeframe": path.stem.rsplit("_", 1)[-1],
                }
                candles.append(self._normalize_item(item))
            self.candles = candles

    def _load_synthetic_fallback(self) -> None:
        random.seed(22)
        start_ts_sec = int(time.time()) - (180 * 24 * 3600)
        current_p = 2000.0
        candles = []
        for i in range(220):
            start_ts_sec += 900
            drift = math.sin(i / 11.0) * 0.002
            shock = random.uniform(-0.004, 0.004)
            close_p = max(1.0, current_p * (1.0 + drift + shock))
            candles.append(
                {
                    "timestamp_ns": start_ts_sec * 1_000_000_000,
                    "open": current_p,
                    "high": max(current_p, close_p) * 1.002,
                    "low": min(current_p, close_p) * 0.998,
                    "close": close_p,
                    "volume": 1500.0 + random.randint(0, 500),
                    "pair": "XAUUSD",
                    "timeframe": "15m",
                }
            )
            current_p = close_p
        self.candles = candles


# =====================================================================
# 6. ANALOG CANDLE RECALL SEQUENCE MATCHER
# =====================================================================


class AnalogCandleRecall:
    """No-lookahead analog candle sequence matcher."""

    @staticmethod
    def find_nearest_match(current_window: List[Dict[str, Any]], historical_pool: List[Dict[str, Any]], window_size: int = 5) -> Dict[str, Any]:
        if len(current_window) < window_size or len(historical_pool) < (window_size + 6):
            return {"similarity": 0.0, "expected_movement": "HOLD", "returns": [0.0] * 5}

        curr = AnalogCandleRecall._returns(current_window[-window_size:])
        best_score = float("inf")
        best_index = -1
        for idx in range(0, len(historical_pool) - window_size - 5):
            hist_segment = historical_pool[idx : idx + window_size]
            dist = sum((c - h) ** 2 for c, h in zip(curr, AnalogCandleRecall._returns(hist_segment)))
            if dist < best_score:
                best_score = dist
                best_index = idx

        if best_index < 0:
            return {"similarity": 0.0, "expected_movement": "HOLD", "returns": [0.0] * 5}

        base_close = historical_pool[best_index + window_size - 1]["close"]
        forward_segment = historical_pool[best_index + window_size : best_index + window_size + 5]
        final_close = forward_segment[-1]["close"] if forward_segment else base_close
        forward_return = (final_close - base_close) / base_close if base_close else 0.0
        similarity = max(0.0, 1.0 - math.sqrt(best_score))
        expected = "BUY" if forward_return > 0.002 else ("SELL" if forward_return < -0.002 else "HOLD")
        highs = [c["high"] for c in forward_segment]
        lows = [c["low"] for c in forward_segment]
        return {
            "similarity": round(similarity, 4),
            "expected_movement": expected,
            "forward_return_5": round(forward_return, 5),
            "max_favorable_excursion": round((max(highs) - base_close) / base_close, 5) if highs and base_close else 0.0,
            "max_adverse_excursion": round((min(lows) - base_close) / base_close, 5) if lows and base_close else 0.0,
        }

    @staticmethod
    def _returns(window: List[Dict[str, Any]]) -> List[float]:
        out = []
        for i in range(1, len(window)):
            prev = window[i - 1]["close"]
            out.append((window[i]["close"] - prev) / prev if prev else 0.0)
        return out


# =====================================================================
# 7. SIGNAL ENGINE
# =====================================================================


class SignalEngine:
    """Decision gate. Provenance must pass before a signal can become actionable."""

    def __init__(self, ledger: AuditLedger, tracer: TrailLinkTracer):
        self.ledger = ledger
        self.tracer = tracer

    def evaluate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        decision_id = f"DEC-{uuid.uuid4().hex[:16].upper()}"
        capsule_id = signal.get("capsule_id", "UNKNOWN")
        current_ns = now_ns()
        decision = self._hold(decision_id, capsule_id, current_ns, "Default fallback HOLD applied.")

        if not self.tracer.verify_signal_provenance(capsule_id):
            decision["reason"] = f"PROVENANCE_FAIL: Cryptographic signature verification failed for capsule {capsule_id}"
            self._commit_decision(decision)
            return decision

        source_ts = int(signal.get("source_ts_ns", 0) or 0)
        age_ms = (current_ns - source_ts) / 1_000_000.0 if source_ts > 0 else float("inf")
        if age_ms > MAX_STALE_AGE_MS:
            decision["reason"] = f"STALE_SIGNAL_REJECT: Age is {age_ms:.2f}ms, maximum is {MAX_STALE_AGE_MS}ms."
            decision["is_stale"] = True
            self._commit_decision(decision)
            return decision

        payload = signal.get("payload", "").upper()
        asset = "XAUUSD"
        if "CRUDE" in payload or "OIL" in payload:
            asset = "USOUSD"
        elif "CPI" in payload or "INFLATION" in payload:
            asset = "EURUSD"
        elif "SPY" in payload:
            asset = "SPY"
        elif "XBT" in payload or "BITCOIN" in payload:
            asset = "XBTUSD"

        metrics = signal.get("metrics", {})
        confidence = float(metrics.get("confidence", 0.0))
        direction = "HOLD"
        reason = "Default passive market monitoring state."
        is_actionable = False
        if confidence >= 0.65:
            if any(k in payload for k in ["SURGES", "SPIKES", "COOLER", "APPROVED", "BUY"]):
                direction = "BUY"
                reason = "Bullish keyword trigger identified."
                is_actionable = True
            elif any(k in payload for k in ["STALL", "BAN", "RESTRICTIONS", "SELL"]):
                direction = "SELL"
                reason = "Bearish keyword trigger identified."
                is_actionable = True

        if is_actionable and self.ledger.has_duplicate_action(capsule_id, asset, direction):
            decision["reason"] = f"DUPLICATE_CAPSULE_REJECT: Capsule {capsule_id} already executed {direction} on {asset}."
            self._commit_decision(decision)
            return decision

        decision.update(
            {
                "asset": asset,
                "direction": direction,
                "confidence": confidence,
                "reason": reason,
                "is_actionable": is_actionable,
            }
        )
        self._commit_decision(decision)
        return decision

    @staticmethod
    def _hold(decision_id: str, capsule_id: str, timestamp_ns: int, reason: str) -> Dict[str, Any]:
        return {
            "decision_id": decision_id,
            "capsule_id": capsule_id,
            "timestamp_ns": timestamp_ns,
            "asset": "XAUUSD",
            "direction": "HOLD",
            "confidence": 0.0,
            "reason": reason,
            "is_stale": False,
            "is_actionable": False,
            "strategy_name": STRATEGY_NAME,
            "strategy_version": STRATEGY_VERSION,
            "parameters_hash": STRATEGY_PARAMS_HASH,
        }

    def _commit_decision(self, dec: Dict[str, Any]) -> None:
        try:
            with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO signal_decisions
                    (decision_id, capsule_id, timestamp_ns, asset, direction, confidence, reason,
                     is_actionable, strategy_name, strategy_version, parameters_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dec["decision_id"],
                        dec["capsule_id"],
                        dec["timestamp_ns"],
                        dec["asset"],
                        dec["direction"],
                        dec["confidence"],
                        dec["reason"],
                        int(dec["is_actionable"]),
                        dec["strategy_name"],
                        dec["strategy_version"],
                        dec["parameters_hash"],
                    ),
                )
                conn.commit()
        except Exception as exc:
            self.ledger.log_event("ERROR", "DB_DECISION_ERR", str(exc))


# =====================================================================
# 8. RISK GOVERNOR
# =====================================================================


class RiskGovernor:
    """Enforces risk constraints, loss limits, duplicate action blocks, and emergency switches."""

    def __init__(self, ledger: AuditLedger, limits: Dict[str, Any]):
        self.ledger = ledger
        self.limits = limits
        self._kill_switch_active = False
        self.last_loss_timestamp_ns = 0

    def trigger_emergency_kill_switch(self) -> None:
        self._kill_switch_active = True
        self.ledger.log_event("CRITICAL", "RISK_SHUTDOWN", "Emergency kill switch active.")

    def reset_kill_switch(self) -> None:
        self._kill_switch_active = False

    def is_kill_switch_file_present(self) -> bool:
        return KILL_SWITCH_FILE.exists()

    def check_order_intent(self, decision: Dict[str, Any], current_portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
        check_id = f"CHK-{uuid.uuid4().hex[:16].upper()}"
        current_ns = now_ns()
        asset = decision.get("asset", "")
        direction = decision.get("direction", "HOLD")
        qty = float(decision.get("quantity", DEFAULT_ORDER_QTY))
        market_prices = current_portfolio_state.get("market_prices", {})
        price_obj = market_prices.get(asset)
        market_price = extract_price(price_obj)
        notional = abs(qty * market_price)
        positions = current_portfolio_state.get("positions", {})
        pos = positions.get(asset, {"qty": 0.0, "avg_price": 0.0})
        current_qty = float(pos.get("qty", 0.0)) if isinstance(pos, dict) else float(pos or 0.0)
        projected_qty = current_qty + (qty if direction == "BUY" else -qty if direction == "SELL" else 0.0)
        current_exposure = float(current_portfolio_state.get("notional_exposure", 0.0))
        projected_exposure = current_exposure + notional if direction == "BUY" else max(0.0, current_exposure - notional)

        risk_snapshot = {
            "limits": self.limits.copy(),
            "kill_switch_file_present": self.is_kill_switch_file_present(),
            "kill_switch_active": self._kill_switch_active,
            "asset": asset,
            "direction": direction,
            "quantity": qty,
            "market_price": market_price,
            "notional": notional,
            "current_qty": current_qty,
            "projected_qty": projected_qty,
            "current_exposure": current_exposure,
            "projected_exposure": projected_exposure,
            "portfolio": current_portfolio_state.copy(),
        }

        if self._kill_switch_active or self.is_kill_switch_file_present():
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "EMERGENCY_KILL_SWITCH_ACTIVE", risk_snapshot)

        if not decision.get("is_actionable") or direction == "HOLD":
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "NON_ACTIONABLE_SIGNAL_REJECTION", risk_snapshot)

        if asset not in TRADEABLE_ASSETS:
            return self._record_check(check_id, decision["decision_id"], current_ns, False, f"UNSUPPORTED_ASSET: {asset}", risk_snapshot)

        if self.last_loss_timestamp_ns > 0 and (current_ns - self.last_loss_timestamp_ns) < int(self.limits.get("loss_cooldown_ns", 10_000_000_000)):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "LOSS_COOLDOWN_ACTIVE", risk_snapshot)

        decision_age_ms = (current_ns - int(decision.get("timestamp_ns", 0))) / 1_000_000.0
        if decision_age_ms > float(self.limits.get("max_signal_age_ms", MAX_STALE_AGE_MS)):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "STALE_SIGNAL_REJECTION", risk_snapshot)

        if not is_market_price_fresh(price_obj, current_ns):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "STALE_MARKET_PRICE_REJECTION", risk_snapshot)

        if market_price <= 0.0:
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "INVALID_MARKET_PRICE", risk_snapshot)

        if direction == "SELL" and not self.limits.get("allow_short_selling", False) and current_qty < qty:
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "SHORT_SELLING_DISABLED", risk_snapshot)

        if abs(projected_qty) > float(self.limits["max_position_size"]):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "EXCEEDED_MAX_POSITION_SIZE", risk_snapshot)

        if notional > float(self.limits.get("max_order_notional", float("inf"))):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "EXCEEDED_MAX_ORDER_NOTIONAL", risk_snapshot)

        if projected_exposure > float(self.limits["max_notional_exposure"]):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "EXCEEDED_MAX_NOTIONAL_EXPOSURE", risk_snapshot)

        if float(current_portfolio_state.get("daily_loss", 0.0)) >= float(self.limits["max_daily_loss"]):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "EXCEEDED_MAX_DAILY_LOSS_LIMIT", risk_snapshot)

        if int(current_portfolio_state.get("open_orders_count", 0)) >= int(self.limits["max_open_orders"]):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "EXCEEDED_MAX_OPEN_ORDERS_LIMIT", risk_snapshot)

        if int(current_portfolio_state.get("trades_last_hour", 0)) >= int(self.limits["max_trades_per_hour"]):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "EXCEEDED_MAX_TRADES_PER_HOUR", risk_snapshot)

        if self.ledger.has_duplicate_action(decision["capsule_id"], asset, direction):
            return self._record_check(check_id, decision["decision_id"], current_ns, False, "DUPLICATE_ACTION_REJECTION", risk_snapshot)

        return self._record_check(check_id, decision["decision_id"], current_ns, True, "APPROVED_BY_RISK_CONTROL", risk_snapshot)

    def _record_check(self, check_id: str, decision_id: str, ts_ns: int, approved: bool, reason: str, snapshot: dict) -> Dict[str, Any]:
        try:
            with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO risk_checks
                    (check_id, decision_id, timestamp_ns, approved, reason, snapshot_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (check_id, decision_id, ts_ns, int(approved), reason, json.dumps(snapshot, default=str)),
                )
                conn.commit()
        except Exception as exc:
            self.ledger.log_event("ERROR", "RISK_CHECK_LOG_ERR", str(exc))
        return {"approved": approved, "reason": reason, "risk_snapshot": snapshot}


# =====================================================================
# 9. BROKERS
# =====================================================================


class PaperBroker:
    """Paper broker with long-only accounting, fees, slippage, and no negative cash."""

    def __init__(self, ledger: AuditLedger, initial_balance: float = INITIAL_BALANCE):
        self.ledger = ledger
        self.initial_balance = float(initial_balance)
        self.cash = float(initial_balance)
        self.positions: Dict[str, Dict[str, float]] = {asset: {"qty": 0.0, "avg_price": 0.0} for asset in TRADEABLE_ASSETS}
        self.realized_pnl = 0.0
        self.fees_paid = 0.0
        self.slippage_paid = 0.0
        self.slippage_pct = 0.0002
        self.commission_fee = 1.00
        self.trade_timestamps: List[int] = []
        self.daily_realized_pnl = 0.0
        self.lock = threading.Lock()

    def get_portfolio_state(self, current_prices: Dict[str, Any], open_orders_count: int) -> Dict[str, Any]:
        with self.lock:
            unrealized_pnl = 0.0
            notional_exposure = 0.0
            positions_copy = json.loads(json.dumps(self.positions))
            for asset, pos in self.positions.items():
                qty = pos["qty"]
                if qty:
                    mark = extract_price(current_prices.get(asset, pos["avg_price"]))
                    unrealized_pnl += (mark - pos["avg_price"]) * qty
                    notional_exposure += abs(mark * qty)
            equity = self.cash + notional_exposure
            daily_loss = max(0.0, -self.daily_realized_pnl)
            cutoff = now_ns() - 3_600_000_000_000
            trades_last_hour = len([ts for ts in self.trade_timestamps if ts >= cutoff])
            return {
                "balance": self.cash,
                "cash": self.cash,
                "equity": equity,
                "positions": positions_copy,
                "daily_loss": daily_loss,
                "open_orders_count": open_orders_count,
                "realized_pnl": self.realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "notional_exposure": notional_exposure,
                "trades_last_hour": trades_last_hour,
                "market_prices": current_prices,
                "fees_paid": self.fees_paid,
                "slippage_paid": self.slippage_paid,
            }

    def execute_paper_fill(self, order_id: str, asset: str, direction: str, qty: float, price_record: Any) -> Dict[str, Any]:
        with self.lock:
            if not is_market_price_fresh(price_record):
                return {"success": False, "reason": "STALE_MARKET_PRICE_REJECTION"}
            market_price = extract_price(price_record)
            if market_price <= 0.0 or qty <= 0.0:
                return {"success": False, "reason": "INVALID_ORDER_INPUT"}
            fill_id = f"FIL-{uuid.uuid4().hex[:16].upper()}"
            ts_ns = now_ns()
            slippage_mult = (1.0 + self.slippage_pct) if direction == "BUY" else (1.0 - self.slippage_pct)
            fill_price = market_price * slippage_mult
            slippage_cost = abs(fill_price - market_price) * qty
            fee = self.commission_fee
            gross = fill_price * qty
            pos = self.positions.setdefault(asset, {"qty": 0.0, "avg_price": 0.0})

            if direction == "BUY":
                total_debit = gross + fee
                if self.cash < total_debit:
                    return {"success": False, "reason": "INSUFFICIENT_CASH_NO_MARGIN"}
                new_qty = pos["qty"] + qty
                pos["avg_price"] = ((pos["qty"] * pos["avg_price"]) + gross) / new_qty
                pos["qty"] = new_qty
                self.cash -= total_debit
                realized = 0.0
            elif direction == "SELL":
                if pos["qty"] < qty:
                    return {"success": False, "reason": "SHORT_SELLING_DISABLED"}
                realized = (fill_price - pos["avg_price"]) * qty - fee
                pos["qty"] -= qty
                if pos["qty"] <= 1e-12:
                    pos["qty"] = 0.0
                    pos["avg_price"] = 0.0
                self.cash += gross - fee
                self.realized_pnl += realized
                self.daily_realized_pnl += realized
            else:
                return {"success": False, "reason": "UNSUPPORTED_DIRECTION"}

            self.fees_paid += fee
            self.slippage_paid += slippage_cost
            self.trade_timestamps.append(ts_ns)
            with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO execution_fills
                    (fill_id, order_id, timestamp_ns, quantity, price, slippage, fee)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (fill_id, order_id, ts_ns, qty, fill_price, slippage_cost, fee),
                )
                conn.commit()
            return {
                "success": True,
                "fill_id": fill_id,
                "fill_price": fill_price,
                "slippage_cost": slippage_cost,
                "fee": fee,
                "realized_pnl": realized,
                "cash": self.cash,
            }


class LiveBrokerDryRun:
    """Builds and audits a live order payload but sends nothing."""

    def __init__(self, ledger: AuditLedger):
        self.ledger = ledger
        self.sent_payloads: List[Dict[str, Any]] = []

    def submit_order(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "exchange": "kraken",
            "pair": intent["asset"],
            "type": "buy" if intent["direction"] == "BUY" else "sell",
            "ordertype": "limit",
            "volume": intent["quantity"],
            "price": intent["price"],
            "validate": True,
            "client_order_id": intent["idempotency_key"],
        }
        event_id = f"LEV-{uuid.uuid4().hex[:16].upper()}"
        with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
            conn.execute(
                """
                INSERT INTO live_order_events
                (event_id, order_id, timestamp_ns, event_type, event_payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, intent["intent_id"], now_ns(), "DRY_RUN_PAYLOAD_BUILT", json.dumps(payload)),
            )
            conn.commit()
        self.sent_payloads.append(payload)
        return {"success": True, "sent": False, "payload": payload}


class LiveBrokerStub:
    """Fail-closed placeholder. Real live execution is intentionally absent."""

    def submit_order(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("LIVE_EXCHANGE_EXECUTION_NOT_IMPLEMENTED_FAIL_CLOSED")


class BrokerRouter:
    """Routes orders to paper, dry-run, or fail-closed live broker."""

    def __init__(self, mode: str, ledger: AuditLedger, paper_broker: PaperBroker):
        self.mode = mode
        self.ledger = ledger
        self.paper_broker = paper_broker
        self.live_dry_run = LiveBrokerDryRun(ledger)
        self.live_stub = LiveBrokerStub()

    def broker_for_mode(self) -> Any:
        if self.mode in {"paper", "backtest"}:
            return self.paper_broker
        if self.mode == "live_dry_run":
            return self.live_dry_run
        if self.mode == "live":
            gates = LiveTradingGate.validate(interactive=False)
            if not gates["approved"]:
                raise RuntimeError(f"LIVE_MODE_FAIL_CLOSED: {gates['reason']}")
            return self.live_stub
        raise RuntimeError(f"UNSUPPORTED_TRADING_MODE: {self.mode}")


class LiveTradingGate:
    """Strict live gate validation. Real live execution still fails closed."""

    REQUIRED_ENV = ["KRAKEN_API_KEY", "KRAKEN_API_SECRET"]

    @staticmethod
    def validate(interactive: bool = True) -> Dict[str, Any]:
        reasons = []
        if TRADING_MODE != "live":
            reasons.append("VERITAS_TRADING_MODE is not live")
        if not ENABLE_LIVE_TRADING:
            reasons.append("VERITAS_ENABLE_LIVE_TRADING is not true")
        if not LIVE_PASSPHRASE_HASH:
            reasons.append("VERITAS_LIVE_PASSPHRASE_HASH missing")
        for file_path in [VERITAS_TEST_PASSED_FILE, VERITAS_PAPER_BURN_IN_FILE, BACKTEST_REPORT_FILE]:
            if not is_fresh_json_file(file_path):
                reasons.append(f"{file_path} missing or stale")
        for env_name in LiveTradingGate.REQUIRED_ENV:
            if not os.environ.get(env_name):
                reasons.append(f"{env_name} missing")
        if KILL_SWITCH_FILE.exists():
            reasons.append("VERITAS_KILL_SWITCH file present")
        if not all(
            [
                MICRO_LIVE_LIMITS["max_order_notional"] <= 10.0,
                MICRO_LIVE_LIMITS["max_daily_loss"] <= 25.0,
                MICRO_LIVE_LIMITS["max_open_orders"] <= 1,
                MICRO_LIVE_LIMITS["max_trades_per_day"] <= 3,
                not MICRO_LIVE_LIMITS["allow_leverage"],
                not MICRO_LIVE_LIMITS["allow_margin"],
                not MICRO_LIVE_LIMITS["allow_short_selling"],
                not MICRO_LIVE_LIMITS["allow_market_orders"],
            ]
        ):
            reasons.append("micro-live limits inactive")
        if reasons:
            return {"approved": False, "reason": "; ".join(reasons)}
        if interactive:
            entered = getpass.getpass("VERITAS live passphrase: ")
            entered_hash = hashlib.sha256(entered.encode("utf-8")).hexdigest()
            if not hmac.compare_digest(entered_hash, LIVE_PASSPHRASE_HASH):
                return {"approved": False, "reason": "live passphrase mismatch"}
            typed = input("Type exact confirmation: ")
            if typed != "I ACCEPT LIVE TRADING RISK":
                return {"approved": False, "reason": "typed live confirmation mismatch"}
        return {"approved": False, "reason": "all gates passed but LiveBrokerStub is not implemented; live execution fails closed"}


# =====================================================================
# 10. ORDER MANAGER
# =====================================================================


class OrderManager:
    """Order state machine with stable idempotency keys."""

    def __init__(self, ledger: AuditLedger, broker_router: BrokerRouter):
        self.ledger = ledger
        self.broker_router = broker_router
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.processed_idempotency_keys = set()
        self.lock = threading.Lock()

    def process_approved_intent(self, decision: Dict[str, Any], price_record: Dict[str, Any]) -> Optional[str]:
        idempotency_key = stable_action_key(decision["capsule_id"], decision["asset"], decision["direction"], decision["strategy_version"])
        with self.lock:
            if idempotency_key in self.processed_idempotency_keys:
                self.ledger.log_event("WARNING", "ORDER_MANAGER", f"Idempotency token already recorded: {idempotency_key}")
                return None
            self.processed_idempotency_keys.add(idempotency_key)
            intent_id = f"INT-{uuid.uuid4().hex[:16].upper()}"
            order_id = f"ORD-{uuid.uuid4().hex[:16].upper()}"
            ts_ns = now_ns()
            asset = decision["asset"]
            direction = decision["direction"]
            qty = float(decision.get("quantity", DEFAULT_ORDER_QTY))
            price = extract_price(price_record)
            with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO order_intents
                    (intent_id, decision_id, idempotency_key, timestamp_ns, asset, direction, quantity, price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (intent_id, decision["decision_id"], idempotency_key, ts_ns, asset, direction, qty, price),
                )
                if self.broker_router.mode in {"paper", "backtest"}:
                    conn.execute(
                        """
                        INSERT INTO paper_orders
                        (order_id, intent_id, state, asset, direction, quantity, price, filled_qty, avg_fill_price, updated_ts_ns)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (order_id, intent_id, "OPEN", asset, direction, qty, price, 0.0, 0.0, ts_ns),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO live_orders
                        (order_id, intent_id, state, asset, direction, quantity, price, filled_qty, avg_fill_price, broker_order_ref, updated_ts_ns)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (order_id, intent_id, "DRY_RUN" if self.broker_router.mode == "live_dry_run" else "REJECTED", asset, direction, qty, price, 0.0, 0.0, None, ts_ns),
                    )
                conn.commit()

            order_payload = {
                "order_id": order_id,
                "intent_id": intent_id,
                "state": "OPEN",
                "asset": asset,
                "direction": direction,
                "quantity": qty,
                "price": price,
                "price_record": price_record,
                "idempotency_key": idempotency_key,
            }
            self.active_orders[order_id] = order_payload

            if self.broker_router.mode == "live_dry_run":
                self.broker_router.live_dry_run.submit_order(order_payload)
                self.ledger.register_signal_action(decision["capsule_id"], asset, direction)
                return order_id
            if self.broker_router.mode == "live":
                self.broker_router.live_stub.submit_order(order_payload)
            return order_id

    def execute_matching_engine(self, current_market_prices: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        fills = []
        with self.lock:
            for oid, order in list(self.active_orders.items()):
                if order["state"] not in ("PENDING", "OPEN"):
                    continue
                price_record = current_market_prices.get(order["asset"])
                result = self.broker_router.paper_broker.execute_paper_fill(
                    oid, order["asset"], order["direction"], order["quantity"], price_record
                )
                ts_ns = now_ns()
                if result.get("success"):
                    order["state"] = "FILLED"
                    order["filled_qty"] = order["quantity"]
                    order["avg_fill_price"] = result["fill_price"]
                    with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
                        conn.execute(
                            """
                            UPDATE paper_orders
                            SET state = ?, filled_qty = ?, avg_fill_price = ?, updated_ts_ns = ?
                            WHERE order_id = ?
                            """,
                            ("FILLED", order["quantity"], result["fill_price"], ts_ns, oid),
                        )
                        conn.commit()
                    fills.append({"order_id": oid, **result})
                else:
                    order["state"] = "REJECTED"
                    with self.ledger.lock, sqlite3.connect(self.ledger.db_path) as conn:
                        conn.execute(
                            "UPDATE paper_orders SET state = ?, updated_ts_ns = ? WHERE order_id = ?",
                            ("REJECTED", ts_ns, oid),
                        )
                        conn.commit()
                    fills.append({"order_id": oid, **result})
        return fills


# =====================================================================
# 11. SIMULATED DATA NODE
# =====================================================================


class SimulatedNewsNode(threading.Thread):
    """SIMULATED DATA ONLY — NOT LIVE MARKET DATA."""

    def __init__(self, node_id: int, category: str, input_queue: "queue.Queue[Tuple[str, str, int]]"):
        super().__init__(daemon=True)
        self.node_id = node_id
        self.node_name = f"SimNode-{self.node_id:02d}-{category}"
        self.category = category
        self.input_queue = input_queue
        self._running = True

    def stop(self) -> None:
        self._running = False

    def simulate_event(self) -> str:
        events = {
            "COMMODITIES": [
                "SIMULATED DATA ONLY: CRUDE OIL spikes as supply restrictions appear in scenario feed.",
                "SIMULATED DATA ONLY: GOLD surges as safe-haven scenario flow increases.",
            ],
            "REGULATORY": [
                "SIMULATED DATA ONLY: SEC scenario says alternative asset custody structures approved.",
                "SIMULATED DATA ONLY: FED scenario shows rate cycle holding steady.",
            ],
            "MACRO_ECONOMIC": [
                "SIMULATED DATA ONLY: CPI scenario comes in cooler than expected.",
                "SIMULATED DATA ONLY: Global shipping scenario shows routing disruption.",
            ],
        }
        return random.choice(events.get(self.category, ["SIMULATED DATA ONLY: Quiet range observed."]))

    def run(self) -> None:
        while self._running:
            try:
                time.sleep(random.uniform(0.5, 1.2))
                self.input_queue.put((self.node_name, self.simulate_event(), now_ns()))
            except Exception as exc:
                sys.stderr.write(f"SimulatedNewsNode error: {exc}\n")


# =====================================================================
# 12. BACKTEST
# =====================================================================


class BacktestRunner:
    def __init__(self, engine: "VeritasEngine", dataset: KrakenCandleDataset):
        self.engine = engine
        self.dataset = dataset
        self.decisions: List[Dict[str, Any]] = []
        self.risk_checks: List[Dict[str, Any]] = []
        self.fills: List[Dict[str, Any]] = []
        self.rejected_trades = 0
        self.hold_decisions = 0
        self.daily_loss_violations = 0
        self.equity_curve: List[float] = []
        self.trade_pnls: List[float] = []

    def run(self) -> Dict[str, Any]:
        candles = self.dataset.candles
        if len(candles) < 10:
            raise RuntimeError("BACKTEST_REQUIRES_AT_LEAST_10_CANDLES")
        for idx, candle in enumerate(candles):
            asset = candle.get("pair", "XAUUSD")
            if asset not in TRADEABLE_ASSETS:
                asset = "XAUUSD"
            self.engine.current_market_prices[asset] = market_price_record(
                candle["close"], self.dataset.source, timestamp_ns=now_ns(), max_age_ms=60_000
            )
            if idx < 6:
                self._record_equity()
                continue
            current_window = candles[max(0, idx - 5) : idx + 1]
            historical_pool = candles[: max(0, idx - 1)]
            outcome = AnalogCandleRecall.find_nearest_match(current_window, historical_pool, window_size=5)
            signal_text = f"KRAKEN BACKTEST CANDLE ANALOG: {asset} {outcome['expected_movement']} similarity {outcome['similarity']}"
            if outcome["expected_movement"] == "BUY":
                signal_text += " BUY surges"
            elif outcome["expected_movement"] == "SELL":
                signal_text += " SELL restrictions"
            else:
                signal_text += " HOLD"
            source_ts = now_ns()
            signal = self.engine.ingest_signal("KrakenBacktestNode", signal_text, source_ts, block=True)
            decision = self.engine.signal_engine.evaluate_signal(signal)
            decision["asset"] = asset
            self.decisions.append(decision)
            if decision["direction"] == "HOLD":
                self.hold_decisions += 1
            risk = self.engine.evaluate_single_decision(decision)
            self.risk_checks.append(risk)
            if not risk["approved"]:
                self.rejected_trades += 1
                if risk["reason"] == "EXCEEDED_MAX_DAILY_LOSS_LIMIT":
                    self.daily_loss_violations += 1
            fills = self.engine.order_manager.execute_matching_engine(self.engine.current_market_prices)
            for fill in fills:
                self.fills.append(fill)
                if fill.get("success") and "realized_pnl" in fill:
                    self.trade_pnls.append(float(fill["realized_pnl"]))
            self._record_equity()
        report = self._build_report()
        with BACKTEST_REPORT_FILE.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        self.engine.ledger.log_event("INFO", "BACKTEST", f"Backtest report saved to {BACKTEST_REPORT_FILE}")
        return report

    def _record_equity(self) -> None:
        open_count = len([o for o in self.engine.order_manager.active_orders.values() if o["state"] in ("PENDING", "OPEN")])
        state = self.engine.broker.get_portfolio_state(self.engine.current_market_prices, open_count)
        self.equity_curve.append(float(state["equity"]))

    def _build_report(self) -> Dict[str, Any]:
        ending = self.equity_curve[-1] if self.equity_curve else self.engine.broker.initial_balance
        wins = [p for p in self.trade_pnls if p > 0]
        losses = [p for p in self.trade_pnls if p < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        max_drawdown = 0.0
        peak = self.equity_curve[0] if self.equity_curve else self.engine.broker.initial_balance
        for equity in self.equity_curve:
            peak = max(peak, equity)
            if peak:
                max_drawdown = max(max_drawdown, (peak - equity) / peak)
        max_consec_losses = 0
        cur = 0
        for pnl in self.trade_pnls:
            if pnl < 0:
                cur += 1
                max_consec_losses = max(max_consec_losses, cur)
            else:
                cur = 0
        return {
            "data_source": self.dataset.source,
            "starting_balance": self.engine.broker.initial_balance,
            "ending_equity": ending,
            "total_return": (ending - self.engine.broker.initial_balance) / self.engine.broker.initial_balance,
            "max_drawdown": max_drawdown,
            "win_rate": len(wins) / len(self.trade_pnls) if self.trade_pnls else 0.0,
            "average_win": sum(wins) / len(wins) if wins else 0.0,
            "average_loss": sum(losses) / len(losses) if losses else 0.0,
            "profit_factor": gross_win / gross_loss if gross_loss else (gross_win if gross_win else 0.0),
            "number_of_trades": len(self.trade_pnls),
            "max_consecutive_losses": max_consec_losses,
            "fees_paid": self.engine.broker.fees_paid,
            "slippage_paid": self.engine.broker.slippage_paid,
            "largest_single_loss": min(losses) if losses else 0.0,
            "daily_loss_violations": self.daily_loss_violations,
            "rejected_trades": self.rejected_trades,
            "HOLD_decisions": self.hold_decisions,
            "decisions_recorded": len(self.decisions),
            "risk_checks_recorded": len(self.risk_checks),
            "fills_recorded": len(self.fills),
        }


# =====================================================================
# 13. MASTER SYSTEM INTEGRATOR
# =====================================================================


class VeritasEngine:
    def __init__(self, db_path: Path = DB_PATH, mode: str = TRADING_MODE):
        self.mode = mode if mode in SUPPORTED_MODES else "paper"
        print_banner()
        self.ledger = AuditLedger(db_path)
        self.tracer = TrailLinkTracer(self.ledger, SECRET_INTEGRITY_KEY)
        self.base_dir = Path(__file__).resolve().parent
        self.are_file = self.base_dir / "are_data" / "are_mem_live.jsonl"
        self.are = AREStore(self.are_file, self.ledger)
        self.signal_engine = SignalEngine(self.ledger, self.tracer)
        if self.mode == "live":
            risk_limits = MICRO_LIVE_LIMITS.copy()
        else:
            risk_limits = {
                "max_position_size": 50.0,
                "max_order_notional": 10_000.0,
                "max_notional_exposure": 100_000.0,
                "max_daily_loss": 5_000.0,
                "max_open_orders": 5,
                "max_trades_per_hour": 60,
                "max_signal_age_ms": MAX_STALE_AGE_MS,
                "allow_short_selling": False,
                "loss_cooldown_ns": 10_000_000_000,
            }
        self.risk_governor = RiskGovernor(self.ledger, risk_limits)
        self.broker = PaperBroker(self.ledger)
        self.broker_router = BrokerRouter(self.mode, self.ledger, self.broker)
        self.order_manager = OrderManager(self.ledger, self.broker_router)
        self.raw_ingest_queue: "queue.Queue[Tuple[str, str, int]]" = queue.Queue()
        self.simulated_nodes: List[SimulatedNewsNode] = []
        self._running = False
        self.processor_thread: Optional[threading.Thread] = None
        self.current_market_prices: Dict[str, Dict[str, Any]] = {
            "XAUUSD": market_price_record(2000.0, "SIMULATED DATA ONLY — NOT LIVE MARKET DATA"),
            "USOUSD": market_price_record(80.0, "SIMULATED DATA ONLY — NOT LIVE MARKET DATA"),
            "EURUSD": market_price_record(1.10, "SIMULATED DATA ONLY — NOT LIVE MARKET DATA"),
            "SPY": market_price_record(500.0, "SIMULATED DATA ONLY — NOT LIVE MARKET DATA"),
            "XBTUSD": market_price_record(65000.0, "SIMULATED DATA ONLY — NOT LIVE MARKET DATA"),
        }

    def start_engine(self) -> None:
        if self.mode == "backtest":
            return
        if self.mode == "live":
            gates = LiveTradingGate.validate(interactive=False)
            if not gates["approved"]:
                raise RuntimeError(f"LIVE_MODE_FAIL_CLOSED: {gates['reason']}")
        self._running = True
        for nid, cat in [(1, "COMMODITIES"), (2, "REGULATORY"), (3, "MACRO_ECONOMIC")]:
            node = SimulatedNewsNode(nid, cat, self.raw_ingest_queue)
            self.simulated_nodes.append(node)
            node.start()
        self.processor_thread = threading.Thread(target=self._master_ingestion_loop, daemon=True)
        self.processor_thread.start()

    def ingest_signal(self, node_name: str, raw_blob: str, source_ts_ns: int, block: bool = False) -> Dict[str, Any]:
        received_ts_ns = now_ns()
        clean_payload = VeritasParser.clean_digital_lint(raw_blob)
        metrics = VeritasParser.extract_metrics(clean_payload)
        capsule_id, _ = self.tracer.register_raw_signal(node_name, raw_blob, received_ts_ns=received_ts_ns)
        self.tracer.register_clean_signal(capsule_id, clean_payload, metrics["entropy"], metrics["confidence"], received_ts_ns=received_ts_ns)
        self.are.ingest(capsule_id, clean_payload, metrics, node_name, source_ts_ns, received_ts_ns)
        if block:
            self.are.q.join()
        return {
            "source_ts_ns": source_ts_ns,
            "received_ts_ns": received_ts_ns,
            "latency_ms": round((received_ts_ns - source_ts_ns) / 1_000_000, 2),
            "capsule_id": capsule_id,
            "origin": node_name,
            "metrics": metrics,
            "payload": clean_payload,
        }

    def _master_ingestion_loop(self) -> None:
        while self._running:
            try:
                node_name, raw_blob, source_ts_ns = self.raw_ingest_queue.get(timeout=0.2)
                self.ingest_signal(node_name, raw_blob, source_ts_ns)
                self.raw_ingest_queue.task_done()
            except queue.Empty:
                continue
            except Exception as exc:
                self.ledger.log_event("ERROR", "PROCESSOR_LOOP", str(exc))

    def evaluate_single_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        asset = decision["asset"]
        price_record = self.current_market_prices.get(asset)
        open_count = len([o for o in self.order_manager.active_orders.values() if o["state"] in ("PENDING", "OPEN")])
        portfolio = self.broker.get_portfolio_state(self.current_market_prices, open_count)
        risk = self.risk_governor.check_order_intent(decision, portfolio)
        if risk["approved"]:
            order_id = self.order_manager.process_approved_intent(decision, price_record)
            if order_id:
                self.ledger.register_signal_action(decision["capsule_id"], asset, decision["direction"])
        return risk

    def evaluate_and_route_trades(self) -> List[Dict[str, Any]]:
        results = []
        recent_signals = self.are.recall_recent_signals(limit=5)
        for sig in recent_signals:
            decision = self.signal_engine.evaluate_signal(sig)
            results.append(self.evaluate_single_decision(decision))
        self.order_manager.execute_matching_engine(self.current_market_prices)
        return results

    def get_market_intelligence_report(self, limit: int = 10) -> Dict[str, Any]:
        open_count = len([o for o in self.order_manager.active_orders.values() if o["state"] in ("PENDING", "OPEN")])
        state = self.broker.get_portfolio_state(self.current_market_prices, open_count)
        return {
            "data_honesty": "SIMULATED DATA ONLY — NOT LIVE MARKET DATA" if self.mode != "backtest" else "HISTORICAL KRAKEN CANDLES — BACKTEST MODE",
            "telemetry": {
                "system_mode": self.mode,
                "available_ram_mb": round(self.are._get_avail_kb() / 1024, 2),
                "active_threads": threading.active_count(),
                "portfolio": state,
            },
            "signals": self.are.recall_recent_signals(limit),
        }

    def run_backtest(self) -> Dict[str, Any]:
        path_raw = os.environ.get("VERITAS_KRAKEN_CANDLE_PATH", "")
        dataset = KrakenCandleDataset(Path(path_raw) if path_raw else None)
        runner = BacktestRunner(self, dataset)
        return runner.run()

    def shutdown(self) -> None:
        self._running = False
        for node in self.simulated_nodes:
            node.stop()
        if self.processor_thread:
            self.processor_thread.join(timeout=2.0)
        self.are.shutdown()
        self.ledger.log_event("INFO", "SHUTDOWN", "VERITAS subsystem shutdown completed.")
        print("[VERITAS INTEGRATOR] Subsystem shutdown completed successfully.")


def run_paper_demo() -> None:
    engine = VeritasEngine()
    engine.start_engine()
    try:
        for step in range(3):
            time.sleep(1.0)
            engine.evaluate_and_route_trades()
            rep = engine.get_market_intelligence_report()
            portfolio = rep["telemetry"]["portfolio"]
            print(
                f"[{step + 1}/3] SIMULATED DATA ONLY — NOT LIVE MARKET DATA | "
                f"Equity: {portfolio['equity']:.2f} | Realized PnL: {portfolio['realized_pnl']:.2f}"
            )
    finally:
        engine.shutdown()


def run_backtest_main() -> None:
    engine = VeritasEngine(mode="backtest")
    try:
        report = engine.run_backtest()
        print("Backtest complete. Report saved to .veritas_backtest_report.json")
        print(json.dumps({k: report[k] for k in ["starting_balance", "ending_equity", "total_return", "number_of_trades", "rejected_trades", "HOLD_decisions"]}, indent=2))
    finally:
        engine.shutdown()



def run_validation_harness() -> Dict[str, Any]:
    """Dependency-free validation harness for environments without pytest."""
    results: List[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        results.append(name)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ledger = AuditLedger(tmp / "ledger.db")
        tracer = TrailLinkTracer(ledger, b"validation-key")
        capsule, _ = tracer.register_raw_signal("test", "GOLD surges")
        tracer.register_clean_signal(capsule, "GOLD surges", 1.0, 1.0)
        check("clean_signals_insert_and_hmac_pass", tracer.verify_signal_provenance(capsule))
        with sqlite3.connect(ledger.db_path) as conn:
            conn.execute("UPDATE clean_signals SET sanitized_payload = ? WHERE capsule_id = ?", ("GOLD altered", capsule))
            conn.commit()
        check("modified_payload_fails_hmac", not tracer.verify_signal_provenance(capsule))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        engine = VeritasEngine(db_path=tmp / "ledger.db")
        try:
            decision = {
                "decision_id": "DEC-VALIDATE",
                "capsule_id": "CAP-VALIDATE",
                "timestamp_ns": now_ns(),
                "asset": "XAUUSD",
                "direction": "BUY",
                "confidence": 1.0,
                "reason": "validation",
                "is_actionable": True,
                "strategy_name": STRATEGY_NAME,
                "strategy_version": STRATEGY_VERSION,
                "parameters_hash": STRATEGY_PARAMS_HASH,
                "quantity": 1.0,
            }
            portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
            check("risk_approval_baseline", engine.risk_governor.check_order_intent(decision, portfolio)["approved"])
            engine.ledger.register_signal_action("CAP-VALIDATE", "XAUUSD", "BUY")
            check("duplicate_action_blocks_order", engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "DUPLICATE_ACTION_REJECTION")
            stale_signal = dict(decision, decision_id="DEC-STALE", capsule_id="CAP-STALE", timestamp_ns=now_ns() - 60_000_000_000)
            check("stale_signal_blocks_order", engine.risk_governor.check_order_intent(stale_signal, portfolio)["reason"] == "STALE_SIGNAL_REJECTION")
            old_prices = {"XAUUSD": market_price_record(2000.0, "validation", timestamp_ns=now_ns() - 60_000_000_000, max_age_ms=10)}
            stale_price_portfolio = engine.broker.get_portfolio_state(old_prices, 0)
            check("stale_market_price_blocks_order", engine.risk_governor.check_order_intent(dict(decision, decision_id="DEC-PRICE", capsule_id="CAP-PRICE"), stale_price_portfolio)["reason"] == "STALE_MARKET_PRICE_REJECTION")
            engine.risk_governor.limits["max_position_size"] = 0.5
            check("max_position_blocks_order", engine.risk_governor.check_order_intent(dict(decision, decision_id="DEC-POS", capsule_id="CAP-POS"), portfolio)["reason"] == "EXCEEDED_MAX_POSITION_SIZE")
            engine.risk_governor.limits["max_position_size"] = 50.0
            engine.risk_governor.limits["max_notional_exposure"] = 100.0
            check("max_notional_blocks_order", engine.risk_governor.check_order_intent(dict(decision, decision_id="DEC-NOT", capsule_id="CAP-NOT"), portfolio)["reason"] == "EXCEEDED_MAX_NOTIONAL_EXPOSURE")
            engine.risk_governor.limits["max_notional_exposure"] = 100_000.0
            loss_portfolio = dict(portfolio, daily_loss=engine.risk_governor.limits["max_daily_loss"])
            check("max_daily_loss_blocks_order", engine.risk_governor.check_order_intent(dict(decision, decision_id="DEC-LOSS", capsule_id="CAP-LOSS"), loss_portfolio)["reason"] == "EXCEEDED_MAX_DAILY_LOSS_LIMIT")
            hot_portfolio = dict(portfolio, trades_last_hour=engine.risk_governor.limits["max_trades_per_hour"])
            check("max_trades_hour_blocks_order", engine.risk_governor.check_order_intent(dict(decision, decision_id="DEC-HOUR", capsule_id="CAP-HOUR"), hot_portfolio)["reason"] == "EXCEEDED_MAX_TRADES_PER_HOUR")
            engine.risk_governor.trigger_emergency_kill_switch()
            check("kill_switch_blocks_order", engine.risk_governor.check_order_intent(dict(decision, decision_id="DEC-KILL", capsule_id="CAP-KILL"), portfolio)["reason"] == "EMERGENCY_KILL_SWITCH_ACTIVE")
            engine.risk_governor.reset_kill_switch()
            check("short_selling_rejected", engine.broker.execute_paper_fill("ORD-SHORT", "XAUUSD", "SELL", 1.0, engine.current_market_prices["XAUUSD"])["reason"] == "SHORT_SELLING_DISABLED")
            buy = engine.broker.execute_paper_fill("ORD-BUY", "XAUUSD", "BUY", 2.0, market_price_record(100.0, "validation"))
            sell = engine.broker.execute_paper_fill("ORD-SELL", "XAUUSD", "SELL", 1.0, market_price_record(110.0, "validation"))
            check("paper_broker_accounting", buy["success"] and sell["success"] and engine.broker.positions["XAUUSD"]["qty"] == 1.0)
            dry = LiveBrokerDryRun(engine.ledger)
            dry_result = dry.submit_order({"intent_id": "INT-VALIDATE", "asset": "XAUUSD", "direction": "BUY", "quantity": 1.0, "price": 2000.0, "idempotency_key": "idem-validate"})
            check("live_dry_run_sends_nothing", dry_result["success"] and dry_result["sent"] is False)
        finally:
            engine.shutdown()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        old_cwd = Path.cwd()
        os.chdir(tmp)
        engine = VeritasEngine(db_path=tmp / "ledger.db", mode="backtest")
        try:
            report = engine.run_backtest()
            check("backtest_writes_report", Path(".veritas_backtest_report.json").exists() and "ending_equity" in report)
        finally:
            engine.shutdown()
            os.chdir(old_cwd)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ledger = AuditLedger(tmp / "ledger.db")
        are = AREStore(tmp / "are.jsonl", ledger)
        for idx in range(10):
            are.ingest(f"CAP-{idx}", "payload", {"confidence": 1.0}, "node", now_ns(), now_ns())
        are.shutdown()
        check("shutdown_drains_are_queue", len((tmp / "are.jsonl").read_text(encoding="utf-8").splitlines()) == 10)

    return {"passed": len(results), "checks": results}

def main() -> int:
    if "--validate" in sys.argv:
        report = run_validation_harness()
        print(json.dumps(report, indent=2))
        return 0
    if TRADING_MODE == "backtest":
        run_backtest_main()
        return 0
    if TRADING_MODE == "live_dry_run":
        print("PAPER MODE ONLY — NO LIVE ORDERS ENABLED")
        engine = VeritasEngine(mode="live_dry_run")
        try:
            print("LIVE DRY RUN active: exact payloads may be built and audited; nothing is sent.")
        finally:
            engine.shutdown()
        return 0
    if TRADING_MODE == "live":
        print("LIVE MODE REQUESTED — FAIL CLOSED")
        gates = LiveTradingGate.validate(interactive=False)
        print(f"LIVE_MODE_FAIL_CLOSED: {gates['reason']}")
        return 2
    run_paper_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
