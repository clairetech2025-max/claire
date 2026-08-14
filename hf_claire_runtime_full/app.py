"""Hugging Face adapter for the real CLAIRE FastAPI runtime.

This file intentionally imports the existing Azure CLAIRE FastAPI app instead of
creating a second CLAIRE implementation. The Dockerfile clones the real CLAIRE
repo into /app, then this adapter exposes claire_gui:app to Hugging Face.
"""

import asyncio
import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

from claire_gui import CLAIRE_GOVERNED_RUNTIME, app  # noqa: F401


@app.post("/internal/runtime/turn")
async def internal_runtime_turn(request: Request):
    expected = os.environ.get("CLAIRE_INTERNAL_OPERATOR_TOKEN", "").strip()
    supplied = request.headers.get("X-CLAIRE-OPERATOR-TOKEN", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return JSONResponse({"status": "not_found"}, status_code=404)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    message = str(payload.get("message") or "").strip()
    if not message or len(message) > 8000:
        return JSONResponse({"status": "invalid_request"}, status_code=400)
    if CLAIRE_GOVERNED_RUNTIME is None:
        return JSONResponse({"status": "runtime_unavailable"}, status_code=503)
    result = await asyncio.to_thread(
        CLAIRE_GOVERNED_RUNTIME.handle_user_message,
        "phase1b-operator",
        str(payload.get("session_id") or "phase1b-controlled"),
        message,
        {
            "trusted_device": True,
            "owner_mode": True,
            "source_component": "hf_internal_operator",
        },
    )
    return JSONResponse(result)


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
