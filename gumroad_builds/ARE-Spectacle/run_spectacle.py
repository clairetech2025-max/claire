from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app.main import app


PRODUCT_NAME = "ARE Spectacle"
HOST = "127.0.0.1"
PORT = int(os.environ.get("ARE_SPECTACLE_PORT", "8010"))


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> None:
    root = runtime_root()
    os.chdir(root)
    (root / "data").mkdir(exist_ok=True)

    url = f"http://{HOST}:{PORT}/health"
    print(f"{PRODUCT_NAME} starting on http://{HOST}:{PORT}")
    print("Close this window to stop the local server.")

    def open_browser() -> None:
        time.sleep(1.25)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
