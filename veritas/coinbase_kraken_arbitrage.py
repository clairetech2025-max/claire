#!/usr/bin/env python3
"""Read-only Kraken/Coinbase arbitrage observer.

This module uses public market-data endpoints only. It never accepts API keys,
never calls account endpoints, and never places orders. The output is an
observation report used to decide whether arbitrage or lead-lag research is
worth pursuing.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .kraken_public_candle_updater import normalize_pair as normalize_kraken_pair
    from .veritas_paper_runtime import CONFIGURED_PAIRS, STATE_DIR, TAKER_FEE_RATE
except ImportError:
    from kraken_public_candle_updater import normalize_pair as normalize_kraken_pair
    from veritas_paper_runtime import CONFIGURED_PAIRS, STATE_DIR, TAKER_FEE_RATE


KRAKEN_PUBLIC_BASE = "https://api.kraken.com/0/public"
COINBASE_EXCHANGE_PUBLIC_BASE = "https://api.exchange.coinbase.com"
ARBITRAGE_REPORT_FILE = STATE_DIR / "veritas_arbitrage_report.json"

COINBASE_TAKER_FEE_RATE = 0.0060
ARBITRAGE_SAFETY_MARGIN = 0.0020
FORBIDDEN_MARKERS = (
    "/private/",
    "AddOrder",
    "CancelOrder",
    "EditOrder",
    "orders",
    "accounts",
    "fills",
    "ledger",
    "withdraw",
    "deposit",
)


class ArbitrageObserverError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def coinbase_product_id(pair: str) -> str:
    normalized = normalize_kraken_pair(pair)
    mapping = {
        "XBTUSD": "BTC-USD",
        "BTCUSD": "BTC-USD",
        "ETHUSD": "ETH-USD",
        "XRPUSD": "XRP-USD",
        "SOLUSD": "SOL-USD",
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized.endswith("USD"):
        return f"{normalized[:-3]}-USD"
    return pair.upper().replace("/", "-")


def assert_public_url(url: str) -> None:
    lowered = url.lower()
    if any(marker.lower() in lowered for marker in FORBIDDEN_MARKERS):
        raise ArbitrageObserverError(f"Refusing forbidden endpoint: {url}")
    allowed = lowered.startswith(KRAKEN_PUBLIC_BASE.lower()) or lowered.startswith(COINBASE_EXCHANGE_PUBLIC_BASE.lower())
    if not allowed:
        raise ArbitrageObserverError(f"Refusing unknown market-data host: {url}")


def fetch_json(url: str, transport: Callable[[str], dict[str, Any]] | None = None) -> tuple[dict[str, Any], float, str]:
    assert_public_url(url)
    started = time.perf_counter()
    if transport:
        payload = transport(url)
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "VeritasReadOnlyArbitrageObserver/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000.0
    return payload, latency_ms, utc_now()


def fetch_kraken_ticker(pair: str, transport: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = normalize_kraken_pair(pair)
    url = f"{KRAKEN_PUBLIC_BASE}/Ticker?{urllib.parse.urlencode({'pair': normalized})}"
    payload, latency_ms, received_at = fetch_json(url, transport=transport)
    errors = payload.get("error") or []
    if errors:
        raise ArbitrageObserverError(f"Kraken ticker error for {normalized}: {errors}")
    result = payload.get("result") or {}
    key = next(iter(result.keys()), "")
    ticker = result.get(key) or {}
    return {
        "exchange": "kraken",
        "pair": normalized,
        "bid": float(ticker["b"][0]),
        "ask": float(ticker["a"][0]),
        "last": float(ticker["c"][0]),
        "volume": float(ticker.get("v", [0, 0])[1]),
        "latency_ms": round(latency_ms, 4),
        "received_at": received_at,
        "url": url,
    }


def fetch_coinbase_ticker(pair: str, transport: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    product = coinbase_product_id(pair)
    url = f"{COINBASE_EXCHANGE_PUBLIC_BASE}/products/{urllib.parse.quote(product)}/ticker"
    payload, latency_ms, received_at = fetch_json(url, transport=transport)
    return {
        "exchange": "coinbase",
        "pair": product,
        "bid": float(payload["bid"]),
        "ask": float(payload["ask"]),
        "last": float(payload["price"]),
        "volume": float(payload.get("volume") or 0.0),
        "latency_ms": round(latency_ms, 4),
        "received_at": received_at,
        "url": url,
    }


def estimate_direction(pair: str, buy: dict[str, Any], sell: dict[str, Any]) -> dict[str, Any]:
    buy_ask = float(buy["ask"])
    sell_bid = float(sell["bid"])
    mid = (buy_ask + sell_bid) / 2.0 if buy_ask and sell_bid else 0.0
    gross_spread = sell_bid - buy_ask
    gross_spread_pct = gross_spread / mid if mid else 0.0
    fee_fraction = TAKER_FEE_RATE + COINBASE_TAKER_FEE_RATE
    net_spread_pct = gross_spread_pct - fee_fraction - ARBITRAGE_SAFETY_MARGIN
    return {
        "pair": pair,
        "buy_exchange": buy["exchange"],
        "sell_exchange": sell["exchange"],
        "buy_ask": buy_ask,
        "sell_bid": sell_bid,
        "gross_spread_usd": round(gross_spread, 10),
        "gross_spread_pct": round(gross_spread_pct, 8),
        "estimated_fee_pct": round(fee_fraction, 8),
        "safety_margin_pct": round(ARBITRAGE_SAFETY_MARGIN, 8),
        "estimated_net_spread_pct": round(net_spread_pct, 8),
        "executable_after_costs": net_spread_pct > 0.0,
    }


def observe_pair(pair: str, transport: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    kraken = fetch_kraken_ticker(pair, transport=transport)
    coinbase = fetch_coinbase_ticker(pair, transport=transport)
    directions = [
        estimate_direction(pair, kraken, coinbase),
        estimate_direction(pair, coinbase, kraken),
    ]
    best = max(directions, key=lambda item: item["estimated_net_spread_pct"])
    return {
        "pair": normalize_kraken_pair(pair),
        "coinbase_product": coinbase_product_id(pair),
        "public_only": True,
        "live_execution": False,
        "kraken": {key: value for key, value in kraken.items() if key != "url"},
        "coinbase": {key: value for key, value in coinbase.items() if key != "url"},
        "directions": directions,
        "best_direction": best,
        "opportunity_after_costs": bool(best["executable_after_costs"]),
        "latency_ms": round(float(kraken["latency_ms"]) + float(coinbase["latency_ms"]), 4),
    }


def build_arbitrage_report(
    pairs: list[str] | None = None,
    transport: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected = pairs or CONFIGURED_PAIRS
    observations = []
    errors = []
    for pair in selected:
        try:
            observations.append(observe_pair(pair, transport=transport))
        except Exception as exc:
            errors.append({"pair": normalize_kraken_pair(pair), "error": str(exc)})
    executable = [row for row in observations if row["opportunity_after_costs"]]
    latencies = [row["latency_ms"] for row in observations]
    report = {
        "generated_at": utc_now(),
        "public_only": True,
        "live_execution": False,
        "private_keys_required": False,
        "order_endpoints_used": False,
        "pairs": observations,
        "errors": errors,
        "latency_summary": {
            "count": len(latencies),
            "average_ms": round(sum(latencies) / len(latencies), 4) if latencies else None,
            "max_ms": round(max(latencies), 4) if latencies else None,
            "min_ms": round(min(latencies), 4) if latencies else None,
        },
        "fee_model": {
            "kraken_taker_fee": TAKER_FEE_RATE,
            "coinbase_taker_fee": COINBASE_TAKER_FEE_RATE,
            "safety_margin": ARBITRAGE_SAFETY_MARGIN,
        },
        "conclusion": {
            "executable_after_costs_count": len(executable),
            "supports_arbitrage_execution": False,
            "supports_arbitrage_observation": True,
            "summary": (
                "Read-only public data can observe cross-exchange spreads. This report does not prove "
                "execution viability and does not place trades."
            ),
        },
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ARBITRAGE_REPORT_FILE.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observe read-only Kraken/Coinbase cross-exchange spreads.")
    parser.add_argument("--pairs", nargs="+", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(build_arbitrage_report(args.pairs), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
