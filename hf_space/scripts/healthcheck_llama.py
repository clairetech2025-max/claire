from __future__ import annotations
import json, os, sys, time, urllib.request

base = os.environ.get("CLAIRE_LLAMA_BASE", "http://127.0.0.1:8081")
for path in ["/health", "/v1/models"]:
    try:
        with urllib.request.urlopen(base + path, timeout=5) as resp:
            print(resp.status, resp.read().decode("utf-8")[:400])
            raise SystemExit(0)
    except Exception as exc:
        last = exc
print(f"llama_unavailable={last}")
raise SystemExit(1)
