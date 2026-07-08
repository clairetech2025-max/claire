#!/usr/bin/env python3
"""Report Veritas readiness for paper/backtest use."""

from __future__ import annotations

import json

from veritas.veritas_paper_runtime import readiness_report


def main() -> int:
    print(json.dumps(readiness_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
