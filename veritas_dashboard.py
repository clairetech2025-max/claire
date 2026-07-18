#!/usr/bin/env python3
"""Streamlit dashboard for the CLAIRE / VERITAS Azure Financial Intelligence Station.

Read-only dashboard except for explicit kill-switch file controls.
No exchange credentials, live order controls, or trading actions are exposed here.
"""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

try:
    from veritas.veritas_trader_engine import (  # type: ignore
        BACKTEST_REPORT_FILE,
        DB_PATH,
        KILL_SWITCH_FILE,
        TRADING_MODE,
    )
except Exception:  # pragma: no cover - dashboard can still read files by convention
    DB_PATH = Path(os.environ.get("VERITAS_DB_PATH", "veritas_system_ledger.db"))
    KILL_SWITCH_FILE = Path(os.environ.get("VERITAS_KILL_SWITCH_FILE", "VERITAS_KILL_SWITCH"))
    BACKTEST_REPORT_FILE = Path(".veritas_backtest_report.json")
    TRADING_MODE = os.environ.get("VERITAS_TRADING_MODE", "paper").strip().lower() or "paper"


STARTED_AT = time.time()
MODE_ORDER = {"paper", "backtest", "live_dry_run", "live"}
VALID_TABLES = {
    "raw_signals",
    "clean_signals",
    "signal_decisions",
    "risk_checks",
    "paper_orders",
    "live_orders",
    "paper_cash_ledger",
    "system_logs",
}

TRADEABLE_ASSETS = ["XAUUSD", "USOUSD", "EURUSD", "SPY", "XBTUSD", "ETHUSD"]
PAPER_FEE = 1.00


st.set_page_config(
    page_title="CLAIRE / VERITAS Financial Intelligence Station",
    page_icon="VERITAS",
    layout="wide",
)


def ns_to_utc(value: Any) -> str:
    try:
        ns = int(value)
        if ns <= 0:
            return ""
        return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return ""


def resolve_db_path() -> Path:
    configured = os.environ.get("VERITAS_DB_PATH", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(Path(str(DB_PATH)).expanduser())
    candidates.append(Path("veritas_system_ledger.db"))
    candidates.append(Path("veritas") / "veritas_system_ledger.db")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_kill_switch_path() -> Path:
    return Path(os.environ.get("VERITAS_KILL_SWITCH_FILE", str(KILL_SWITCH_FILE))).expanduser()


def resolve_backtest_report_path() -> Path:
    return Path(os.environ.get("VERITAS_BACKTEST_REPORT_FILE", str(BACKTEST_REPORT_FILE))).expanduser()


def current_mode() -> str:
    mode = os.environ.get("VERITAS_TRADING_MODE", str(TRADING_MODE)).strip().lower() or "paper"
    return mode if mode in MODE_ORDER else "paper"


def get_in_process_report() -> dict[str, Any] | None:
    """Use an in-process engine only if one is explicitly registered by the host."""
    try:
        import __main__  # noqa: PLC0415

        engine = getattr(__main__, "VERITAS_ENGINE", None)
        if engine and hasattr(engine, "get_market_intelligence_report"):
            return dict(engine.get_market_intelligence_report())
    except Exception as exc:
        st.caption(f"In-process report unavailable: {exc}")
    return None


@st.cache_data(ttl=2)
def table_exists(db_path: str, table: str) -> bool:
    if table not in VALID_TABLES:
        return False
    path = Path(db_path)
    if not path.exists():
        return False
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    return row is not None


@st.cache_data(ttl=2)
def read_table(db_path: str, table: str, limit: int = 25) -> pd.DataFrame:
    if table not in VALID_TABLES:
        return pd.DataFrame()
    path = Path(db_path)
    if not path.exists() or not table_exists(db_path, table):
        return pd.DataFrame()
    with sqlite3.connect(path) as conn:
        try:
            return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", conn, params=(limit,))
        except Exception:
            return pd.DataFrame()


def ensure_dashboard_tables(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_cash_ledger (
                ledger_id TEXT PRIMARY KEY,
                timestamp_ns INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                amount REAL NOT NULL,
                balance_after REAL NOT NULL,
                note TEXT
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
                updated_ts_ns INTEGER
            )
            """
        )
        conn.commit()


def paper_cash_balance(db_path: str) -> float:
    ensure_dashboard_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COALESCE(SUM(amount), 0.0) FROM paper_cash_ledger").fetchone()
    return float(row[0] or 0.0)


def paper_positions_from_orders(db_path: str) -> dict[str, float]:
    paper = read_table(db_path, "paper_orders", 500)
    positions: dict[str, float] = {}
    if paper.empty:
        return positions
    for _, row in paper.iterrows():
        state = str(row.get("state") or "").upper()
        if state not in {"FILLED", "OPEN"}:
            continue
        asset = str(row.get("asset") or "")
        if not asset:
            continue
        qty = float(row.get("filled_qty") or row.get("quantity") or 0.0)
        direction = str(row.get("direction") or "").upper()
        if direction == "SELL":
            qty *= -1
        positions[asset] = positions.get(asset, 0.0) + qty
    return positions


def append_paper_cash_event(db_path: str, event_type: str, amount: float, note: str) -> dict[str, Any]:
    if amount <= 0:
        raise ValueError("amount must be positive")
    ensure_dashboard_tables(db_path)
    signed_amount = amount if event_type in {"DEPOSIT", "TRADE_CREDIT"} else -amount
    balance_after = paper_cash_balance(db_path) + signed_amount
    if balance_after < -1e-9:
        raise ValueError("paper cash cannot go negative")
    record = {
        "ledger_id": f"PCL-{uuid.uuid4().hex[:16].upper()}",
        "timestamp_ns": time.time_ns(),
        "event_type": event_type,
        "amount": signed_amount,
        "balance_after": balance_after,
        "note": str(note or "")[:300],
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO paper_cash_ledger
            (ledger_id, timestamp_ns, event_type, amount, balance_after, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (record["ledger_id"], record["timestamp_ns"], record["event_type"], record["amount"], record["balance_after"], record["note"]),
        )
        conn.commit()
    st.cache_data.clear()
    return record


def append_manual_paper_order(db_path: str, asset: str, direction: str, quantity: float, price: float) -> dict[str, Any]:
    ensure_dashboard_tables(db_path)
    asset = str(asset or "").upper()
    direction = str(direction or "").upper()
    quantity = float(quantity)
    price = float(price)
    if asset not in TRADEABLE_ASSETS:
        raise ValueError(f"unsupported paper asset: {asset}")
    if direction not in {"BUY", "SELL"}:
        raise ValueError("direction must be BUY or SELL")
    if quantity <= 0 or price <= 0:
        raise ValueError("quantity and price must be positive")
    if direction == "SELL" and paper_positions_from_orders(db_path).get(asset, 0.0) < quantity:
        raise ValueError("insufficient paper position; short selling is disabled")
    gross = quantity * price
    if direction == "BUY" and paper_cash_balance(db_path) < gross + PAPER_FEE:
        raise ValueError("insufficient paper cash")
    order_id = f"PAPER-{uuid.uuid4().hex[:16].upper()}"
    intent_id = f"MANUAL-{uuid.uuid4().hex[:16].upper()}"
    ts_ns = time.time_ns()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO paper_orders
            (order_id, intent_id, state, asset, direction, quantity, price, filled_qty, avg_fill_price, updated_ts_ns)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (order_id, intent_id, "FILLED", asset, direction, quantity, price, quantity, price, ts_ns),
        )
        conn.commit()
    cash_delta = gross + PAPER_FEE if direction == "BUY" else max(0.0, gross - PAPER_FEE)
    append_paper_cash_event(db_path, "TRADE_DEBIT" if direction == "BUY" else "TRADE_CREDIT", cash_delta, f"{direction} {quantity} {asset} @ {price}")
    st.cache_data.clear()
    return {"order_id": order_id, "asset": asset, "direction": direction, "quantity": quantity, "price": price}


@st.cache_data(ttl=2)
def count_unresolved_logs(db_path: str) -> int:
    logs = read_table(db_path, "system_logs", 200)
    if logs.empty or "level" not in logs.columns:
        return 0
    return int(logs[logs["level"].astype(str).str.upper().isin(["ERROR", "WARNING", "WARN", "CRITICAL"])].shape[0])


def parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return None


def format_uptime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def available_ram_mb() -> str:
    if psutil is None:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return f"{int(line.split()[1]) / 1024:.1f} MB"
        except Exception:
            return "unknown"
    return f"{psutil.virtual_memory().available / (1024 * 1024):.1f} MB"


def latest_portfolio_from_orders(db_path: str, report: dict[str, Any] | None) -> dict[str, Any]:
    if report:
        portfolio = (((report.get("telemetry") or {}).get("portfolio")) or {})
        if portfolio:
            return portfolio

    paper = read_table(db_path, "paper_orders", 500)
    live = read_table(db_path, "live_orders", 200)
    orders = pd.concat([paper, live], ignore_index=True) if not paper.empty or not live.empty else pd.DataFrame()
    open_orders = 0
    positions = paper_positions_from_orders(db_path)
    if not orders.empty:
        if "state" in orders.columns:
            open_orders = int(orders[orders["state"].astype(str).str.upper().isin(["PENDING", "OPEN", "PARTIAL"])].shape[0])
    cash = paper_cash_balance(db_path)
    position_value = 0.0
    if not paper.empty:
        latest_prices: dict[str, float] = {}
        for _, row in paper.iterrows():
            asset = str(row.get("asset") or "")
            if asset and float(row.get("avg_fill_price") or row.get("price") or 0.0) > 0:
                latest_prices.setdefault(asset, float(row.get("avg_fill_price") or row.get("price") or 0.0))
        position_value = sum(float(qty) * float(latest_prices.get(asset, 0.0)) for asset, qty in positions.items())
    return {
        "cash_balance": cash,
        "equity": cash + position_value,
        "realized_pnl": None,
        "unrealized_pnl": None,
        "daily_loss": None,
        "open_orders": open_orders,
        "positions": positions,
    }


def metric_value(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def render_dataframe(title: str, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    st.subheader(title)
    if df.empty:
        st.info("No ledger records found.")
        return
    view = df.copy()
    for col in ["timestamp_ns", "updated_ts_ns", "received_ts_ns"]:
        if col in view.columns:
            view[col.replace("_ns", "")] = view[col].apply(ns_to_utc)
    if columns:
        keep = [col for col in columns if col in view.columns]
        view = view[keep]
    st.dataframe(view, use_container_width=True, hide_index=True)


def render_header(mode: str, report: dict[str, Any] | None) -> None:
    st.title("CLAIRE / VERITAS Financial Intelligence Station")
    st.caption(f"Current mode: {mode}")
    st.warning("PAPER MODE ONLY unless all live gates pass")
    honesty = "SIMULATED DATA ONLY unless Kraken/backtest/live feed is active"
    if report and report.get("data_honesty"):
        honesty = str(report["data_honesty"])
    st.warning(honesty)


def render_system_telemetry(db_path: str, mode: str, kill_switch: Path) -> None:
    st.header("System Telemetry")
    cols = st.columns(6)
    cols[0].metric("Uptime", format_uptime(time.time() - STARTED_AT))
    cols[1].metric("Available RAM", available_ram_mb())
    cols[2].metric("Active threads", threading.active_count())
    cols[3].metric("Current mode", mode)
    cols[4].metric("Kill-switch", "ACTIVE" if kill_switch.exists() else "clear")
    cols[5].metric("Alerts/logs", count_unresolved_logs(db_path))


def render_portfolio(db_path: str, report: dict[str, Any] | None) -> None:
    st.header("Portfolio Panel")
    portfolio = latest_portfolio_from_orders(db_path, report)
    cols = st.columns(6)
    cols[0].metric("Cash balance", metric_value(portfolio.get("cash_balance", portfolio.get("cash"))))
    cols[1].metric("Equity", metric_value(portfolio.get("equity")))
    cols[2].metric("Realized PnL", metric_value(portfolio.get("realized_pnl")))
    cols[3].metric("Unrealized PnL", metric_value(portfolio.get("unrealized_pnl")))
    cols[4].metric("Daily loss", metric_value(portfolio.get("daily_loss")))
    cols[5].metric("Open orders", metric_value(portfolio.get("open_orders", portfolio.get("open_orders_count"))))

    positions = portfolio.get("positions") or portfolio.get("positions_by_asset") or {}
    st.subheader("Positions by Asset")
    if isinstance(positions, dict) and positions:
        st.dataframe(pd.DataFrame([{"asset": k, "position": v} for k, v in positions.items()]), use_container_width=True, hide_index=True)
    else:
        st.info("No position records found.")


def render_paper_trading_controls(db_path: str) -> None:
    st.header("Paper Trading Controls")
    st.caption("Fake-money testing only. These controls write to the Veritas finance ledger, not CLAIRE memory.")

    ensure_dashboard_tables(db_path)
    cols = st.columns([1, 1])
    with cols[0]:
        st.subheader("Add Paper Money")
        amount = st.number_input("Paper deposit amount", min_value=0.0, value=10000.0, step=1000.0, key="paper_deposit_amount")
        note = st.text_input("Deposit note", value="manual paper funding", key="paper_deposit_note")
        if st.button("Add Fake Money", type="primary"):
            try:
                record = append_paper_cash_event(db_path, "DEPOSIT", float(amount), note)
                st.success(f"Added paper funds. New paper cash balance: {record['balance_after']:,.2f}")
                st.rerun()
            except Exception as exc:
                st.error(f"Paper deposit failed: {exc}")

    with cols[1]:
        st.subheader("Manual Paper Trade")
        asset = st.selectbox("Asset", TRADEABLE_ASSETS, index=TRADEABLE_ASSETS.index("XBTUSD") if "XBTUSD" in TRADEABLE_ASSETS else 0)
        direction = st.selectbox("Direction", ["BUY", "SELL"])
        quantity = st.number_input("Quantity", min_value=0.0, value=0.01, step=0.01, format="%.8f")
        price = st.number_input("Limit/fill price", min_value=0.0, value=50000.0, step=100.0, format="%.8f")
        if st.button("Place Paper Trade"):
            try:
                order = append_manual_paper_order(db_path, asset, direction, float(quantity), float(price))
                st.success(f"Paper trade filled: {order['direction']} {order['quantity']} {order['asset']} @ {order['price']}")
                st.rerun()
            except Exception as exc:
                st.error(f"Paper trade rejected: {exc}")

    cash = paper_cash_balance(db_path)
    st.metric("Paper cash available", metric_value(cash))
    cash_ledger = read_table(db_path, "paper_cash_ledger", 25)
    render_dataframe("Paper Cash Ledger", cash_ledger, ["timestamp", "event_type", "amount", "balance_after", "note"])


def render_live_gate_panel(mode: str, kill_switch: Path) -> None:
    st.header("Live Gate")
    st.caption("Inspection only. Live exchange execution remains fail-closed unless a real live broker is separately implemented and all gates pass.")
    env_hash = os.environ.get("VERITAS_LIVE_PASSPHRASE_HASH", "").strip()
    gate_rows = [
        {"gate": "VERITAS_TRADING_MODE=live", "status": mode == "live"},
        {"gate": "VERITAS_ENABLE_LIVE_TRADING=true", "status": os.environ.get("VERITAS_ENABLE_LIVE_TRADING", "").lower() == "true"},
        {"gate": "VERITAS_LIVE_PASSPHRASE_HASH present", "status": bool(env_hash)},
        {"gate": "KRAKEN_API_KEY present", "status": bool(os.environ.get("KRAKEN_API_KEY"))},
        {"gate": "KRAKEN_API_SECRET present", "status": bool(os.environ.get("KRAKEN_API_SECRET"))},
        {"gate": "Kill-switch clear", "status": not kill_switch.exists()},
        {"gate": "Live broker implemented", "status": False},
    ]
    st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)

    entered = st.text_input("Live passphrase check", value="", type="password")
    if st.button("Verify Live Passphrase"):
        if not env_hash:
            st.error("VERITAS_LIVE_PASSPHRASE_HASH is not set. Passphrase was not stored.")
        else:
            entered_hash = hashlib.sha256(entered.encode("utf-8")).hexdigest()
            if hmac.compare_digest(entered_hash, env_hash):
                st.success("Passphrase matches configured hash. Live execution is still fail-closed until every live gate and broker implementation exists.")
            else:
                st.error("Passphrase mismatch.")


def render_signal_panel(db_path: str, report: dict[str, Any] | None) -> None:
    st.header("Signal Panel")
    if report and report.get("signals"):
        rows = []
        for item in report.get("signals", []):
            payload = item.get("payload") or item.get("sanitized_payload") or item.get("text") or item
            rows.append({
                "capsule_id": item.get("capsule_id") or item.get("id"),
                "origin/source": item.get("source_node") or item.get("source") or item.get("origin"),
                "payload_summary": str(payload)[:240],
                "confidence": item.get("confidence"),
                "provenance_status": item.get("provenance_status") or item.get("cryptographic_signature") or "ledger",
                "stale": item.get("stale", "unknown"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return

    clean = read_table(db_path, "clean_signals", 20)
    raw = read_table(db_path, "raw_signals", 20)
    if clean.empty and raw.empty:
        st.info("No signal records found.")
        return
    merged = clean.merge(raw[["capsule_id", "source_node"]], on="capsule_id", how="left") if not clean.empty and not raw.empty and "capsule_id" in clean.columns else clean
    rows = []
    for _, item in merged.iterrows():
        rows.append({
            "capsule_id": item.get("capsule_id"),
            "origin/source": item.get("source_node"),
            "payload_summary": str(item.get("sanitized_payload") or "")[:240],
            "confidence": item.get("confidence"),
            "provenance_status": "signed" if item.get("cryptographic_signature") else "unsigned",
            "stale": "unknown",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_decision_panel(db_path: str) -> None:
    df = read_table(db_path, "signal_decisions", 25)
    render_dataframe(
        "Decision Panel",
        df,
        ["timestamp", "asset", "direction", "confidence", "reason", "is_actionable", "strategy_version"],
    )


def render_risk_panel(db_path: str) -> None:
    st.header("Risk Panel")
    df = read_table(db_path, "risk_checks", 25)
    if df.empty:
        st.info("No risk checks found.")
        return
    rows = []
    for _, row in df.iterrows():
        snapshot = parse_json(row.get("snapshot_json")) or {}
        rows.append({
            "timestamp": ns_to_utc(row.get("timestamp_ns")),
            "approved/rejected": "approved" if int(row.get("approved") or 0) else "rejected",
            "reason": row.get("reason"),
            "snapshot_summary": json.dumps(snapshot, ensure_ascii=False)[:400] if snapshot else "",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_orders_panel(db_path: str) -> None:
    st.header("Orders Panel")
    paper = read_table(db_path, "paper_orders", 25)
    live = read_table(db_path, "live_orders", 25)
    order_columns = ["order_id", "state", "asset", "direction", "quantity", "price", "filled_qty", "avg_fill_price", "updated_ts"]
    render_dataframe("Paper Orders", paper, order_columns)
    render_dataframe("Live Orders", live, order_columns)


def render_backtest_panel(report_path: Path) -> None:
    st.header("Backtest Panel")
    if not report_path.exists():
        st.info("No .veritas_backtest_report.json found.")
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        st.error(f"Backtest report could not be read: {exc}")
        return
    cols = st.columns(4)
    cols[0].metric("Starting balance", metric_value(report.get("starting_balance")))
    cols[1].metric("Ending equity", metric_value(report.get("ending_equity")))
    cols[2].metric("Total return", f"{float(report.get('total_return') or 0) * 100:.2f}%")
    cols[3].metric("Max drawdown", f"{float(report.get('max_drawdown') or 0) * 100:.2f}%")
    cols = st.columns(4)
    cols[0].metric("Win rate", f"{float(report.get('win_rate') or 0) * 100:.2f}%")
    cols[1].metric("Profit factor", metric_value(report.get("profit_factor")))
    cols[2].metric("Trades", metric_value(report.get("number_of_trades")))
    cols[3].metric("Rejected trades", metric_value(report.get("rejected_trades")))
    st.metric("HOLD decisions", metric_value(report.get("HOLD_decisions")))


def render_emergency_controls(kill_switch: Path) -> None:
    st.header("Emergency Controls")
    st.caption("No live order buttons are exposed. These controls only create or remove the local kill-switch file.")
    status = kill_switch.exists()
    st.metric("Kill-switch file", "ACTIVE" if status else "clear")
    if st.button("Create VERITAS_KILL_SWITCH", type="primary"):
        kill_switch.write_text(f"created_by_dashboard={datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")
        st.success(f"Kill-switch created at {kill_switch}")
        st.rerun()
    confirm = st.text_input("Type I UNDERSTAND RISK to remove the kill-switch", value="", type="default")
    if st.button("Remove VERITAS_KILL_SWITCH"):
        if confirm == "I UNDERSTAND RISK":
            if kill_switch.exists():
                kill_switch.unlink()
            st.success("Kill-switch removed after typed confirmation.")
            st.rerun()
        else:
            st.error("Typed confirmation did not match. Kill-switch was not removed.")


def render_run_command() -> None:
    st.header("Run command")
    st.code("pip install streamlit pandas\nstreamlit run veritas_dashboard.py", language="bash")


def main() -> None:
    db_path = resolve_db_path()
    kill_switch = resolve_kill_switch_path()
    report_path = resolve_backtest_report_path()
    mode = current_mode()
    report = get_in_process_report()

    render_header(mode, report)
    st.caption(f"Ledger: {db_path}")
    st.caption(f"Kill-switch: {kill_switch}")

    render_system_telemetry(str(db_path), mode, kill_switch)
    render_portfolio(str(db_path), report)
    render_paper_trading_controls(str(db_path))
    render_live_gate_panel(mode, kill_switch)
    render_signal_panel(str(db_path), report)
    render_decision_panel(str(db_path))
    render_risk_panel(str(db_path))
    render_orders_panel(str(db_path))
    render_backtest_panel(report_path)
    render_emergency_controls(kill_switch)
    render_run_command()


if __name__ == "__main__":
    main()
