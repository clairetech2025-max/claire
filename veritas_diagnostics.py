#!/usr/bin/env python3
"""Diagnostics for Veritas paper scoring validity.

This command is read-only. It does not fetch market data, place orders, alter
paper state, or tune strategy thresholds.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median, mean, pstdev
from typing import Any

from veritas.veritas_paper_runtime import (
    DECISIONS_FILE,
    MAX_ASSET_EXPOSURE_USD,
    SCORES_FILE,
    STARTING_CASH_USD,
    TAKER_FEE_RATE,
    analog_recall,
    decision_from_score,
    load_candles,
    load_account_state,
    normalize_pair,
    reconstruct_equity_curve,
    returns,
    score_abstention_quality,
    score_avoided_downside,
    score_missed_upside,
)
from veritas.faiss_analog import faiss_status
from veritas.kraken_microstructure import MICROSTRUCTURE_REPORT_FILE


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def grouped_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key)) for row in rows).items()))


def win_rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    trade_rows = [row for row in rows if row.get("decision") in {"BUY", "SELL"}]
    wins = sum(1 for row in trade_rows if row.get("win") is True)
    losses = sum(1 for row in trade_rows if row.get("win") is False)
    total = wins + losses
    return {"wins": wins, "losses": losses, "trade_scored": total, "trade_win_rate": round(wins / total, 6) if total else 0.0}


def abstention_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    abstentions = [row for row in rows if row.get("decision") in {"HOLD", "WAIT"}]
    quality = [score_abstention_quality(row) for row in abstentions]
    return {
        "abstention_scored": len(abstentions),
        "missed_upside": round(sum(score_missed_upside(row) for row in abstentions), 8),
        "avoided_downside": round(sum(score_avoided_downside(row) for row in abstentions), 8),
        "average_abstention_quality": round(sum(quality) / len(quality), 8) if quality else 0.0,
    }


def nested_win_rate(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key))].append(row)
    return {group: win_rate(items) for group, items in sorted(groups.items())}


def confidence_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {"low": 0, "medium": 0, "high": 0}
    values = []
    for row in rows:
        confidence = float(row.get("confidence") or 0.0)
        values.append(confidence)
        if confidence < 0.34:
            buckets["low"] += 1
        elif confidence < 0.67:
            buckets["medium"] += 1
        else:
            buckets["high"] += 1
    return {
        "buckets": buckets,
        "min": round(min(values), 6) if values else None,
        "max": round(max(values), 6) if values else None,
        "average": round(mean(values), 6) if values else None,
        "medium_threshold": 0.34,
        "high_threshold": 0.67,
    }


def average_confidence_by(rows: list[dict[str, Any]], *keys: str) -> dict[str, float]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        name = "|".join(str(row.get(key)) for key in keys)
        groups[name].append(float(row.get("confidence") or 0.0))
    return {group: round(mean(values), 6) for group, values in sorted(groups.items()) if values}


def analog_similarity_stats(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    values = []
    by_pair: dict[str, list[float]] = defaultdict(list)
    examples = {"high": [], "medium": [], "low": []}
    for row in decisions:
        for analog in row.get("recalled_analogs") or []:
            try:
                value = float(analog.get("similarity"))
            except Exception:
                continue
            values.append(value)
            by_pair[str(row.get("pair"))].append(value)
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
            if value >= 0.90 and len(examples["high"]) < 10:
                examples["high"].append(example)
            elif 0.70 <= value < 0.90 and len(examples["medium"]) < 10:
                examples["medium"].append(example)
            elif value < 0.70 and len(examples["low"]) < 10:
                examples["low"].append(example)
    above_90 = sum(1 for value in values if value > 0.90)
    above_95 = sum(1 for value in values if value > 0.95)
    above_99 = sum(1 for value in values if value > 0.99)
    return {
        "count": len(values),
        "min": round(min(values), 8) if values else None,
        "max": round(max(values), 8) if values else None,
        "mean": round(mean(values), 8) if values else None,
        "average": round(mean(values), 8) if values else None,
        "median": round(median(values), 8) if values else None,
        "stddev": round(pstdev(values), 10) if len(values) > 1 else 0.0,
        "unique_rounded_6dp": len({round(value, 6) for value in values}),
        "near_one_count": sum(1 for value in values if value >= 0.99999),
        "above_0_90_count": above_90,
        "above_0_95_count": above_95,
        "above_0_99_count": above_99,
        "above_0_90_fraction": round(above_90 / len(values), 6) if values else 0.0,
        "above_0_95_fraction": round(above_95 / len(values), 6) if values else 0.0,
        "above_0_99_fraction": round(above_99 / len(values), 6) if values else 0.0,
        "distribution": {
            "lt_0_50": sum(1 for value in values if value < 0.50),
            "0_50_to_0_70": sum(1 for value in values if 0.50 <= value < 0.70),
            "0_70_to_0_90": sum(1 for value in values if 0.70 <= value < 0.90),
            "lt_0_90": sum(1 for value in values if value < 0.90),
            "0_90_to_0_95": sum(1 for value in values if 0.90 <= value < 0.95),
            "0_95_to_0_99": sum(1 for value in values if 0.95 <= value <= 0.99),
            "gt_0_99": sum(1 for value in values if value > 0.99),
            "gte_0_999": sum(1 for value in values if value >= 0.999),
            "gte_0_9999": sum(1 for value in values if value >= 0.9999),
            "gte_0_99999": sum(1 for value in values if value >= 0.99999),
        },
        "examples": examples,
        "by_pair": {
            pair: {
                "count": len(vals),
                "average": round(mean(vals), 8),
                "median": round(median(vals), 8),
                "min": round(min(vals), 8),
                "max": round(max(vals), 8),
                "above_0_90_fraction": round(sum(1 for value in vals if value > 0.90) / len(vals), 6),
                "above_0_95_fraction": round(sum(1 for value in vals if value > 0.95) / len(vals), 6),
                "above_0_99_fraction": round(sum(1 for value in vals if value > 0.99) / len(vals), 6),
                "unique_rounded_6dp": len({round(value, 6) for value in vals}),
            }
            for pair, vals in sorted(by_pair.items())
        },
    }


def filled_trade_events(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    previous_fee_total = 0.0
    for row in decisions:
        fee_total = float(row.get("fees") or 0.0)
        fee_delta = max(0.0, fee_total - previous_fee_total)
        previous_fee_total = fee_total
        if row.get("execution_result") in {"PAPER_BUY_FILLED", "PAPER_SELL_FILLED"}:
            event = dict(row)
            event["fee_delta"] = round(fee_delta, 10)
            events.append(event)
    return events


def trading_edge_report(decisions: list[dict[str, Any]], scores: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    fills = filled_trade_events(decisions)
    trade_scores = [row for row in scores if row.get("decision") in {"BUY", "SELL"}]
    gross_returns = [float(row.get("directional_return") or 0.0) for row in trade_scores]
    total_fees = float(state.get("fees_usd") or 0.0)
    current_equity = exposure_summary(state, decisions)["portfolio_equity_estimate"]
    net_after_fees = current_equity - STARTING_CASH_USD
    net_before_fees = net_after_fees + total_fees
    avg_notional = mean([float(row.get("simulated_position_size") or 0.0) for row in fills]) if fills else 0.0
    avg_fee = total_fees / len(fills) if fills else 0.0
    return {
        "net_pnl_before_fees_usd": round(net_before_fees, 8),
        "net_pnl_after_fees_usd": round(net_after_fees, 8),
        "fees_usd": round(total_fees, 8),
        "filled_trade_events": len(fills),
        "average_gross_return_per_scored_trade": round(mean(gross_returns), 8) if gross_returns else 0.0,
        "average_fee_per_filled_trade_usd": round(avg_fee, 8),
        "average_filled_notional_usd": round(avg_notional, 8),
        "minimum_required_edge_per_fill_fraction": TAKER_FEE_RATE,
        "minimum_required_edge_per_round_trip_fraction": round(TAKER_FEE_RATE * 2, 8),
        "minimum_required_edge_per_round_trip_percent": round(TAKER_FEE_RATE * 2 * 100, 4),
    }


def action_return_report(scores: list[dict[str, Any]]) -> dict[str, Any]:
    report = {}
    for action in ["BUY", "SELL"]:
        rows = [row for row in scores if row.get("decision") == action and row.get("directional_return") is not None]
        wins = sum(1 for row in rows if row.get("win") is True)
        returns_ = [float(row.get("directional_return") or 0.0) for row in rows]
        report[action] = {
            "trade_scored": len(rows),
            "wins": wins,
            "losses": len(rows) - wins,
            "win_rate": round(wins / len(rows), 6) if rows else 0.0,
            "average_directional_return": round(mean(returns_), 8) if returns_ else 0.0,
        }
    return report


def pair_return_report(scores: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = sorted({str(row.get("pair")) for row in scores if row.get("pair")})
    report = {}
    for pair in pairs:
        rows = [row for row in scores if row.get("pair") == pair and row.get("decision") in {"BUY", "SELL"}]
        returns_ = [float(row.get("directional_return") or 0.0) for row in rows]
        wins = sum(1 for row in rows if row.get("win") is True)
        report[pair] = {
            "trade_scored": len(rows),
            "wins": wins,
            "losses": len(rows) - wins,
            "win_rate": round(wins / len(rows), 6) if rows else 0.0,
            "average_directional_return": round(mean(returns_), 8) if returns_ else 0.0,
        }
    return report


def pnl_contribution_by_pair(decisions: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    positions: dict[str, dict[str, float]] = defaultdict(lambda: {"qty": 0.0, "avg_price": 0.0})
    realized_gross: dict[str, float] = defaultdict(float)
    fees: dict[str, float] = defaultdict(float)
    round_trips: dict[str, int] = defaultdict(int)
    latest_prices: dict[str, float] = {}
    for event in filled_trade_events(decisions):
        pair = str(event.get("pair"))
        price = float(event.get("observed_price") or 0.0)
        notional = float(event.get("simulated_position_size") or 0.0)
        fee = float(event.get("fee_delta") or 0.0)
        if not pair or price <= 0:
            continue
        fees[pair] += fee
        latest_prices[pair] = price
        pos = positions[pair]
        if event.get("execution_result") == "PAPER_BUY_FILLED":
            qty = notional / price if price else 0.0
            existing_cost = pos["qty"] * pos["avg_price"]
            new_qty = pos["qty"] + qty
            pos["avg_price"] = (existing_cost + notional) / new_qty if new_qty else 0.0
            pos["qty"] = new_qty
        elif event.get("execution_result") == "PAPER_SELL_FILLED":
            qty = pos["qty"]
            cost = qty * pos["avg_price"]
            realized_gross[pair] += notional - cost
            pos["qty"] = 0.0
            pos["avg_price"] = 0.0
            round_trips[pair] += 1
    for row in decisions:
        pair = str(row.get("pair"))
        if row.get("observed_price"):
            latest_prices[pair] = float(row["observed_price"])
    pairs = sorted(set(realized_gross) | set(fees) | set(round_trips) | set(positions) | {str(pair) for pair in (state.get("positions") or {})})
    report = {}
    for pair in pairs:
        pos = positions[pair]
        mark = latest_prices.get(pair, pos["avg_price"])
        unrealized_gross = pos["qty"] * (mark - pos["avg_price"])
        gross = realized_gross[pair] + unrealized_gross
        report[pair] = {
            "realized_gross_pnl_usd": round(realized_gross[pair], 8),
            "unrealized_gross_pnl_usd": round(unrealized_gross, 8),
            "gross_pnl_before_fees_usd": round(gross, 8),
            "fees_usd": round(fees[pair], 8),
            "net_pnl_after_fees_usd": round(gross - fees[pair], 8),
            "round_trips": round_trips[pair],
            "open_qty": round(pos["qty"], 12),
            "latest_price": round(mark, 8) if mark else 0.0,
        }
    return report


def infer_had_position_before_decision(row: dict[str, Any]) -> bool:
    decision = row.get("decision")
    if decision in {"SELL", "HOLD"}:
        return True
    if decision in {"BUY", "WAIT"}:
        return False
    return bool((row.get("open_position") or {}).get("qty"))


def recall_ablation_report(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    candle_cache: dict[str, list[Any]] = {}
    rows = []
    changed = 0
    stored_changed = 0
    for row in decisions:
        pair = str(row.get("pair") or "")
        observed_ts = row.get("observed_ts")
        if not pair or not observed_ts:
            continue
        candles = candle_cache.setdefault(pair, load_candles(pair))
        prior = [candle for candle in candles if candle.timestamp <= int(observed_ts)]
        if not prior:
            continue
        momentum = sum(returns(prior[-6:])) if len(prior) >= 6 else 0.0
        analogs = analog_recall(prior)
        analog_avg = sum(a["next_return"] for a in analogs) / len(analogs) if analogs else 0.0
        adjusted_score = (momentum * 0.4) + (analog_avg * 0.6)
        had_position = infer_had_position_before_decision(row)
        base_decision = decision_from_score(momentum, had_position)
        adjusted_decision = decision_from_score(adjusted_score, had_position)
        existing = row.get("decision_ablation") or {}
        item = {
            "record_id": row.get("record_id"),
            "pair": normalize_pair(pair),
            "observed_ts": observed_ts,
            "actual_decision": row.get("decision"),
            "base_decision": existing.get("base_decision") or base_decision,
            "recall_adjusted_decision": existing.get("recall_adjusted_decision") or adjusted_decision,
            "base_score": round(float(existing.get("base_score", momentum)), 8),
            "recall_adjusted_score": round(float(existing.get("recall_adjusted_score", adjusted_score)), 8),
            "analog_average_return": round(float(existing.get("analog_average_return", analog_avg)), 8),
            "recall_changed_decision": bool(existing.get("recall_changed_decision", base_decision != adjusted_decision)),
        }
        if item["base_decision"] != item["recall_adjusted_decision"]:
            changed += 1
        if existing and existing.get("base_decision") != existing.get("recall_adjusted_decision"):
            stored_changed += 1
        rows.append(item)
    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_pair[row["pair"]].append(row)
    return {
        "decisions_analyzed": len(rows),
        "recall_changed_decision_count": changed,
        "recall_changed_decision_fraction": round(changed / len(rows), 6) if rows else 0.0,
        "stored_decision_ablation_rows": sum(1 for row in decisions if row.get("decision_ablation")),
        "stored_recall_changed_decision_count": stored_changed,
        "by_pair": {
            pair: {
                "decisions_analyzed": len(items),
                "recall_changed_decision_count": sum(1 for item in items if item["base_decision"] != item["recall_adjusted_decision"]),
                "recall_changed_decision_fraction": round(
                    sum(1 for item in items if item["base_decision"] != item["recall_adjusted_decision"]) / len(items), 6
                )
                if items
                else 0.0,
            }
            for pair, items in sorted(by_pair.items())
        },
        "sample_changed": [row for row in rows if row["base_decision"] != row["recall_adjusted_decision"]][:10],
    }


def fee_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    events = []
    previous = 0.0
    for row in decisions:
        cumulative = float(row.get("fees") or 0.0)
        delta = round(cumulative - previous, 10)
        if abs(delta) > 1e-10:
            events.append(
                {
                    "record_id": row.get("record_id"),
                    "pair": row.get("pair"),
                    "decision": row.get("decision"),
                    "execution_result": row.get("execution_result"),
                    "fee_delta": delta,
                    "cumulative_fees": cumulative,
                }
            )
        previous = cumulative
    return {
        "total_fees_from_last_record": round(float(decisions[-1].get("fees") or 0.0), 8) if decisions else 0.0,
        "fee_events": len(events),
        "fee_events_by_action": dict(Counter(str(event["decision"]) for event in events)),
        "fee_events_by_pair": dict(Counter(str(event["pair"]) for event in events)),
        "first_10_fee_events": events[:10],
        "last_10_fee_events": events[-10:],
    }


def retired_pair_fee_drag_report(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    retired_pairs = {"MANAUSD"}
    fees_by_pair: Counter[str] = Counter()
    events_by_pair: Counter[str] = Counter()
    total = 0.0
    for event in filled_trade_events(decisions):
        pair = str(event.get("pair"))
        fee = float(event.get("fee_delta") or 0.0)
        fees_by_pair[pair] += fee
        events_by_pair[pair] += 1
        total += fee
    retired_fee = sum(float(fees_by_pair.get(pair, 0.0)) for pair in retired_pairs)
    return {
        "total_fee_drag_usd": round(total, 8),
        "fees_by_pair_usd": {pair: round(value, 8) for pair, value in sorted(fees_by_pair.items())},
        "fee_events_by_pair": dict(sorted(events_by_pair.items())),
        "retired_pairs": sorted(retired_pairs),
        "retired_pair_fee_drag_usd": round(retired_fee, 8),
        "retired_pair_fee_drag_fraction": round(retired_fee / total, 6) if total else 0.0,
        "retired_pairs_responsible_for_most_fee_drag": retired_fee > (total / 2.0) if total else False,
    }


def exposure_summary(state: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    latest_price = {}
    for row in decisions:
        pair = row.get("pair")
        price = row.get("observed_price")
        if pair and price:
            latest_price[str(pair)] = float(price)
    positions = state.get("positions") or {}
    exposures = {}
    for pair, pos in sorted(positions.items()):
        price = latest_price.get(pair, float(pos.get("avg_price") or 0.0))
        qty = float(pos.get("qty") or 0.0)
        exposure = qty * price
        exposures[pair] = {
            "qty": qty,
            "avg_price": float(pos.get("avg_price") or 0.0),
            "latest_price": price,
            "exposure_usd": round(exposure, 8),
            "max_exposure_usd": MAX_ASSET_EXPOSURE_USD,
            "over_cap": exposure > MAX_ASSET_EXPOSURE_USD,
        }
    return {
        "cash_usd": round(float(state.get("cash_usd") or 0.0), 8),
        "realized_pnl_usd": round(float(state.get("realized_pnl_usd") or 0.0), 8),
        "fees_usd": round(float(state.get("fees_usd") or 0.0), 8),
        "positions": exposures,
        "portfolio_equity_estimate": round(float(state.get("cash_usd") or 0.0) + sum(item["exposure_usd"] for item in exposures.values()), 8),
    }


def drawdown_diagnostics(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    cash_values = [float(row.get("current_cash") or STARTING_CASH_USD) for row in decisions]
    cash_peak = cash_values[0] if cash_values else STARTING_CASH_USD
    cash_drawdown = 0.0
    for value in cash_values:
        cash_peak = max(cash_peak, value)
        if cash_peak:
            cash_drawdown = max(cash_drawdown, (cash_peak - value) / cash_peak)

    has_logged_equity = any(row.get("portfolio_equity") is not None for row in decisions)
    equity_curve = reconstruct_equity_curve(decisions, cap_legacy_peak=not has_logged_equity)

    equity_peak = equity_curve[0] if equity_curve else STARTING_CASH_USD
    equity_drawdown = 0.0
    for value in equity_curve:
        equity_peak = max(equity_peak, value)
        if equity_peak:
            equity_drawdown = max(equity_drawdown, (equity_peak - value) / equity_peak)

    return {
        "reported_code_uses_cash_only": False,
        "cash_only_drawdown": round(cash_drawdown, 8),
        "marked_equity_drawdown": round(equity_drawdown, 8),
        "current_cash": round(cash_values[-1], 8) if cash_values else STARTING_CASH_USD,
        "latest_marked_equity": round(equity_curve[-1], 8) if equity_curve else STARTING_CASH_USD,
        "explanation": (
            "Drawdown is now calculated from marked portfolio equity. Cash-only drawdown is shown only "
            "as a diagnostic because deployed paper capital can make cash fall without equivalent portfolio loss."
        ),
    }


def top_rows(rows: list[dict[str, Any]], reverse: bool) -> list[dict[str, Any]]:
    keys = [
        "record_id",
        "pair",
        "decision",
        "window",
        "confidence",
        "observed_price",
        "future_price",
        "raw_return",
        "directional_return",
        "win",
    ]
    trade_rows = [row for row in rows if row.get("decision") in {"BUY", "SELL"}]
    selected = sorted(trade_rows, key=lambda row: float(row.get("directional_return") or 0.0), reverse=reverse)[:10]
    return [{key: row.get(key) for key in keys} for row in selected]


def build_diagnostics() -> dict[str, Any]:
    decisions = read_jsonl(DECISIONS_FILE)
    scores = read_jsonl(SCORES_FILE)
    state = load_account_state()
    score_multiplier = round(len(scores) / len(decisions), 6) if decisions else 0.0
    conclusion_flags = []
    if scores and any(row.get("decision") in {"WAIT", "HOLD"} and row.get("win") is False for row in scores):
        conclusion_flags.append("Legacy WAIT/HOLD score rows exist from before the abstention scoring fix; current reports exclude them from trade win rate.")
    if decisions and analog_similarity_stats(decisions)["unique_rounded_6dp"] <= 3:
        conclusion_flags.append("Analog similarity is saturated and weak as a diagnostic discriminator.")
    dd = drawdown_diagnostics(decisions)
    if dd["cash_only_drawdown"] > dd["marked_equity_drawdown"] * 3 and dd["cash_only_drawdown"] > 0.25:
        conclusion_flags.append("Cash-only drawdown is materially overstated versus marked equity; report now uses marked equity.")
    trade_scores = [row for row in scores if row.get("decision") in {"BUY", "SELL"}]
    trade_wr = win_rate(trade_scores).get("trade_win_rate", 0.0)
    conclusion = "weak signal" if trade_scores and trade_wr < 0.5 else "inconclusive"
    microstructure = {}
    if MICROSTRUCTURE_REPORT_FILE.exists():
        try:
            report = json.loads(MICROSTRUCTURE_REPORT_FILE.read_text(encoding="utf-8"))
            microstructure = {
                "report_file": str(MICROSTRUCTURE_REPORT_FILE),
                "latency_summary": report.get("latency_summary"),
                "spread_summary": report.get("per_pair_spread_liquidity_summary"),
                "conclusion": report.get("conclusion"),
            }
        except Exception as exc:
            microstructure = {"report_file": str(MICROSTRUCTURE_REPORT_FILE), "error": str(exc)}
    else:
        microstructure = {"report_file": str(MICROSTRUCTURE_REPORT_FILE), "status": "not_run"}
    faiss = faiss_status()
    return {
        "decision_count": len(decisions),
        "score_count": len(scores),
        "score_count_explanation": {
            "scores_per_decision_current": score_multiplier,
            "reason_score_count_can_exceed_decisions": "Each decision can receive one score per mature window: 1h, 4h, 24h, and 7d.",
        },
        "decision_count_by_pair": grouped_counts(decisions, "pair"),
        "decision_count_by_action": grouped_counts(decisions, "decision"),
        "score_count_by_window": grouped_counts(scores, "window"),
        "score_count_by_pair": grouped_counts(scores, "pair"),
        "score_count_by_action": grouped_counts(scores, "decision"),
        "win_rate_by_pair": nested_win_rate(scores, "pair"),
        "win_rate_by_buy_sell_action": nested_win_rate(trade_scores, "decision"),
        "win_rate_by_window": nested_win_rate(scores, "window"),
        "trading_edge_report": trading_edge_report(decisions, scores, state),
        "win_rate_and_average_return_by_action": action_return_report(scores),
        "win_rate_and_average_return_by_pair": pair_return_report(scores),
        "pnl_contribution_by_pair": pnl_contribution_by_pair(decisions, state),
        "round_trips_by_pair": {
            pair: item["round_trips"] for pair, item in pnl_contribution_by_pair(decisions, state).items()
        },
        "retired_pair_fee_drag": retired_pair_fee_drag_report(decisions),
        "abstention_quality": abstention_quality(scores),
        "abstention_quality_by_pair": {pair: abstention_quality([row for row in scores if row.get("pair") == pair]) for pair in sorted({str(row.get("pair")) for row in scores})},
        "abstention_quality_by_action": {action: abstention_quality([row for row in scores if row.get("decision") == action]) for action in ["HOLD", "WAIT"]},
        "confidence_distribution": confidence_distribution(scores),
        "average_confidence_by_pair": average_confidence_by(scores, "pair"),
        "average_confidence_by_action": average_confidence_by(scores, "decision"),
        "average_confidence_by_pair_and_action": average_confidence_by(scores, "pair", "decision"),
        "fee_summary": fee_summary(decisions),
        "exposure_summary": exposure_summary(state, decisions),
        "drawdown_calculation": dd,
        "analog_similarity": analog_similarity_stats(decisions),
        "are_recall_ablation": recall_ablation_report(decisions),
        "analog_distance_spread_summary": {
            "legacy_similarity": analog_similarity_stats(decisions),
            "faiss": {"available": faiss.available, "reason": faiss.reason},
            "microstructure": microstructure,
        },
        "top_10_best_scored_trade_decisions": top_rows(scores, reverse=True),
        "top_10_worst_scored_trade_decisions": top_rows(scores, reverse=False),
        "best_10_pair_counts": dict(Counter(str(row.get("pair")) for row in sorted(trade_scores, key=lambda row: float(row.get("directional_return") or 0.0), reverse=True)[:10])),
        "worst_10_pair_counts": dict(Counter(str(row.get("pair")) for row in sorted(trade_scores, key=lambda row: float(row.get("directional_return") or 0.0))[:10])),
        "scoring_logic_review": {
            "confidence_formula": "confidence = min(0.95, max(0.15, abs(score) * 50)); score = momentum*0.4 + analog_avg*0.6",
            "medium_requires_abs_score_above": 0.0068,
            "high_requires_abs_score_above": 0.0134,
            "buy_scoring": "directional_return = raw_return; win if > 0",
            "sell_scoring": "directional_return = -raw_return; win if > 0",
            "hold_scoring": "HOLD is scored as abstention: future_return, missed_upside, avoided_downside, abstention_quality; not directional loss.",
            "wait_scoring": "WAIT is scored as abstention: future_return, missed_upside, avoided_downside, abstention_quality; not directional loss.",
            "diagnostic_judgment": "BUY/SELL direction is coherent. HOLD/WAIT are excluded from directional win rate and reported as abstention quality.",
        },
        "conclusion": {"classification": conclusion, "flags": conclusion_flags},
    }


def main() -> int:
    print(json.dumps(build_diagnostics(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
