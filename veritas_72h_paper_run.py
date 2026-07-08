#!/usr/bin/env python3
"""72-hour Veritas paper-only runner.

Each cycle fetches Kraken public OHLC candles, runs one paper observation, and
updates the paper report. It never uses private keys and never calls order
endpoints.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from veritas.kraken_public_candle_updater import update_public_candles
from veritas.veritas_paper_runtime import CONFIGURED_PAIRS, build_report, observe_once


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def error_summary(exc: Exception) -> dict[str, str]:
    return {"type": exc.__class__.__name__, "message": str(exc)}


def run_paper_loop(pairs: list[str], interval: int, hours: float, cycle_seconds: float) -> dict:
    started = time.time()
    deadline = started + max(0.0, hours) * 3600
    cycle = 0
    last_report = None
    print(
        json.dumps(
            {
                "event": "veritas_72h_paper_run_start",
                "pairs": pairs,
                "interval": interval,
                "hours": hours,
                "cycle_seconds": cycle_seconds,
                "started_at": utc_now(),
                "live_execution": False,
                "private_keys_required": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        while time.time() < deadline:
            cycle += 1
            cycle_started = utc_now()
            updates = []
            decisions = []
            errors: list[dict[str, Any]] = []
            for pair in pairs:
                try:
                    updates.append(update_public_candles(pair, interval=interval))
                except Exception as exc:
                    errors.append(
                        {
                            "stage": "update_public_candles",
                            "pair": pair,
                            "error": error_summary(exc),
                            "at": utc_now(),
                        }
                    )
                    continue
                try:
                    decisions.append(observe_once(pair))
                except Exception as exc:
                    errors.append(
                        {
                            "stage": "observe_once",
                            "pair": pair,
                            "error": error_summary(exc),
                            "at": utc_now(),
                        }
                    )
            last_report = build_report()
            live_flags = [bool(decision.get("live_execution")) for decision in decisions]
            progress = {
                "event": "veritas_72h_cycle_complete",
                "cycle": cycle,
                "cycle_started_at": cycle_started,
                "cycle_completed_at": utc_now(),
                "pairs": pairs,
                "interval": interval,
                "candle_rows": {update.pair: update.rows_written for update in updates},
                "errors": errors,
                "pairs_attempted": len(pairs),
                "pairs_observed": len(decisions),
                "pairs_skipped": len(pairs) - len(decisions),
                "decisions": [
                    {
                        "pair": decision.get("pair"),
                        "decision": decision.get("decision"),
                        "execution_result": decision.get("execution_result"),
                        "observed_price": decision.get("observed_price"),
                        "source_file": decision.get("source_file"),
                        "live_execution": bool(decision.get("live_execution")),
                    }
                    for decision in decisions
                ],
                "live_execution": any(live_flags),
                "decisions_total": last_report.get("decisions") if last_report else None,
                "scores_total": last_report.get("scores") if last_report else None,
                "equity_usd": last_report.get("equity_usd") if last_report else None,
            }
            print(json.dumps(progress, sort_keys=True), flush=True)
            if progress["live_execution"]:
                raise RuntimeError("Invariant violation: paper runner observed live_execution=true")
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            time.sleep(min(max(0.0, cycle_seconds), remaining))
    except KeyboardInterrupt:
        print(json.dumps({"event": "veritas_72h_paper_run_stopped", "stopped_at": utc_now(), "cycle": cycle}, sort_keys=True), flush=True)
    final = build_report()
    result = {
        "event": "veritas_72h_paper_run_complete",
        "completed_at": utc_now(),
        "cycles": cycle,
        "pairs": pairs,
        "interval": interval,
        "live_execution": False,
        "report": final,
    }
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Veritas public-data paper observations for a fixed duration.")
    parser.add_argument("--pair", default=None, help="Single pair compatibility option.")
    parser.add_argument("--pairs", nargs="+", default=None, help="One or more Kraken pairs.")
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--hours", type=float, default=72.0)
    parser.add_argument("--cycle-seconds", type=float, default=300.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pairs = args.pairs or ([args.pair] if args.pair else CONFIGURED_PAIRS)
    run_paper_loop(pairs, args.interval, args.hours, args.cycle_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
