#!/usr/bin/env python3
"""Read-only Kraken public microstructure observer.

Uses only Kraken public Ticker and Depth endpoints. It never accepts API keys
and never calls private or order endpoints.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .kraken_public_candle_updater import normalize_pair
    from .veritas_paper_runtime import CONFIGURED_PAIRS, DECISIONS_FILE, STATE_DIR, TAKER_FEE_RATE
except ImportError:
    from kraken_public_candle_updater import normalize_pair
    from veritas_paper_runtime import CONFIGURED_PAIRS, DECISIONS_FILE, STATE_DIR, TAKER_FEE_RATE


KRAKEN_PUBLIC_BASE = "https://api.kraken.com/0/public"
ALLOWED_ENDPOINTS = {"Ticker", "Depth"}
FORBIDDEN_MARKERS = ("private", "AddOrder", "CancelOrder", "EditOrder", "TradesHistory", "ClosedOrders", "Ledgers", "Balance")
MICROSTRUCTURE_REPORT_FILE = STATE_DIR / "veritas_microstructure_report.json"


class MicrostructureError(RuntimeError):
    pass


@dataclass
class PublicResponse:
    payload: dict[str, Any]
    latency_ms: float
    local_receive_ts: str
    url: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_public_url(endpoint: str, url: str) -> None:
    if endpoint not in ALLOWED_ENDPOINTS:
        raise MicrostructureError(f"Refusing non-observation endpoint: {endpoint}")
    lowered = url.lower()
    if any(marker.lower() in lowered for marker in FORBIDDEN_MARKERS):
        raise MicrostructureError(f"Refusing forbidden endpoint: {endpoint}")


def query_public(endpoint: str, params: dict[str, Any], transport: Callable[[str], dict[str, Any]] | None = None) -> PublicResponse:
    url = f"{KRAKEN_PUBLIC_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    assert_public_url(endpoint, url)
    started = time.perf_counter()
    if transport:
        payload = transport(url)
    else:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000.0
    return PublicResponse(payload=payload, latency_ms=latency_ms, local_receive_ts=utc_now(), url=url)


def result_object(response: dict[str, Any]) -> tuple[str, Any]:
    errors = response.get("error") or []
    if errors:
        raise MicrostructureError(str(errors))
    result = response.get("result") or {}
    key = next(iter(result.keys()), "")
    return key, result.get(key)


def estimate_buy_slippage(asks: list[list[Any]], notional_usd: float) -> dict[str, Any]:
    remaining = float(notional_usd)
    filled_qty = 0.0
    spent = 0.0
    best_ask = float(asks[0][0]) if asks else 0.0
    for level in asks:
        price = float(level[0])
        qty = float(level[1])
        level_notional = price * qty
        take = min(remaining, level_notional)
        if take <= 0:
            break
        filled_qty += take / price
        spent += take
        remaining -= take
        if remaining <= 1e-9:
            break
    if not filled_qty or not best_ask:
        return {"notional_usd": notional_usd, "enough_liquidity": False, "estimated_slippage_pct": None}
    avg_price = spent / filled_qty
    return {
        "notional_usd": notional_usd,
        "enough_liquidity": remaining <= 1e-9,
        "avg_fill_price": round(avg_price, 10),
        "estimated_slippage_pct": round((avg_price - best_ask) / best_ask * 100.0, 8),
        "estimated_taker_fee_usd": round(notional_usd * TAKER_FEE_RATE, 8),
    }


def observe_pair(pair: str, depth_count: int = 25, transport: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = normalize_pair(pair)
    ticker_response = query_public("Ticker", {"pair": normalized}, transport=transport)
    depth_response = query_public("Depth", {"pair": normalized, "count": depth_count}, transport=transport)
    _, ticker = result_object(ticker_response.payload)
    _, depth = result_object(depth_response.payload)
    ask = float(ticker["a"][0])
    bid = float(ticker["b"][0])
    spread = ask - bid
    mid = (ask + bid) / 2.0
    spread_pct = spread / mid * 100.0 if mid else 0.0
    asks = depth.get("asks") or []
    bids = depth.get("bids") or []
    ask_depth_usd = sum(float(level[0]) * float(level[1]) for level in asks)
    bid_depth_usd = sum(float(level[0]) * float(level[1]) for level in bids)
    top_ask_volume = float(asks[0][1]) if asks else 0.0
    top_bid_volume = float(bids[0][1]) if bids else 0.0
    slippage = [estimate_buy_slippage(asks, amount) for amount in (25.0, 50.0, 125.0)]
    taker_round_trip_pct = TAKER_FEE_RATE * 2 * 100.0
    return {
        "pair": normalized,
        "api_response_timestamp": ticker_response.local_receive_ts,
        "local_receive_timestamp": depth_response.local_receive_ts,
        "observed_api_latency_ms": round(ticker_response.latency_ms + depth_response.latency_ms, 4),
        "best_bid": bid,
        "best_ask": ask,
        "bid_ask_spread": round(spread, 10),
        "spread_percentage": round(spread_pct, 8),
        "order_book_depth": {"asks": len(asks), "bids": len(bids), "ask_depth_usd": round(ask_depth_usd, 4), "bid_depth_usd": round(bid_depth_usd, 4)},
        "top_of_book_volume": {"ask": top_ask_volume, "bid": top_bid_volume},
        "estimated_slippage": slippage,
        "estimated_taker_fee_impact": {"one_way_pct": TAKER_FEE_RATE * 100.0, "round_trip_pct": taker_round_trip_pct},
        "spread_large_enough_to_overcome_fees": spread_pct > taker_round_trip_pct,
        "enough_liquidity_for_125": bool(slippage[-1].get("enough_liquidity")),
        "abnormal_spread_widening": spread_pct > max(0.5, taker_round_trip_pct),
        "public_only": True,
        "live_execution": False,
    }


def build_microstructure_report(pairs: list[str] | None = None, transport: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    selected = pairs or CONFIGURED_PAIRS
    pair_reports = []
    errors = []
    for pair in selected:
        try:
            pair_reports.append(observe_pair(pair, transport=transport))
        except Exception as exc:
            errors.append({"pair": normalize_pair(pair), "error": str(exc)})
    latencies = [row["observed_api_latency_ms"] for row in pair_reports]
    spread_support = [row for row in pair_reports if row["spread_large_enough_to_overcome_fees"]]
    enough_liquidity = [row for row in pair_reports if row["enough_liquidity_for_125"]]
    latest_decisions = latest_decision_by_pair()
    alignment = {
        row["pair"]: {
            "latest_decision": latest_decisions.get(row["pair"], {}).get("decision"),
            "execution_result": latest_decisions.get(row["pair"], {}).get("execution_result"),
            "favorable_liquidity": row["enough_liquidity_for_125"] and not row["abnormal_spread_widening"],
            "directional_signal_aligns_with_liquidity": (
                latest_decisions.get(row["pair"], {}).get("decision") in {"BUY", "SELL"}
                and row["enough_liquidity_for_125"]
                and not row["abnormal_spread_widening"]
            ),
        }
        for row in pair_reports
    }
    report = {
        "generated_at": utc_now(),
        "public_only": True,
        "live_execution": False,
        "pairs": pair_reports,
        "errors": errors,
        "latency_summary": {
            "count": len(latencies),
            "average_ms": round(sum(latencies) / len(latencies), 4) if latencies else None,
            "max_ms": round(max(latencies), 4) if latencies else None,
            "min_ms": round(min(latencies), 4) if latencies else None,
        },
        "per_pair_spread_liquidity_summary": {
            row["pair"]: {
                "spread_percentage": row["spread_percentage"],
                "enough_liquidity_for_125": row["enough_liquidity_for_125"],
                "abnormal_spread_widening": row["abnormal_spread_widening"],
            }
            for row in pair_reports
        },
        "directional_signal_liquidity_alignment": alignment,
        "conclusion": {
            "supports_spread_arbitrage_observation": bool(spread_support),
            "liquidity_supports_125_paper_trade_pairs": [row["pair"] for row in enough_liquidity],
            "summary": (
                "Kraken public data supports spread/liquidity observation. It does not by itself prove "
                "arbitrage viability; fees and spread must be compared over time without live execution."
            ),
        },
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MICROSTRUCTURE_REPORT_FILE.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def latest_decision_by_pair() -> dict[str, dict[str, Any]]:
    if not DECISIONS_FILE.exists():
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for line in DECISIONS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        pair = row.get("pair")
        if pair:
            latest[str(pair)] = row
    return latest
