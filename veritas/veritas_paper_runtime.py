#!/usr/bin/env python3
"""Paper-only Veritas runtime for the 72-hour readiness run.

This module never calls Kraken private order endpoints and never creates live
orders. It reads local candle/account data, produces paper decisions, persists
fake account state, and scores decisions after observation windows mature.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VERITAS_ROOT = Path(__file__).resolve().parent
STATE_DIR = Path(os.environ.get("VERITAS_PAPER_STATE_DIR", VERITAS_ROOT / "paper_state"))
PUBLIC_CANDLE_DIR = Path(os.environ.get("VERITAS_PUBLIC_CANDLE_DIR", VERITAS_ROOT / "public_candles"))
ACCOUNT_STATE_FILE = STATE_DIR / "paper_account_state.json"
DECISIONS_FILE = STATE_DIR / "paper_decisions.jsonl"
SCORES_FILE = STATE_DIR / "paper_scores.jsonl"
REPORT_FILE = STATE_DIR / "paper_report.json"

STARTING_CASH_USD = 500.00
CONFIGURED_PAIRS = ["XRP/USD", "ETH/USD", "SOL/USD", "BTC/USD"]
MAX_ASSET_EXPOSURE_USD = 125.00
MAX_DAILY_LOSS_FRACTION = 0.05
TAKER_FEE_RATE = 0.0040
FEE_GATE_SAFETY_MARGIN = 0.0040
MIN_EXPECTED_EDGE_FRACTION = (TAKER_FEE_RATE * 2.0) + FEE_GATE_SAFETY_MARGIN
SCORING_WINDOWS_SECONDS = {
    "1h": 3600,
    "4h": 4 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
}

ANALOG_TOP_K = 3
ANALOG_DISTANCE_SCALE = 1.35
ANALOG_FEATURE_WEIGHTS = {
    "return": 1.35,
    "range": 0.75,
    "body": 0.75,
    "volume_delta": 0.30,
    "trades_delta": 0.20,
    "cumulative_return": 1.10,
    "realized_volatility": 0.85,
    "average_range": 0.65,
}

PAIR_ALIASES = {
    "BTC/USD": "XBTUSD",
    "XBT/USD": "XBTUSD",
    "XBTUSD": "XBTUSD",
    "BTCUSD": "XBTUSD",
    "ETH/USD": "ETHUSD",
    "ETHUSD": "ETHUSD",
    "SOL/USD": "SOLUSD",
    "SOLUSD": "SOLUSD",
    "XRP/USD": "XRPUSD",
    "XRPUSD": "XRPUSD",
    "MANA/USD": "MANAUSD",
    "MANAUSD": "MANAUSD",
}


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int
    pair: str
    source_file: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_pair(pair: str) -> str:
    cleaned = pair.strip().upper().replace("-", "/")
    if "/" not in cleaned and len(cleaned) == 6 and cleaned.startswith("BTC"):
        cleaned = "BTC/USD"
    return PAIR_ALIASES.get(cleaned, cleaned.replace("/", ""))


def state_dir() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def stable_idempotency_key(pair: str, observed_ts: int, decision: str, price: float) -> str:
    raw = f"{normalize_pair(pair)}|{observed_ts}|{decision}|{price:.8f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_candle_row(row: dict[str, str] | list[str], pair: str, source_file: str) -> Candle:
    if isinstance(row, list):
        if len(row) < 6:
            raise ValueError("headerless Kraken candle row must have at least 6 columns")
        timestamp, open_, high, low, close, volume = row[:6]
        trades = row[6] if len(row) > 6 else 0
    else:
        timestamp = row.get("timestamp") or row.get("time") or row.get("ts")
        open_ = row.get("open") or row.get("o")
        high = row.get("high") or row.get("h")
        low = row.get("low") or row.get("l")
        close = row.get("close") or row.get("c")
        volume = row.get("volume") or row.get("vol") or row.get("v") or 0
        trades = row.get("trades") or row.get("count") or 0
    return Candle(
        timestamp=int(float(timestamp)),
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=float(volume),
        trades=int(float(trades or 0)),
        pair=pair,
        source_file=source_file,
    )


def load_candles(pair: str, search_paths: list[Path] | None = None) -> list[Candle]:
    normalized = normalize_pair(pair)
    paths = search_paths or [PUBLIC_CANDLE_DIR, REPO_ROOT / "data" / "kraken_history", REPO_ROOT / "knowledge"]
    candidates: list[Path] = []
    for base in paths:
        if base.exists():
            candidates = sorted(base.glob(f"{normalized}_*.csv"))
            if candidates:
                break
    if not candidates:
        return []

    preferred = sorted(candidates, key=lambda p: (p.stat().st_size, p.name), reverse=True)[0]
    candles: list[Candle] = []
    with preferred.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        sample = handle.readline()
        handle.seek(0)
        first_cells = [cell.strip().lower() for cell in sample.split(",")]
        has_header = bool(first_cells and first_cells[0] in {"timestamp", "time", "ts"})
        if has_header:
            for row in csv.DictReader(handle):
                try:
                    candles.append(parse_candle_row(row, normalized, str(preferred)))
                except Exception:
                    continue
        else:
            for row in csv.reader(handle):
                if not row:
                    continue
                try:
                    candles.append(parse_candle_row(row, normalized, str(preferred)))
                except Exception:
                    continue
    candles.sort(key=lambda c: c.timestamp)
    return candles


def load_account_state() -> dict[str, Any]:
    state_dir()
    if ACCOUNT_STATE_FILE.exists():
        return json.loads(ACCOUNT_STATE_FILE.read_text(encoding="utf-8"))
    state = {
        "schema": "veritas_paper_account_v1",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "starting_cash_usd": STARTING_CASH_USD,
        "cash_usd": STARTING_CASH_USD,
        "realized_pnl_usd": 0.0,
        "fees_usd": 0.0,
        "positions": {},
        "processed_idempotency_keys": [],
        "last_prices": {},
        "daily": {"date": datetime.now(timezone.utc).date().isoformat(), "starting_equity": STARTING_CASH_USD, "stop_for_day": False},
    }
    save_account_state(state)
    return state


def save_account_state(state: dict[str, Any]) -> None:
    state_dir()
    state["updated_at"] = utc_now()
    tmp = ACCOUNT_STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(ACCOUNT_STATE_FILE)


def equity(state: dict[str, Any], price_by_pair: dict[str, float]) -> float:
    total = float(state.get("cash_usd", 0.0))
    last_prices = state.get("last_prices") or {}
    for pair, position in (state.get("positions") or {}).items():
        mark = price_by_pair.get(pair, last_prices.get(pair, position.get("avg_price", 0.0)))
        total += float(position.get("qty", 0.0)) * float(mark)
    return total


def refresh_daily_state(state: dict[str, Any], current_equity: float) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    daily = state.setdefault("daily", {})
    if daily.get("date") != today:
        state["daily"] = {"date": today, "starting_equity": current_equity, "stop_for_day": False}


def daily_drawdown_hit(state: dict[str, Any], current_equity: float) -> bool:
    daily = state.get("daily") or {}
    start = float(daily.get("starting_equity") or STARTING_CASH_USD)
    if start <= 0:
        return True
    return (start - current_equity) / start >= MAX_DAILY_LOSS_FRACTION or bool(daily.get("stop_for_day"))


def analog_recall(candles: list[Candle], window: int = 8) -> list[dict[str, Any]]:
    if len(candles) < window * 3:
        return []
    recent = candles[-window:]
    candidates: list[tuple[int, list[tuple[str, float]]]] = []
    for idx in range(0, len(candles) - window - 1):
        candidates.append((idx, analog_feature_vector(candles[idx : idx + window])))
    if not candidates:
        return []

    recent_vector = analog_feature_vector(recent)
    scales = analog_feature_scales([vector for _, vector in candidates] + [recent_vector])
    best: list[tuple[float, int, dict[str, float]]] = []
    for idx, vector in candidates:
        dist, parts = analog_feature_distance(recent_vector, vector, scales)
        best.append((dist, idx, parts))
    best.sort(key=lambda item: item[0])
    analogs = []
    recent_information = analog_information_score(recent)
    for rank, (dist, idx, parts) in enumerate(best[:ANALOG_TOP_K], start=1):
        segment = candles[idx : idx + window]
        after = candles[idx + window]
        prior = segment[-1]
        future_return = (after.close - prior.close) / prior.close if prior.close else 0.0
        segment_information = analog_information_score(segment)
        similarity = math.exp(-dist / ANALOG_DISTANCE_SCALE)
        low_information_match = min(recent_information, segment_information) < 0.0005
        if low_information_match:
            similarity = min(similarity, 0.75)
        analogs.append(
            {
                "rank": rank,
                "start_ts": segment[0].timestamp,
                "end_ts": prior.timestamp,
                "distance": round(dist, 6),
                "similarity": round(similarity, 6),
                "feature_distance": {key: round(value, 6) for key, value in parts.items()},
                "recent_information": round(recent_information, 8),
                "analog_information": round(segment_information, 8),
                "low_information_match": low_information_match,
                "next_return": round(future_return, 6),
            }
        )
    return analogs


def analog_feature_vector(candles: list[Candle]) -> list[tuple[str, float]]:
    features: list[tuple[str, float]] = []
    segment_returns = returns(candles)
    for offset, (prev, cur) in enumerate(zip(candles, candles[1:])):
        ret = math.log(cur.close / prev.close) if prev.close > 0 and cur.close > 0 else 0.0
        range_pct = (cur.high - cur.low) / cur.close if cur.close > 0 else 0.0
        body_pct = (cur.close - cur.open) / cur.open if cur.open > 0 else 0.0
        volume_delta = math.log1p(max(cur.volume, 0.0)) - math.log1p(max(prev.volume, 0.0))
        trades_delta = math.log1p(max(cur.trades, 0)) - math.log1p(max(prev.trades, 0))
        features.extend(
            [
                (f"return_{offset}", ret),
                (f"range_{offset}", range_pct),
                (f"body_{offset}", body_pct),
                (f"volume_delta_{offset}", volume_delta),
                (f"trades_delta_{offset}", trades_delta),
            ]
        )
    realized_volatility = math.sqrt(sum(value * value for value in segment_returns) / len(segment_returns)) if segment_returns else 0.0
    average_range = sum((c.high - c.low) / c.close for c in candles if c.close > 0) / len(candles) if candles else 0.0
    features.extend(
        [
            ("cumulative_return", sum(segment_returns)),
            ("realized_volatility", realized_volatility),
            ("average_range", average_range),
        ]
    )
    return features


def analog_feature_scales(vectors: list[list[tuple[str, float]]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for vector in vectors:
        for name, value in vector:
            grouped.setdefault(name, []).append(float(value))
    scales: dict[str, float] = {}
    for name, values in grouped.items():
        sorted_values = sorted(values)
        center = sorted_values[len(sorted_values) // 2]
        deviations = sorted(abs(value - center) for value in sorted_values)
        mad = deviations[len(deviations) // 2] if deviations else 0.0
        floor = max(abs(center) * 0.05, 1e-6)
        scales[name] = max(mad * 1.4826, floor)
    return scales


def analog_weight(feature_name: str) -> float:
    for prefix, weight in ANALOG_FEATURE_WEIGHTS.items():
        if feature_name == prefix or feature_name.startswith(prefix + "_"):
            return weight
    return 1.0


def analog_feature_distance(
    left: list[tuple[str, float]],
    right: list[tuple[str, float]],
    scales: dict[str, float],
) -> tuple[float, dict[str, float]]:
    right_by_name = {name: value for name, value in right}
    weighted_sum = 0.0
    weight_total = 0.0
    parts: dict[str, float] = {}
    part_weights: dict[str, float] = {}
    for name, left_value in left:
        if name not in right_by_name:
            continue
        weight = analog_weight(name)
        scaled = (float(left_value) - float(right_by_name[name])) / scales.get(name, 1.0)
        contribution = weight * scaled * scaled
        weighted_sum += contribution
        weight_total += weight
        group = feature_group(name)
        parts[group] = parts.get(group, 0.0) + contribution
        part_weights[group] = part_weights.get(group, 0.0) + weight
    distance = math.sqrt(weighted_sum / weight_total) if weight_total else 0.0
    grouped = {name: math.sqrt(value / part_weights[name]) for name, value in parts.items() if part_weights.get(name)}
    return distance, grouped


def feature_group(feature_name: str) -> str:
    for prefix in ANALOG_FEATURE_WEIGHTS:
        if feature_name == prefix or feature_name.startswith(prefix + "_"):
            return prefix
    return "other"


def analog_information_score(candles: list[Candle]) -> float:
    segment_returns = returns(candles)
    realized_volatility = math.sqrt(sum(value * value for value in segment_returns) / len(segment_returns)) if segment_returns else 0.0
    average_range = sum((c.high - c.low) / c.close for c in candles if c.close > 0) / len(candles) if candles else 0.0
    cumulative_return = abs(sum(segment_returns))
    return realized_volatility + average_range + cumulative_return


def returns(candles: list[Candle]) -> list[float]:
    values = []
    for prev, cur in zip(candles, candles[1:]):
        values.append((cur.close - prev.close) / prev.close if prev.close else 0.0)
    return values


def decide(pair: str, candles: list[Candle], state: dict[str, Any]) -> dict[str, Any]:
    if not candles:
        return {
            "decision": "WAIT",
            "confidence": 0.0,
            "reason": "No local candle data available.",
            "recalled_analogs": [],
            "risk_notes": ["missing_candle_data"],
        }
    latest = candles[-1]
    price_by_pair = {normalize_pair(pair): latest.close}
    current_equity = equity(state, price_by_pair)
    refresh_daily_state(state, current_equity)
    analogs = analog_recall(candles)
    risk_notes = []
    if daily_drawdown_hit(state, current_equity):
        state["daily"]["stop_for_day"] = True
        return {
            "decision": "WAIT",
            "confidence": 1.0,
            "reason": "Daily paper drawdown limit reached; new BUY decisions are stopped for the day.",
            "recalled_analogs": analogs,
            "risk_notes": ["daily_drawdown_stop"],
        }

    momentum = sum(returns(candles[-6:])) if len(candles) >= 6 else 0.0
    analog_avg = sum(a["next_return"] for a in analogs) / len(analogs) if analogs else 0.0
    score = (momentum * 0.4) + (analog_avg * 0.6)
    confidence = min(0.95, max(0.15, abs(score) * 50))
    position = (state.get("positions") or {}).get(normalize_pair(pair), {"qty": 0.0})
    has_position = float(position.get("qty", 0.0)) > 0
    base_decision = decision_from_score(momentum, has_position)
    if score > 0.002 and not has_position:
        decision = "BUY"
        reason = "Positive recent momentum with supportive analog outcomes."
    elif score < -0.002 and has_position:
        decision = "SELL"
        reason = "Negative recent momentum or analog outcomes while a paper position is open."
    elif abs(score) <= 0.001:
        decision = "HOLD" if has_position else "WAIT"
        reason = "Signal strength is below action threshold."
    else:
        decision = "HOLD" if has_position else "WAIT"
        reason = "Action not justified under current paper risk constraints."
    ungated_decision = decision
    expected_edge = abs(score)
    gate = market_truth_gate(ungated_decision, expected_edge)
    if gate["blocked"]:
        decision = "HOLD" if has_position else "WAIT"
        risk_notes.append("fee_edge_gate_block")
        reason = gate["reason"]
    return {
        "decision": decision,
        "confidence": round(confidence, 4),
        "reason": reason,
        "recalled_analogs": analogs,
        "risk_notes": risk_notes,
        "market_truth_gate": gate,
        "decision_ablation": {
            "base_decision": base_decision,
            "recall_adjusted_decision": decision,
            "pre_gate_decision": ungated_decision,
            "base_score": round(momentum, 8),
            "recall_adjusted_score": round(score, 8),
            "analog_average_return": round(analog_avg, 8),
            "recall_changed_decision": base_decision != decision,
        },
    }


def market_truth_gate(decision: str, expected_edge: float) -> dict[str, Any]:
    round_trip_fee = TAKER_FEE_RATE * 2.0
    required_edge = MIN_EXPECTED_EDGE_FRACTION
    actionable = decision in {"BUY", "SELL"}
    blocked = actionable and expected_edge < required_edge
    return {
        "enabled": True,
        "pre_gate_decision": decision,
        "blocked": blocked,
        "expected_edge": round(float(expected_edge), 8),
        "round_trip_fee": round(round_trip_fee, 8),
        "safety_margin": round(FEE_GATE_SAFETY_MARGIN, 8),
        "required_edge": round(required_edge, 8),
        "reason": (
            "Expected edge does not clear round-trip fees plus safety margin."
            if blocked
            else "Expected edge clears fee gate or decision is non-actionable."
        ),
    }


def decision_from_score(score: float, has_position: bool) -> str:
    if score > 0.002 and not has_position:
        return "BUY"
    if score < -0.002 and has_position:
        return "SELL"
    if abs(score) <= 0.001:
        return "HOLD" if has_position else "WAIT"
    return "HOLD" if has_position else "WAIT"


def apply_paper_decision(state: dict[str, Any], pair: str, price: float, decision: str, confidence: float) -> dict[str, Any]:
    normalized = normalize_pair(pair)
    if decision in {"BUY", "SELL"} and price <= 0:
        return {"result": "BLOCKED_INVALID_PRICE", "fee": 0.0, "simulated_position_size": 0.0}
    price_by_pair = {normalized: price}
    current_equity = equity(state, price_by_pair)
    fee = 0.0
    simulated_position_size = 0.0
    result = "NO_FILL"
    positions = state.setdefault("positions", {})
    pos = positions.setdefault(normalized, {"qty": 0.0, "avg_price": 0.0})
    current_asset_exposure = float(pos.get("qty", 0.0)) * price
    remaining_asset_capacity = max(0.0, MAX_ASSET_EXPOSURE_USD - current_asset_exposure)

    if decision == "BUY":
        if daily_drawdown_hit(state, current_equity):
            state["daily"]["stop_for_day"] = True
            return {"result": "BLOCKED_DAILY_DRAWDOWN", "fee": 0.0, "simulated_position_size": 0.0}
        notional = min(remaining_asset_capacity, float(state.get("cash_usd", 0.0)) / (1.0 + TAKER_FEE_RATE))
        if notional <= 0:
            return {"result": "BLOCKED_ASSET_CAP_OR_CASH", "fee": 0.0, "simulated_position_size": 0.0}
        qty = notional / price
        fee = notional * TAKER_FEE_RATE
        debit = notional + fee
        existing_notional = float(pos["qty"]) * float(pos["avg_price"])
        new_qty = float(pos["qty"]) + qty
        pos["avg_price"] = (existing_notional + notional) / new_qty if new_qty else 0.0
        pos["qty"] = new_qty
        state["cash_usd"] = float(state["cash_usd"]) - debit
        state["fees_usd"] = float(state.get("fees_usd", 0.0)) + fee
        simulated_position_size = notional
        result = "PAPER_BUY_FILLED"
    elif decision == "SELL" and float(pos.get("qty", 0.0)) > 0:
        qty = float(pos["qty"])
        gross = qty * price
        fee = gross * TAKER_FEE_RATE
        realized = (price - float(pos["avg_price"])) * qty - fee
        state["cash_usd"] = float(state["cash_usd"]) + gross - fee
        state["realized_pnl_usd"] = float(state.get("realized_pnl_usd", 0.0)) + realized
        state["fees_usd"] = float(state.get("fees_usd", 0.0)) + fee
        pos["qty"] = 0.0
        pos["avg_price"] = 0.0
        simulated_position_size = gross
        result = "PAPER_SELL_FILLED"

    current_equity_after = equity(state, price_by_pair)
    refresh_daily_state(state, current_equity_after)
    if daily_drawdown_hit(state, current_equity_after):
        state["daily"]["stop_for_day"] = True
    return {"result": result, "fee": round(fee, 8), "simulated_position_size": round(simulated_position_size, 8)}


def observe_once(pair: str) -> dict[str, Any]:
    normalized = normalize_pair(pair)
    candles = load_candles(normalized)
    state = load_account_state()
    before_cash = float(state.get("cash_usd", 0.0))
    latest = candles[-1] if candles else None
    observed_price = float(latest.close) if latest else 0.0
    if observed_price > 0:
        state.setdefault("last_prices", {})[normalized] = observed_price
    decision_core = decide(normalized, candles, state)
    idempotency_key = stable_idempotency_key(
        normalized,
        latest.timestamp if latest else 0,
        decision_core["decision"],
        observed_price,
    )
    processed_keys = set(state.setdefault("processed_idempotency_keys", []))
    if decision_core["decision"] in {"BUY", "SELL"} and idempotency_key in processed_keys:
        execution = {"result": "DUPLICATE_DECISION_SKIPPED", "fee": 0.0, "simulated_position_size": 0.0}
    else:
        execution = apply_paper_decision(
            state,
            normalized,
            observed_price,
            decision_core["decision"],
            float(decision_core["confidence"]),
        )
        if decision_core["decision"] in {"BUY", "SELL"} and execution["result"].startswith("PAPER_"):
            processed_keys.add(idempotency_key)
            state["processed_idempotency_keys"] = sorted(processed_keys)
    save_account_state(state)
    open_position = (state.get("positions") or {}).get(normalized, {"qty": 0.0, "avg_price": 0.0})
    portfolio_equity = equity(state, state.get("last_prices") or {})
    decision_record = {
        "schema": "veritas_paper_decision_v1",
        "record_id": f"VPD-{uuid.uuid4().hex[:16].upper()}",
        "timestamp": utc_now(),
        "observed_ts": latest.timestamp if latest else None,
        "pair": normalized,
        "observed_price": observed_price,
        "decision": decision_core["decision"],
        "confidence": decision_core["confidence"],
        "reason": decision_core["reason"],
        "recalled_analogs": decision_core["recalled_analogs"],
        "decision_ablation": decision_core.get("decision_ablation"),
        "market_truth_gate": decision_core.get("market_truth_gate"),
        "risk_notes": decision_core["risk_notes"],
        "simulated_position_size": execution["simulated_position_size"],
        "execution_result": execution["result"],
        "starting_balance": STARTING_CASH_USD,
        "max_asset_exposure_usd": MAX_ASSET_EXPOSURE_USD,
        "current_cash": round(float(state.get("cash_usd", 0.0)), 8),
        "portfolio_equity": round(portfolio_equity, 8),
        "cash_before": round(before_cash, 8),
        "open_position": open_position,
        "fees": round(float(state.get("fees_usd", 0.0)), 8),
        "idempotency_key": idempotency_key,
        "source_file": latest.source_file if latest else None,
        "live_execution": False,
    }
    append_jsonl(DECISIONS_FILE, decision_record)
    return decision_record


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    state_dir()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def score_decisions() -> dict[str, Any]:
    decisions = read_jsonl(DECISIONS_FILE)
    scored = read_jsonl(SCORES_FILE)
    scored_keys = {(row.get("record_id"), row.get("window")) for row in scored}
    new_scores: list[dict[str, Any]] = []
    candle_cache: dict[str, list[Candle]] = {}
    for decision in decisions:
        pair = decision.get("pair")
        observed_ts = decision.get("observed_ts")
        observed_price = float(decision.get("observed_price") or 0.0)
        if not pair or not observed_ts or observed_price <= 0:
            continue
        candles = candle_cache.setdefault(pair, load_candles(pair))
        for label, seconds in SCORING_WINDOWS_SECONDS.items():
            key = (decision.get("record_id"), label)
            if key in scored_keys:
                continue
            target_ts = int(observed_ts) + seconds
            future = next((c for c in candles if c.timestamp >= target_ts), None)
            if not future:
                continue
            ret = (future.close - observed_price) / observed_price
            direction = decision.get("decision")
            missed_upside = max(0.0, ret)
            avoided_downside = max(0.0, -ret)
            if direction == "SELL":
                directional_return = -ret
                win = directional_return > 0
                score_type = "trade"
                abstention_quality = None
            elif direction == "BUY":
                directional_return = ret
                win = directional_return > 0
                score_type = "trade"
                abstention_quality = None
            else:
                directional_return = None
                win = None
                score_type = "abstention"
                abstention_quality = round(avoided_downside - missed_upside, 8)
            score = {
                "schema": "veritas_paper_score_v1",
                "score_type": score_type,
                "record_id": decision.get("record_id"),
                "pair": pair,
                "decision": direction,
                "window": label,
                "observed_ts": observed_ts,
                "score_ts": future.timestamp,
                "observed_price": observed_price,
                "future_price": future.close,
                "future_return": round(ret, 8),
                "raw_return": round(ret, 8),
                "directional_return": round(directional_return, 8) if directional_return is not None else None,
                "missed_upside": round(missed_upside, 8),
                "avoided_downside": round(avoided_downside, 8),
                "abstention_quality": abstention_quality,
                "win": win,
                "confidence": decision.get("confidence"),
                "recalled_analogs_count": len(decision.get("recalled_analogs") or []),
                "scored_at": utc_now(),
            }
            append_jsonl(SCORES_FILE, score)
            new_scores.append(score)
    return {"new_scores": len(new_scores), "total_scores": len(scored) + len(new_scores)}


def score_missed_upside(row: dict[str, Any]) -> float:
    if row.get("missed_upside") is not None:
        return float(row.get("missed_upside") or 0.0)
    if row.get("decision") in {"HOLD", "WAIT"}:
        return max(0.0, float(row.get("raw_return") or row.get("future_return") or 0.0))
    return 0.0


def score_avoided_downside(row: dict[str, Any]) -> float:
    if row.get("avoided_downside") is not None:
        return float(row.get("avoided_downside") or 0.0)
    if row.get("decision") in {"HOLD", "WAIT"}:
        return max(0.0, -float(row.get("raw_return") or row.get("future_return") or 0.0))
    return 0.0


def score_abstention_quality(row: dict[str, Any]) -> float:
    if row.get("abstention_quality") is not None:
        return float(row.get("abstention_quality") or 0.0)
    return score_avoided_downside(row) - score_missed_upside(row)


def build_report() -> dict[str, Any]:
    score_decisions()
    decisions = read_jsonl(DECISIONS_FILE)
    scores = read_jsonl(SCORES_FILE)
    state = load_account_state()
    grouped: dict[str, list[dict[str, Any]]] = {label: [] for label in SCORING_WINDOWS_SECONDS}
    for score in scores:
        grouped.setdefault(score.get("window"), []).append(score)
    window_reports = {}
    for label, rows in grouped.items():
        trade_rows = [row for row in rows if row.get("decision") in {"BUY", "SELL"}]
        abstention_rows = [row for row in rows if row.get("decision") in {"HOLD", "WAIT"}]
        wins = [row for row in trade_rows if row.get("win")]
        returns_ = [float(row.get("directional_return") or 0.0) for row in trade_rows]
        abstention_quality = [score_abstention_quality(row) for row in abstention_rows]
        window_reports[label] = {
            "scored": len(rows),
            "trade_scored": len(trade_rows),
            "abstention_scored": len(abstention_rows),
            "wins": len(wins),
            "losses": len(trade_rows) - len(wins),
            "trade_win_rate": round(len(wins) / len(trade_rows), 4) if trade_rows else 0.0,
            "average_return": round(sum(returns_) / len(returns_), 8) if returns_ else 0.0,
            "average_abstention_quality": round(sum(abstention_quality) / len(abstention_quality), 8) if abstention_quality else 0.0,
            "missed_upside": round(sum(score_missed_upside(row) for row in abstention_rows), 8),
            "avoided_downside": round(sum(score_avoided_downside(row) for row in abstention_rows), 8),
        }
    trade_scores = [row for row in scores if row.get("decision") in {"BUY", "SELL"}]
    abstention_scores = [row for row in scores if row.get("decision") in {"HOLD", "WAIT"}]
    best = sorted(trade_scores, key=lambda row: float(row.get("directional_return") or 0.0), reverse=True)[:3]
    worst = sorted(trade_scores, key=lambda row: float(row.get("directional_return") or 0.0))[:3]
    with_analogs = [row for row in scores if int(row.get("recalled_analogs_count") or 0) > 0]
    analog_wins = [row for row in with_analogs if row.get("win")]
    current_price_by_pair = {}
    for pair in set((state.get("positions") or {}).keys()) | {normalize_pair(pair) for pair in CONFIGURED_PAIRS}:
        candles = load_candles(pair)
        if candles:
            current_price_by_pair[pair] = candles[-1].close
    current_equity = equity(state, current_price_by_pair)
    asset_reports = build_asset_reports(state, decisions, scores, current_price_by_pair)
    report = {
        "generated_at": utc_now(),
        "paper_only": True,
        "live_trading_enabled": False,
        "starting_cash_usd": STARTING_CASH_USD,
        "current_cash_usd": round(float(state.get("cash_usd", 0.0)), 8),
        "equity_usd": round(current_equity, 8),
        "realized_pnl_usd": round(float(state.get("realized_pnl_usd", 0.0)), 8),
        "fees_usd": round(float(state.get("fees_usd", 0.0)), 8),
        "open_positions": state.get("positions") or {},
        "asset_reports": asset_reports,
        "decisions": len(decisions),
        "scores": len(scores),
        "trade_scores": len(trade_scores),
        "abstention_scores": len(abstention_scores),
        "windows": window_reports,
        "max_drawdown": estimate_max_drawdown(decisions),
        "confidence_calibration": confidence_calibration(scores),
        "analog_similarity": analog_similarity_summary(decisions),
        "are_recall_impact": recall_impact_report(decisions, scores),
        "market_truth_gate": market_truth_gate_summary(decisions),
        "money_readiness": money_readiness_report(decisions, scores),
        "best_decisions": best,
        "worst_decisions": worst,
        "abstention_quality": build_abstention_quality(abstention_scores),
        "are_recall_helped_examples": analog_wins[:3],
        "are_recall_failed_examples": [row for row in with_analogs if not row.get("win")][:3],
        "synthetic_fallback_used": False,
    }
    state_dir()
    REPORT_FILE.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def analog_similarity_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[float] = []
    examples = {"high": [], "medium": [], "low": []}
    for row in decisions:
        for analog in row.get("recalled_analogs") or []:
            try:
                value = float(analog.get("similarity"))
            except Exception:
                continue
            values.append(value)
            example = {
                "record_id": row.get("record_id"),
                "pair": row.get("pair"),
                "decision": row.get("decision"),
                "similarity": round(value, 6),
                "distance": analog.get("distance"),
                "next_return": analog.get("next_return"),
                "start_ts": analog.get("start_ts"),
                "end_ts": analog.get("end_ts"),
            }
            if value >= 0.90 and len(examples["high"]) < 5:
                examples["high"].append(example)
            elif 0.70 <= value < 0.90 and len(examples["medium"]) < 5:
                examples["medium"].append(example)
            elif value < 0.70 and len(examples["low"]) < 5:
                examples["low"].append(example)
    values.sort()
    return {
        "count": len(values),
        "min": round(values[0], 8) if values else None,
        "max": round(values[-1], 8) if values else None,
        "mean": round(mean(values), 8) if values else None,
        "median": round(median(values), 8) if values else None,
        "percent_above_0_99": round(percent_above(values, 0.99), 6),
        "percent_above_0_95": round(percent_above(values, 0.95), 6),
        "percent_above_0_90": round(percent_above(values, 0.90), 6),
        "percentile_buckets": {
            "lt_0_50": sum(1 for value in values if value < 0.50),
            "0_50_to_0_70": sum(1 for value in values if 0.50 <= value < 0.70),
            "0_70_to_0_90": sum(1 for value in values if 0.70 <= value < 0.90),
            "0_90_to_0_95": sum(1 for value in values if 0.90 <= value < 0.95),
            "0_95_to_0_99": sum(1 for value in values if 0.95 <= value <= 0.99),
            "gt_0_99": sum(1 for value in values if value > 0.99),
        },
        "examples": examples,
    }


def percent_above(values: list[float], threshold: float) -> float:
    return (sum(1 for value in values if value > threshold) / len(values)) if values else 0.0


def recall_impact_report(decisions: list[dict[str, Any]], scores: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row.get("record_id"): row for row in decisions}
    changed_decisions = [
        row for row in decisions if (row.get("decision_ablation") or {}).get("recall_changed_decision") is True
    ]
    changed_ids = {row.get("record_id") for row in changed_decisions}
    trade_scores = [row for row in scores if row.get("decision") in {"BUY", "SELL"} and row.get("directional_return") is not None]
    changed_pnl: list[float] = []
    unchanged_pnl: list[float] = []
    for score in trade_scores:
        decision = by_id.get(score.get("record_id")) or {}
        notional = float(decision.get("simulated_position_size") or 0.0)
        pnl = notional * float(score.get("directional_return") or 0.0)
        if score.get("record_id") in changed_ids:
            changed_pnl.append(pnl)
        else:
            unchanged_pnl.append(pnl)
    return {
        "changed_decision_count": len(changed_decisions),
        "changed_decision_fraction": round(len(changed_decisions) / len(decisions), 6) if decisions else 0.0,
        "are_helped_pnl_usd": round(sum(value for value in changed_pnl if value > 0), 8),
        "are_hurt_pnl_usd": round(sum(value for value in changed_pnl if value < 0), 8),
        "net_pnl_when_recall_changed_usd": round(sum(changed_pnl), 8),
        "net_pnl_when_recall_unchanged_usd": round(sum(unchanged_pnl), 8),
        "average_pnl_when_recall_changed_usd": round(sum(changed_pnl) / len(changed_pnl), 8) if changed_pnl else 0.0,
        "average_pnl_when_recall_unchanged_usd": round(sum(unchanged_pnl) / len(unchanged_pnl), 8) if unchanged_pnl else 0.0,
        "trade_score_count_when_recall_changed": len(changed_pnl),
        "trade_score_count_when_recall_unchanged": len(unchanged_pnl),
    }


def market_truth_gate_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    gated = [row for row in decisions if isinstance(row.get("market_truth_gate"), dict)]
    blocked = [row for row in gated if row["market_truth_gate"].get("blocked")]
    cleared = [
        row
        for row in gated
        if row["market_truth_gate"].get("pre_gate_decision") in {"BUY", "SELL"}
        and not row["market_truth_gate"].get("blocked")
    ]
    expected_edges = [float(row["market_truth_gate"].get("expected_edge") or 0.0) for row in gated]
    blocked_by_pair: dict[str, int] = {}
    blocked_by_action: dict[str, int] = {}
    examples = []
    for row in blocked:
        gate = row["market_truth_gate"]
        pair = str(row.get("pair"))
        action = str(gate.get("pre_gate_decision"))
        blocked_by_pair[pair] = blocked_by_pair.get(pair, 0) + 1
        blocked_by_action[action] = blocked_by_action.get(action, 0) + 1
    for row in blocked[:10]:
        gate = row["market_truth_gate"]
        examples.append(
            {
                "record_id": row.get("record_id"),
                "pair": row.get("pair"),
                "pre_gate_decision": gate.get("pre_gate_decision"),
                "final_decision": row.get("decision"),
                "expected_edge": gate.get("expected_edge"),
                "required_edge": gate.get("required_edge"),
                "observed_price": row.get("observed_price"),
            }
        )
    return {
        "enabled": True,
        "required_edge": round(MIN_EXPECTED_EDGE_FRACTION, 8),
        "round_trip_fee": round(TAKER_FEE_RATE * 2.0, 8),
        "safety_margin": round(FEE_GATE_SAFETY_MARGIN, 8),
        "gated_decisions": len(gated),
        "blocked_actionable_decisions": len(blocked),
        "cleared_actionable_decisions": len(cleared),
        "blocked_fraction": round(len(blocked) / len(gated), 6) if gated else 0.0,
        "average_expected_edge": round(sum(expected_edges) / len(expected_edges), 8) if expected_edges else 0.0,
        "blocked_by_pair": dict(sorted(blocked_by_pair.items())),
        "blocked_by_pre_gate_action": dict(sorted(blocked_by_action.items())),
        "blocked_examples": examples,
    }


def money_readiness_report(decisions: list[dict[str, Any]], scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize whether the paper run has shown evidence worth monetizing.

    This is deliberately a report-only layer. It does not relax the fee gate,
    change sizing, or create live execution.
    """
    actionable_pre_gate = [
        row
        for row in decisions
        if isinstance(row.get("market_truth_gate"), dict)
        and row["market_truth_gate"].get("pre_gate_decision") in {"BUY", "SELL"}
    ]
    fee_survivors = [row for row in actionable_pre_gate if not row["market_truth_gate"].get("blocked")]
    blocked = [row for row in actionable_pre_gate if row["market_truth_gate"].get("blocked")]
    near_misses = sorted(
        blocked,
        key=lambda row: float(row["market_truth_gate"].get("required_edge") or 0.0)
        - float(row["market_truth_gate"].get("expected_edge") or 0.0),
    )[:10]
    trade_scores = [row for row in scores if row.get("decision") in {"BUY", "SELL"} and row.get("directional_return") is not None]
    net_trade_returns = [float(row.get("directional_return") or 0.0) - (TAKER_FEE_RATE * 2.0) for row in trade_scores]
    net_wins = [value for value in net_trade_returns if value > 0]
    abstention_scores = [row for row in scores if row.get("decision") in {"HOLD", "WAIT"}]
    missed_by_pair: dict[str, float] = {}
    avoided_by_pair: dict[str, float] = {}
    scored_by_pair: dict[str, int] = {}
    for row in abstention_scores:
        pair = str(row.get("pair"))
        scored_by_pair[pair] = scored_by_pair.get(pair, 0) + 1
        missed_by_pair[pair] = missed_by_pair.get(pair, 0.0) + score_missed_upside(row)
        avoided_by_pair[pair] = avoided_by_pair.get(pair, 0.0) + score_avoided_downside(row)
    pair_opportunities = []
    for pair, missed in missed_by_pair.items():
        avoided = avoided_by_pair.get(pair, 0.0)
        pair_opportunities.append(
            {
                "pair": pair,
                "abstention_scores": scored_by_pair.get(pair, 0),
                "missed_upside": round(missed, 8),
                "avoided_downside": round(avoided, 8),
                "net_abstention_quality": round(avoided - missed, 8),
            }
        )
    pair_opportunities.sort(key=lambda row: row["missed_upside"], reverse=True)
    survivor_examples = []
    for row in fee_survivors[:10]:
        gate = row["market_truth_gate"]
        survivor_examples.append(
            {
                "record_id": row.get("record_id"),
                "pair": row.get("pair"),
                "pre_gate_decision": gate.get("pre_gate_decision"),
                "expected_edge": gate.get("expected_edge"),
                "required_edge": gate.get("required_edge"),
                "observed_price": row.get("observed_price"),
            }
        )
    near_miss_examples = []
    for row in near_misses:
        gate = row["market_truth_gate"]
        expected = float(gate.get("expected_edge") or 0.0)
        required = float(gate.get("required_edge") or 0.0)
        near_miss_examples.append(
            {
                "record_id": row.get("record_id"),
                "pair": row.get("pair"),
                "pre_gate_decision": gate.get("pre_gate_decision"),
                "expected_edge": gate.get("expected_edge"),
                "required_edge": gate.get("required_edge"),
                "edge_gap": round(required - expected, 8),
                "observed_price": row.get("observed_price"),
            }
        )
    if not fee_survivors:
        status = "no_after_fee_edge_proven"
        next_step = "Keep paper-only collection running and use missed-upside/near-miss data before changing strategy thresholds."
    elif not trade_scores:
        status = "fee_survivors_seen_but_not_scored_yet"
        next_step = "Wait for scoring windows to mature before trusting any candidate edge."
    elif net_trade_returns and (sum(net_trade_returns) / len(net_trade_returns)) > 0 and len(net_wins) / len(net_trade_returns) > 0.5:
        status = "paper_edge_candidate"
        next_step = "Continue paper-only validation on fresh data; do not enable live trading until results persist across regimes."
    else:
        status = "trade_candidates_not_profitable_after_fee_model"
        next_step = "Do not optimize execution yet; identify which features separate winners from losers after fees."
    return {
        "status": status,
        "paper_only": True,
        "live_trading_enabled": False,
        "required_edge": round(MIN_EXPECTED_EDGE_FRACTION, 8),
        "round_trip_fee": round(TAKER_FEE_RATE * 2.0, 8),
        "actionable_pre_gate_decisions": len(actionable_pre_gate),
        "fee_surviving_pre_gate_decisions": len(fee_survivors),
        "fee_blocked_pre_gate_decisions": len(blocked),
        "trade_scores": len(trade_scores),
        "estimated_average_trade_return_after_round_trip_fee": round(sum(net_trade_returns) / len(net_trade_returns), 8)
        if net_trade_returns
        else 0.0,
        "estimated_after_fee_win_rate": round(len(net_wins) / len(net_trade_returns), 4) if net_trade_returns else 0.0,
        "top_fee_survivor_examples": survivor_examples,
        "closest_fee_gate_near_misses": near_miss_examples,
        "top_missed_upside_pairs": pair_opportunities[:10],
        "next_step": next_step,
        "note": "Diagnostic only. This report does not place orders or change strategy rules.",
    }


def estimate_max_drawdown(decisions: list[dict[str, Any]]) -> float:
    has_logged_equity = any(row.get("portfolio_equity") is not None for row in decisions)
    equities = reconstruct_equity_curve(decisions, cap_legacy_peak=not has_logged_equity)
    if not equities:
        return 0.0
    peak = equities[0]
    drawdown = 0.0
    for value in equities:
        peak = max(peak, value)
        if peak:
            drawdown = max(drawdown, (peak - value) / peak)
    return round(drawdown, 8)


def reconstruct_equity_curve(decisions: list[dict[str, Any]], cap_legacy_peak: bool = False) -> list[float]:
    last_prices: dict[str, float] = {}
    positions: dict[str, dict[str, float]] = {}
    curve = []
    for row in decisions:
        if row.get("portfolio_equity") is not None:
            try:
                curve.append(float(row["portfolio_equity"]))
                continue
            except Exception:
                pass
        pair = str(row.get("pair"))
        if row.get("observed_price"):
            last_prices[pair] = float(row["observed_price"])
        if pair and isinstance(row.get("open_position"), dict):
            pos = row["open_position"]
            positions[pair] = {"qty": float(pos.get("qty") or 0.0), "avg_price": float(pos.get("avg_price") or 0.0)}
        cash = float(row.get("current_cash") or STARTING_CASH_USD)
        marked = 0.0
        for p, pos in positions.items():
            marked += float(pos.get("qty") or 0.0) * last_prices.get(p, float(pos.get("avg_price") or 0.0))
        value = cash + marked
        if cap_legacy_peak:
            value = min(value, STARTING_CASH_USD)
        curve.append(value)
    return curve


def confidence_calibration(scores: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {"low": [], "medium": [], "high": []}
    for score in scores:
        confidence = float(score.get("confidence") or 0.0)
        if confidence < 0.34:
            buckets["low"].append(score)
        elif confidence < 0.67:
            buckets["medium"].append(score)
        else:
            buckets["high"].append(score)
    return {
        key: {
            "count": len(rows),
            "win_rate": round(sum(1 for row in rows if row.get("win")) / len(rows), 4) if rows else 0.0,
        }
        for key, rows in buckets.items()
    }


def build_asset_reports(
    state: dict[str, Any],
    decisions: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    current_price_by_pair: dict[str, float],
) -> dict[str, dict[str, Any]]:
    normalized_pairs = [normalize_pair(pair) for pair in CONFIGURED_PAIRS]
    positions = state.get("positions") or {}
    reports: dict[str, dict[str, Any]] = {}
    for pair in normalized_pairs:
        position = positions.get(pair, {"qty": 0.0, "avg_price": 0.0})
        qty = float(position.get("qty", 0.0))
        price = float(current_price_by_pair.get(pair, position.get("avg_price", 0.0)))
        exposure = qty * price
        pair_decisions = [row for row in decisions if row.get("pair") == pair]
        pair_scores = [row for row in scores if row.get("pair") == pair]
        trade_scores = [row for row in pair_scores if row.get("decision") in {"BUY", "SELL"}]
        abstention_scores = [row for row in pair_scores if row.get("decision") in {"HOLD", "WAIT"}]
        wins = [row for row in trade_scores if row.get("win")]
        returns_ = [float(row.get("directional_return") or 0.0) for row in trade_scores]
        abstention_quality = [score_abstention_quality(row) for row in abstention_scores]
        reports[pair] = {
            "configured": True,
            "exposure_usd": round(exposure, 8),
            "max_exposure_usd": MAX_ASSET_EXPOSURE_USD,
            "qty": qty,
            "avg_price": float(position.get("avg_price", 0.0)),
            "last_price": price,
            "decisions": len(pair_decisions),
            "scores": len(pair_scores),
            "trade_scores": len(trade_scores),
            "abstention_scores": len(abstention_scores),
            "wins": len(wins),
            "losses": len(trade_scores) - len(wins),
            "trade_win_rate": round(len(wins) / len(trade_scores), 4) if trade_scores else 0.0,
            "average_return": round(sum(returns_) / len(returns_), 8) if returns_ else 0.0,
            "average_abstention_quality": round(sum(abstention_quality) / len(abstention_quality), 8) if abstention_quality else 0.0,
            "missed_upside": round(sum(score_missed_upside(row) for row in abstention_scores), 8),
            "avoided_downside": round(sum(score_avoided_downside(row) for row in abstention_scores), 8),
        }
    return reports


def build_abstention_quality(scores: list[dict[str, Any]]) -> dict[str, Any]:
    quality = [score_abstention_quality(row) for row in scores]
    return {
        "count": len(scores),
        "average_abstention_quality": round(sum(quality) / len(quality), 8) if quality else 0.0,
        "missed_upside": round(sum(score_missed_upside(row) for row in scores), 8),
        "avoided_downside": round(sum(score_avoided_downside(row) for row in scores), 8),
        "note": "HOLD/WAIT are abstentions and are not counted as directional trade losses.",
    }


def account_history_summary(account_dir: Path | None = None) -> dict[str, Any]:
    base = account_dir or VERITAS_ROOT / "account_history"
    rows = []
    if base.exists():
        for path in sorted(base.glob("*.jsonl")):
            rows.extend(read_jsonl(path))
    counts = {"orders": 0, "fills": 0, "ledger_entries": 0, "balances": 0}
    fees = 0.0
    deposits_withdrawals = 0
    times = []
    for row in rows:
        endpoint = row.get("endpoint")
        record = row.get("record") or {}
        if endpoint == "ClosedOrders":
            counts["orders"] += 1
        elif endpoint == "TradesHistory":
            counts["fills"] += 1
            try:
                fees += float(record.get("fee") or 0.0)
            except Exception:
                pass
        elif endpoint == "Ledgers":
            counts["ledger_entries"] += 1
            ledger_type = str(record.get("type") or "").lower()
            if ledger_type in {"deposit", "withdrawal"}:
                deposits_withdrawals += 1
            try:
                fees += float(record.get("fee") or 0.0)
            except Exception:
                pass
        elif endpoint == "Balance":
            counts["balances"] += 1
        try:
            if "time" in record:
                times.append(float(record["time"]))
        except Exception:
            pass
    return {
        "present": bool(rows),
        "records": len(rows),
        "date_range": {
            "start": datetime.fromtimestamp(min(times), timezone.utc).isoformat() if times else None,
            "end": datetime.fromtimestamp(max(times), timezone.utc).isoformat() if times else None,
        },
        "orders": counts["orders"],
        "fills": counts["fills"],
        "ledger_entries": counts["ledger_entries"],
        "balances": counts["balances"],
        "fees_total": round(fees, 8),
        "deposits_withdrawals_detected": deposits_withdrawals,
    }


def candle_data_summary() -> dict[str, Any]:
    paths = [PUBLIC_CANDLE_DIR, REPO_ROOT / "data" / "kraken_history", REPO_ROOT / "knowledge"]
    files = []
    for base in paths:
        if base.exists():
            files.extend(path for path in base.glob("*.csv") if path.is_file())
    sample_pairs = {}
    for path in files[:2000]:
        pair = path.name.split("_", 1)[0]
        sample_pairs[pair] = sample_pairs.get(pair, 0) + 1
    fresh_files = list(PUBLIC_CANDLE_DIR.glob("*.csv")) if PUBLIC_CANDLE_DIR.exists() else []
    configured = {}
    for pair in CONFIGURED_PAIRS:
        normalized = normalize_pair(pair)
        matches = list(PUBLIC_CANDLE_DIR.glob(f"{normalized}_*.csv")) if PUBLIC_CANDLE_DIR.exists() else []
        configured[pair] = {
            "normalized_pair": normalized,
            "fresh_public_candle_present": bool(matches),
            "fresh_public_candle_files": [str(path) for path in sorted(matches)],
        }
    return {
        "present": bool(files),
        "files": len(files),
        "fresh_public_candle_files": len(fresh_files),
        "fresh_public_candle_dir": str(PUBLIC_CANDLE_DIR),
        "configured_pairs": configured,
        "sample_pairs": dict(sorted(sample_pairs.items())[:20]),
    }


def readiness_report() -> dict[str, Any]:
    history = account_history_summary()
    candles = candle_data_summary()
    backtest_report = VERITAS_ROOT / ".veritas_backtest_report.json"
    synthetic = True
    if backtest_report.exists():
        try:
            synthetic = json.loads(backtest_report.read_text(encoding="utf-8")).get("data_source") == "synthetic_fallback"
        except Exception:
            synthetic = True
    return {
        "generated_at": utc_now(),
        "real_account_history_present": history["present"],
        "date_range_covered": history["date_range"],
        "number_of_orders": history["orders"],
        "number_of_fills": history["fills"],
        "number_of_ledger_entries": history["ledger_entries"],
        "fees_total": history["fees_total"],
        "deposits_withdrawals_detected": history["deposits_withdrawals_detected"],
        "candle_data_present": candles["present"],
        "candle_files": candles["files"],
        "fresh_public_candle_files": candles["fresh_public_candle_files"],
        "fresh_public_candle_dir": candles["fresh_public_candle_dir"],
        "configured_pairs": candles["configured_pairs"],
        "synthetic_fallback_used": synthetic,
        "live_trading_enabled": False,
        "readiness_status": "backtest ready" if candles["present"] else "paper only",
        "live_status": "live not implemented",
        "paper_account": {
            "starting_cash_usd": STARTING_CASH_USD,
            "max_asset_exposure_usd": MAX_ASSET_EXPOSURE_USD,
            "max_daily_loss_fraction": MAX_DAILY_LOSS_FRACTION,
            "state_file": str(ACCOUNT_STATE_FILE),
            "decision_log": str(DECISIONS_FILE),
        },
    }
