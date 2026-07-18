from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from current_truth_loader import get_subsystem_entry


NOT_REGISTERED = "Veritas subsystem not registered."


def _entry() -> dict[str, Any] | None:
    return get_subsystem_entry("Veritas")


def _registered_root() -> Path | None:
    entry = _entry()
    if not entry:
        return None
    root = Path(str(entry.get("absolute_path") or "")).expanduser()
    if not root.exists():
        return None
    return root


def _not_configured(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    status = {"status": "not_configured", "summary": NOT_REGISTERED}
    if extra:
        status.update(extra)
    return status


def _registry_path(key: str, default_name: str | None = None) -> Path | None:
    root = _registered_root()
    if root is None:
        return None
    entry = _entry() or {}
    value = entry.get(key)
    if value:
        return Path(str(value)).expanduser()
    if default_name:
        return root / default_name
    return None


def _db_path() -> Path | None:
    return _registry_path("ledger_path", "veritas_system_ledger.db")


def _kill_switch_path() -> Path | None:
    return _registry_path("kill_switch_path", "VERITAS_KILL_SWITCH")


def _backtest_report_path() -> Path | None:
    return _registry_path("backtest_report_path", ".veritas_backtest_report.json")


def _paper_trade_log_path() -> Path | None:
    return _registry_path("paper_trade_log")


def _market_data_path() -> Path | None:
    return _registry_path("market_data_path")


def _read_table(table: str, limit: int = 10) -> list[dict[str, Any]]:
    db_path = _db_path()
    if not db_path or not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []


def get_trading_station_status() -> dict[str, Any]:
    root = _registered_root()
    if root is None:
        return _not_configured()
    db_path = _db_path()
    kill_switch = _kill_switch_path()
    return {
        "status": "configured",
        "subsystem": "Veritas",
        "authority_role": (_entry() or {}).get("authority_role"),
        "root_path": str(root),
        "db_path": str(db_path) if db_path else None,
        "db_exists": bool(db_path and db_path.exists()),
        "kill_switch_active": bool(kill_switch and kill_switch.exists()),
        "mode": os.environ.get("VERITAS_TRADING_MODE", "paper"),
        "memory_authority": False,
        "default_runtime_authority": False,
    }


def get_kraken_status() -> dict[str, Any]:
    root = _registered_root()
    if root is None:
        return _not_configured()
    return {
        "status": "configured",
        "connector": "Kraken",
        "root_path": str(root),
        "api_key_present": bool(os.environ.get("KRAKEN_API_KEY")),
        "api_secret_present": bool(os.environ.get("KRAKEN_API_SECRET")),
        "live_trading_from_chat": "blocked",
    }


def get_market_data_status() -> dict[str, Any]:
    root = _registered_root()
    if root is None:
        return _not_configured()
    data_path = _market_data_path()
    files = []
    if data_path and data_path.exists():
        files = [path.name for path in sorted(data_path.glob("*")) if path.is_file()][:20]
    return {
        "status": "configured" if data_path and data_path.exists() else "not_configured",
        "summary": "Kraken OHLCV market data path registered." if files else "No registered Kraken OHLCV files found.",
        "market_data_path": str(data_path) if data_path else None,
        "files": files,
    }


def get_latest_ohlc_summary() -> dict[str, Any]:
    market = get_market_data_status()
    if market.get("status") != "configured":
        return market
    data_path = Path(str(market["market_data_path"]))
    summaries = []
    for path in sorted(data_path.glob("*")):
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                first = handle.readline().strip()
                last = ""
                for line in handle:
                    if line.strip():
                        last = line.strip()
            summaries.append({"file": path.name, "bytes": path.stat().st_size, "first_row": first, "last_row": last})
        except Exception as exc:
            summaries.append({"file": path.name, "error": str(exc)})
    return {"status": "configured", "summary": "Latest OHLCV file boundaries read.", "items": summaries}


def get_paper_trade_summary() -> dict[str, Any]:
    root = _registered_root()
    if root is None:
        return _not_configured()
    log_path = _paper_trade_log_path()
    if not log_path or not log_path.exists():
        return {"status": "not_configured", "summary": "Paper-trade log not registered.", "items": []}
    items = []
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines[-10:]:
            try:
                items.append(json.loads(line))
            except Exception:
                items.append({"raw": line[:500]})
    except Exception as exc:
        return {"status": "error", "summary": str(exc), "items": []}
    return {"status": "configured", "summary": f"Paper-trade log contains {len(lines)} records.", "items": items}


def get_risk_status() -> dict[str, Any]:
    checks = get_recent_risk_checks(10)
    return {
        "status": "configured" if _registered_root() else "not_configured",
        "summary": "Recent Veritas risk checks are available." if checks else "No recent Veritas risk checks found.",
        "items": checks,
        "live_trading_from_chat": "blocked",
    }


def get_kill_switch_status() -> dict[str, Any]:
    root = _registered_root()
    if root is None:
        return _not_configured({"active": False})
    kill_switch = _kill_switch_path()
    return {"status": "configured", "active": bool(kill_switch and kill_switch.exists()), "path": str(kill_switch) if kill_switch else None}


def get_latest_backtest_report() -> dict[str, Any] | None:
    report_path = _backtest_report_path()
    if not report_path or not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def get_recent_risk_checks(limit: int = 10) -> list[dict[str, Any]]:
    return _read_table("risk_checks", limit)


def get_recent_orders(limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    return {"paper_orders": _read_table("paper_orders", limit), "live_orders": _read_table("live_orders", limit)}


class VeritasAdapter:
    def get_trading_station_status(self) -> dict[str, Any]:
        return get_trading_station_status()

    def get_kraken_status(self) -> dict[str, Any]:
        return get_kraken_status()

    def get_market_data_status(self) -> dict[str, Any]:
        return get_market_data_status()

    def get_latest_ohlc_summary(self) -> dict[str, Any]:
        return get_latest_ohlc_summary()

    def get_paper_trade_summary(self) -> dict[str, Any]:
        return get_paper_trade_summary()

    def get_risk_status(self) -> dict[str, Any]:
        return get_risk_status()

    def get_latest_backtest_report(self) -> dict[str, Any] | None:
        return get_latest_backtest_report()

    def get_recent_risk_checks(self) -> list[dict[str, Any]]:
        return get_recent_risk_checks()

    def get_recent_orders(self) -> dict[str, list[dict[str, Any]]]:
        return get_recent_orders()

    def get_kill_switch_status(self) -> dict[str, Any]:
        return get_kill_switch_status()
