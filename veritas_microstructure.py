#!/usr/bin/env python3
"""Run read-only Veritas Kraken microstructure observation."""

from __future__ import annotations

import argparse
import json

from veritas.kraken_microstructure import build_microstructure_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe Kraken public ticker/depth microstructure.")
    parser.add_argument("--pairs", nargs="+", default=None)
    args = parser.parse_args()
    print(json.dumps(build_microstructure_report(args.pairs), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
