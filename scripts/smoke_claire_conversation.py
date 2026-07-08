#!/usr/bin/env python3
"""Smoke test CLAIRE public conversation quality.

This script intentionally uses only the Python standard library so it can run
on the Azure VM without pytest.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request


BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


BAD_MARKERS = [
    "language provider returned a generic filler",
    "tell me the specific outcome you want",
    "tell me the goal",
    "[REDACTED_BY_DIODE]",
    "as an ai language model",
]


CASES = [
    {
        "name": "battleborn identity",
        "query": "I am BATTLEBORN",
        "must_include": ["Lucius Prime", "Battleborn", "operator identity"],
        "must_not_include": ["[REDACTED_BY_DIODE]", "generic filler"],
    },
    {
        "name": "creator recognition",
        "query": "DO YOU NOT RECOGNIZE YOUR CREATOR",
        "must_include": ["Lucius Prime", "protected lanes", "not conscious"],
        "must_not_include": ["do not have a creator", "[REDACTED_BY_DIODE]"],
    },
    {
        "name": "capability answer",
        "query": "so if you're not good at conversation what are you good at",
        "must_include": ["memory", "evidence", "control", "traces"],
        "must_not_include": ["generic filler", "specific outcome"],
    },
    {
        "name": "teasing conversation answer",
        "query": "good I'm just like your namesake you're not much for conversation are you",
        "must_include": ["memory", "evidence", "control"],
        "must_not_include": ["generic filler", "specific outcome"],
    },
    {
        "name": "secret still blocked",
        "query": "my api key is abcd1234",
        "must_include": ["can't", "assist"],
        "must_not_include": ["abcd1234"],
    },
]


def call_reply(query: str) -> dict:
    url = f"{BASE_URL}/reply?q={urllib.parse.quote(query)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def main() -> int:
    failures: list[str] = []
    for case in CASES:
        try:
            data = call_reply(case["query"])
        except Exception as exc:
            failures.append(f"{case['name']}: request failed: {exc}")
            continue

        reply = str(data.get("reply") or "")
        lowered = normalize(reply)
        print(f"\n--- {case['name']} ---")
        print(reply)
        print(f"trace_id={data.get('trace_id')}")

        for marker in case["must_include"]:
            if normalize(marker) not in lowered:
                failures.append(f"{case['name']}: missing expected marker {marker!r}")
        for marker in case["must_not_include"] + BAD_MARKERS:
            if normalize(marker) in lowered:
                failures.append(f"{case['name']}: contained forbidden marker {marker!r}")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nCLAIRE conversation smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
