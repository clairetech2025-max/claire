#!/usr/bin/env python3
"""CLI for Veritas paper-only observation decisions."""

from __future__ import annotations

import argparse
import json

from veritas.veritas_paper_runtime import observe_once


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Veritas paper-only observation cycle.")
    parser.add_argument("--pair", default="BTC/USD")
    parser.add_argument("--mode", default="observe", choices=["observe"])
    args = parser.parse_args()
    result = observe_once(args.pair)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
