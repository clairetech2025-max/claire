from __future__ import annotations
import os, sys, urllib.request
url = os.environ.get("CLAIRE_HEALTH_URL", "http://127.0.0.1:7860/health")
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        print(resp.status, resp.read().decode("utf-8")[:400])
        raise SystemExit(0 if 200 <= resp.status < 500 else 1)
except Exception as exc:
    print(f"claire_unavailable={exc}")
    raise SystemExit(1)
