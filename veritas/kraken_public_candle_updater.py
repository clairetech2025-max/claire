#!/usr/bin/env python3
"""Read-only Kraken public OHLC updater for Veritas paper runtime.

This module only calls Kraken public market-data endpoints. It never accepts
API keys, never calls private endpoints, and never touches order endpoints.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


KRAKEN_PUBLIC_BASE = "https://api.kraken.com/0/public"
ALLOWED_PUBLIC_ENDPOINTS = {"OHLC"}
FORBIDDEN_ENDPOINT_MARKERS = (
    "/private/",
    "AddOrder",
    "CancelOrder",
    "EditOrder",
    "TradesHistory",
    "ClosedOrders",
    "Ledgers",
    "Balance",
)
DEFAULT_PUBLIC_CANDLE_DIR = Path(__file__).resolve().parent / "public_candles"
DEFAULT_INTERVAL = 5


class KrakenPublicCandleError(RuntimeError):
    pass


@dataclass
class PublicCandleUpdate:
    pair: str
    interval: int
    rows_written: int
    last: str | None
    output_file: str
    manifest_file: str
    fetched_at: str
    live_execution: bool = False
    endpoint: str = "OHLC"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_pair(pair: str) -> str:
    cleaned = pair.strip().upper().replace("-", "/")
    aliases = {
        "BTC/USD": "XBTUSD",
        "XBT/USD": "XBTUSD",
        "BTCUSD": "XBTUSD",
        "XBTUSD": "XBTUSD",
        "ETH/USD": "ETHUSD",
        "ETHUSD": "ETHUSD",
        "SOL/USD": "SOLUSD",
        "SOLUSD": "SOLUSD",
        "XRP/USD": "XRPUSD",
        "XRPUSD": "XRPUSD",
        "MANA/USD": "MANAUSD",
        "MANAUSD": "MANAUSD",
    }
    return aliases.get(cleaned, cleaned.replace("/", ""))


def assert_public_endpoint(endpoint: str, url: str) -> None:
    if endpoint not in ALLOWED_PUBLIC_ENDPOINTS:
        raise KrakenPublicCandleError(f"Refusing non-public candle endpoint: {endpoint}")
    if any(marker.lower() in url.lower() for marker in FORBIDDEN_ENDPOINT_MARKERS):
        raise KrakenPublicCandleError(f"Refusing forbidden Kraken endpoint: {endpoint}")


def query_public_ohlc(
    pair: str,
    interval: int = DEFAULT_INTERVAL,
    since: int | None = None,
    transport: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_pair(pair)
    query = {"pair": normalized, "interval": int(interval)}
    if since is not None:
        query["since"] = int(since)
    url = f"{KRAKEN_PUBLIC_BASE}/OHLC?{urllib.parse.urlencode(query)}"
    assert_public_endpoint("OHLC", url)
    if transport:
        return transport(url)
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_ohlc_response(pair: str, response: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    errors = response.get("error") or []
    if errors:
        raise KrakenPublicCandleError(f"Kraken public OHLC error: {errors}")
    result = response.get("result") or {}
    last = result.get("last")
    candle_key = next((key for key in result.keys() if key != "last"), None)
    if not candle_key:
        return [], last
    normalized = normalize_pair(pair)
    rows = []
    for raw in result.get(candle_key) or []:
        if len(raw) < 8:
            continue
        rows.append(
            {
                "timestamp": int(float(raw[0])),
                "open": float(raw[1]),
                "high": float(raw[2]),
                "low": float(raw[3]),
                "close": float(raw[4]),
                "vwap": float(raw[5]),
                "volume": float(raw[6]),
                "trades": int(float(raw[7])),
                "pair": normalized,
                "source": "kraken_public_ohlc",
            }
        )
    rows.sort(key=lambda row: row["timestamp"])
    return rows, str(last) if last is not None else None


def load_since(manifest_file: Path) -> int | None:
    if not manifest_file.exists():
        return None
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        last = data.get("last")
        return int(last) if last is not None else None
    except Exception:
        return None


def write_candles_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    existing: dict[int, dict[str, Any]] = {}
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    existing[int(float(row["timestamp"]))] = row
                except Exception:
                    continue
    for row in rows:
        existing[int(row["timestamp"])] = row
    ordered = [existing[key] for key in sorted(existing)]
    fieldnames = ["timestamp", "open", "high", "low", "close", "vwap", "volume", "trades", "pair", "source"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ordered)
    return len(ordered)


def update_public_candles(
    pair: str,
    interval: int = DEFAULT_INTERVAL,
    output_dir: Path = DEFAULT_PUBLIC_CANDLE_DIR,
    since: int | None = None,
    transport: Callable[[str], dict[str, Any]] | None = None,
) -> PublicCandleUpdate:
    normalized = normalize_pair(pair)
    output_dir = Path(output_dir)
    output_file = output_dir / f"{normalized}_{int(interval)}.csv"
    manifest_file = output_dir / f"{normalized}_{int(interval)}_manifest.json"
    resolved_since = since if since is not None else load_since(manifest_file)
    response = query_public_ohlc(normalized, int(interval), since=resolved_since, transport=transport)
    rows, last = parse_ohlc_response(normalized, response)
    total_rows = write_candles_csv(output_file, rows)
    manifest = {
        "pair": normalized,
        "interval": int(interval),
        "last": last,
        "rows": total_rows,
        "updated_at": utc_now(),
        "endpoint": "OHLC",
        "public_only": True,
        "live_execution": False,
    }
    manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return PublicCandleUpdate(
        pair=normalized,
        interval=int(interval),
        rows_written=total_rows,
        last=last,
        output_file=str(output_file),
        manifest_file=str(manifest_file),
        fetched_at=manifest["updated_at"],
    )


def run_loop(pair: str, interval: int, output_dir: Path, cycles: int, sleep_seconds: float) -> list[PublicCandleUpdate]:
    updates = []
    for idx in range(cycles):
        updates.append(update_public_candles(pair, interval=interval, output_dir=output_dir))
        if idx < cycles - 1:
            time.sleep(sleep_seconds)
    return updates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Kraken public OHLC candles for Veritas paper runtime.")
    parser.add_argument("--pair", default="BTC/USD")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_PUBLIC_CANDLE_DIR)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--sleep-seconds", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    updates = run_loop(args.pair, args.interval, args.output_dir, max(1, args.cycles), max(0.0, args.sleep_seconds))
    print(json.dumps({"ok": True, "updates": [asdict(update) for update in updates]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
