from __future__ import annotations

import os
from typing import Any


def call_nvidia_inference(prompt: str) -> dict[str, Any]:
    endpoint = os.getenv("NVIDIA_INFERENCE_URL", "").strip()
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()

    if not endpoint:
        return {
            "status": "not_configured",
            "message": "NVIDIA inference endpoint not configured. Running in local demo mode.",
        }

    try:
        import httpx
    except Exception:
        return {
            "status": "dependency_missing",
            "message": "httpx is required for NVIDIA inference calls.",
        }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(endpoint, json={"prompt": prompt}, headers=headers)
            response.raise_for_status()
            try:
                data: Any = response.json()
            except Exception:
                data = {"text": response.text}
            return {"status": "ok", "response": data}
    except Exception as exc:
        return {
            "status": "error",
            "message": f"NVIDIA inference call failed: {str(exc)[:300]}",
        }
