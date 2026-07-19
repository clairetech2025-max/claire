from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from validate_hf_tree import validate_tree


HF_API = "https://huggingface.co/api"
APPROVAL_ENV = "HF_APPROVE_SDK_TRANSITION"


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def effective_space_id(manifest: dict[str, Any]) -> str:
    return (os.getenv("HF_SPACE_ID") or str(manifest.get("space_id") or "")).strip()


def token_available() -> bool:
    if os.getenv("HF_TOKEN"):
        return True
    try:
        result = subprocess.run(
            ["hf", "auth", "whoami"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def hub_get(path: str) -> dict[str, Any]:
    request = urllib.request.Request(f"{HF_API}{path}")
    token = os.getenv("HF_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Hub API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Hub API request failed: {exc.reason}") from exc


def live_space_sdk(space: dict[str, Any]) -> str:
    card_data = space.get("cardData") if isinstance(space.get("cardData"), dict) else {}
    return str(space.get("sdk") or card_data.get("sdk") or "").strip().lower()


def approval_enabled() -> bool:
    return os.getenv(APPROVAL_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("build_dir", type=Path)
    parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Only validate local package and manifest. Do not use before real upload.",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    errors = validate_tree(args.build_dir)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    space_id = effective_space_id(manifest)
    if not space_id:
        print("manifest has no space_id and HF_SPACE_ID is unset; refusing upload", file=sys.stderr)
        return 2

    package_sdk = str(manifest.get("sdk") or "").strip().lower()
    if not package_sdk:
        print("manifest missing sdk; refusing upload", file=sys.stderr)
        return 2

    if args.skip_remote:
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "local-only",
                    "space_id": space_id,
                    "package_sdk": package_sdk,
                    "build_dir": str(args.build_dir),
                },
                sort_keys=True,
            )
        )
        return 0

    if not token_available():
        print("Hugging Face authentication unavailable; set HF_TOKEN or run `hf auth login`.", file=sys.stderr)
        return 2

    try:
        space = hub_get(f"/spaces/{space_id}")
    except RuntimeError as exc:
        print(f"cannot inspect existing Space {space_id}: {exc}", file=sys.stderr)
        return 2

    current_sdk = live_space_sdk(space)
    if current_sdk and package_sdk and current_sdk != package_sdk and not approval_enabled():
        print(
            (
                f"Space SDK transition requires explicit approval: {space_id} "
                f"is currently {current_sdk}, package is {package_sdk}. "
                f"Set {APPROVAL_ENV}=true only after approving this runtime-mode change."
            ),
            file=sys.stderr,
        )
        return 2

    runtime = space.get("runtime") if isinstance(space.get("runtime"), dict) else {}
    print(
        json.dumps(
            {
                "ok": True,
                "space_id": space_id,
                "application": manifest.get("application"),
                "package_sdk": package_sdk,
                "current_sdk": current_sdk or "unknown",
                "current_sha": space.get("sha"),
                "runtime_stage": runtime.get("stage"),
                "host": space.get("host"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
