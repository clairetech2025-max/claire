#!/usr/bin/env python3
"""Build a Veritas paper-decision scoring report."""

from __future__ import annotations

import json

from veritas.veritas_paper_runtime import build_report


def main() -> int:
    print(json.dumps(build_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
