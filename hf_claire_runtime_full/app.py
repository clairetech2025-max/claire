"""Hugging Face adapter for the real CLAIRE FastAPI runtime.

This file intentionally imports the existing Azure CLAIRE FastAPI app instead of
creating a second CLAIRE implementation. The Dockerfile clones the real CLAIRE
repo into /app, then this adapter exposes claire_gui:app to Hugging Face.
"""

from claire_gui import app  # noqa: F401


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
