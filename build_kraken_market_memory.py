#!/usr/bin/env python3
"""
Build Claire Market Memory from Kraken OHLCVT CSV exports.

Input CSV format:
timestamp,open,high,low,close,volume,trades

This script keeps raw candles out of Claire's document lane. It produces:
- manifest.jsonl: one record per source CSV
- market_vectors.jsonl: compact regime/vector memories for selected assets
- summary.json: parser run summary
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


FILENAME_RE = re.compile(r"^(?P<pair>.+)_(?P<interval>\d+)\.csv$", re.IGNORECASE)
DEFAULT_CORE_PAIRS = {"XBTUSD", "ETHUSD", "SOLUSD", "XRPUSD"}


@dataclass
class Row:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_filename(path: Path) -> tuple[str, int] | None:
    if path.name.startswith("._"):
        return None
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    return match.group("pair").upper(), int(match.group("interval"))


def read_rows(path: Path) -> Iterable[Row]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for parts in reader:
            if len(parts) < 7:
                continue
            try:
                yield Row(
                    ts=int(float(parts[0])),
                    open=float(parts[1]),
                    high=float(parts[2]),
                    low=float(parts[3]),
                    close=float(parts[4]),
                    volume=float(parts[5]),
                    trades=int(float(parts[6])),
                )
            except Exception:
                continue


def regime_for(return_pct: float, bb_width_pct: float, range_position: float, volume_z: float) -> str:
    if bb_width_pct >= 10 or abs(return_pct) >= 12 or abs(volume_z) >= 8:
        return "HIGH_VOL"
    if bb_width_pct <= 2.5 and abs(return_pct) <= 2.0:
        return "COMPRESSION"
    if return_pct >= 4.0 and range_position >= 0.65:
        return "TREND_UP"
    if return_pct <= -4.0 and range_position <= 0.35:
        return "TREND_DOWN"
    return "RANGE"


def vector_from_window(pair: str, interval: int, path: Path, idx: int, window: list[Row]) -> dict:
    closes = [row.close for row in window]
    volumes = [row.volume for row in window]
    highs = [row.high for row in window]
    lows = [row.low for row in window]
    last = window[-1]
    first_close = closes[0]
    sma = sum(closes) / len(closes)
    variance = sum((price - sma) ** 2 for price in closes) / max(1, len(closes))
    stdev = math.sqrt(variance)
    bb_width_pct = (stdev * 4 / sma * 100) if sma else 0.0
    return_pct = ((last.close - first_close) / first_close * 100) if first_close else 0.0
    high = max(highs)
    low = min(lows)
    range_position = ((last.close - low) / (high - low)) if high != low else 0.5
    volume_sma = sum(volumes) / len(volumes) if volumes else 0.0
    volume_z = ((last.volume - volume_sma) / (volume_sma or 1.0)) if volumes else 0.0
    drawdown_pct = ((last.close - high) / high * 100) if high else 0.0
    trade_count = sum(row.trades for row in window)
    regime = regime_for(return_pct, bb_width_pct, range_position, volume_z)
    return {
        "lane": "market_memory",
        "source": "kraken_ohlcvt",
        "pair": pair,
        "interval_minutes": interval,
        "timestamp": iso(last.ts),
        "unix": last.ts,
        "source_file": path.name,
        "source_row": idx,
        "window": len(window),
        "regime": regime,
        "features": {
            "close": round(last.close, 10),
            "return_pct": round(return_pct, 6),
            "bb_width_pct": round(bb_width_pct, 6),
            "range_position": round(range_position, 6),
            "volume_z": round(volume_z, 6),
            "drawdown_pct": round(drawdown_pct, 6),
            "trade_count_window": trade_count,
        },
        "text": (
            f"Kraken market memory {pair} {interval}m at {iso(last.ts)}: "
            f"regime={regime}, return={return_pct:.3f}%, "
            f"bb_width={bb_width_pct:.3f}%, volume_z={volume_z:.3f}, "
            f"range_position={range_position:.3f}."
        ),
    }


def scan_manifest(path: Path) -> dict:
    first: Row | None = None
    last: Row | None = None
    rows = 0
    for row in read_rows(path):
        if first is None:
            first = row
        last = row
        rows += 1
    parsed = parse_filename(path)
    pair, interval = parsed if parsed else ("UNKNOWN", 0)
    return {
        "pair": pair,
        "interval_minutes": interval,
        "file": path.name,
        "path": str(path),
        "bytes": path.stat().st_size,
        "rows": rows,
        "start": iso(first.ts) if first else None,
        "end": iso(last.ts) if last else None,
    }


def stride_for_interval(interval: int, rows: int, max_vectors: int) -> int:
    if rows <= 0:
        return 1
    return max(1, math.ceil(rows / max_vectors))


def build_vectors(path: Path, pair: str, interval: int, max_vectors: int, window_size: int) -> list[dict]:
    rows_estimate = 0
    for _ in read_rows(path):
        rows_estimate += 1
    stride = stride_for_interval(interval, rows_estimate, max_vectors)

    vectors: list[dict] = []
    window: deque[Row] = deque(maxlen=window_size)
    for idx, row in enumerate(read_rows(path), start=1):
        window.append(row)
        if len(window) < window_size:
            continue
        if idx % stride == 0 or idx == rows_estimate:
            vectors.append(vector_from_window(pair, interval, path, idx, list(window)))
    return vectors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Folder containing Kraken CSV files")
    parser.add_argument("--output", required=True, help="Output folder for market memory files")
    parser.add_argument("--assets", default="XBTUSD,ETHUSD,SOLUSD,XRPUSD", help="Comma-separated pairs for vector output")
    parser.add_argument("--all-assets", action="store_true", help="Build vectors for every pair, not just --assets")
    parser.add_argument("--only-assets", action="store_true", help="Skip manifest/vector work for pairs outside --assets")
    parser.add_argument("--intervals", default="", help="Comma-separated interval minutes to include, e.g. 5,60,1440")
    parser.add_argument("--manifest-only", action="store_true", help="Only build manifest.jsonl")
    parser.add_argument("--recursive", action="store_true", help="Scan subfolders too")
    parser.add_argument("--max-vectors-per-file", type=int, default=240)
    parser.add_argument("--window", type=int, default=20)
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_filter = {item.strip().upper() for item in args.assets.split(",") if item.strip()} or DEFAULT_CORE_PAIRS
    interval_filter = {int(item.strip()) for item in args.intervals.split(",") if item.strip()} if args.intervals.strip() else set()
    manifest_path = output_dir / "manifest.jsonl"
    vectors_path = output_dir / "market_vectors.jsonl"
    summary_path = output_dir / "summary.json"

    source_iter = input_dir.rglob("*.csv") if args.recursive else input_dir.glob("*.csv")
    files = sorted(path for path in source_iter if "__MACOSX" not in str(path) and not path.name.startswith("._"))
    summary = {
        "input": str(input_dir),
        "output": str(output_dir),
        "files_seen": len(files),
        "manifest_records": 0,
        "vector_records": 0,
        "vector_pairs": sorted(asset_filter) if not args.all_assets else ["ALL"],
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    with manifest_path.open("w", encoding="utf-8") as manifest_f, vectors_path.open("w", encoding="utf-8") as vectors_f:
        for path in files:
            parsed = parse_filename(path)
            if not parsed:
                continue
            pair, interval = parsed
            if args.only_assets and pair not in asset_filter:
                continue
            if interval_filter and interval not in interval_filter:
                continue
            manifest = scan_manifest(path)
            manifest_f.write(json.dumps(manifest, ensure_ascii=False) + "\n")
            summary["manifest_records"] += 1
            if args.manifest_only:
                continue
            if not args.all_assets and pair not in asset_filter:
                continue
            vectors = build_vectors(path, pair, interval, args.max_vectors_per_file, args.window)
            for vector in vectors:
                vectors_f.write(json.dumps(vector, ensure_ascii=False) + "\n")
            summary["vector_records"] += len(vectors)

    summary["completed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
