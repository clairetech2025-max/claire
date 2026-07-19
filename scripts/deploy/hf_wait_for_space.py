from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import preflight_hf_space


TERMINAL_FAILURE_STAGES = {"BUILD_ERROR", "RUNTIME_ERROR", "PAUSED"}
RUNNING_STAGES = {"RUNNING"}


def health_url(host: str, endpoint: str) -> str:
    clean_host = host.rstrip("/")
    clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{clean_host}{clean_endpoint}"


def http_get_json_or_text(url: str, *, timeout: int = 30) -> tuple[int, str]:
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)


def runtime_packet(space: dict[str, Any]) -> dict[str, object]:
    runtime = space.get("runtime") if isinstance(space.get("runtime"), dict) else {}
    return {
        "id": space.get("id"),
        "sha": space.get("sha"),
        "host": space.get("host"),
        "sdk": preflight_hf_space.live_space_sdk(space) or "unknown",
        "runtime_stage": runtime.get("stage"),
        "hardware": runtime.get("hardware") or runtime.get("requested_hardware"),
    }


def wait_for_running(space_id: str, *, timeout_seconds: int, interval_seconds: int) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    last_packet: dict[str, object] = {}

    while True:
        attempts += 1
        space = preflight_hf_space.hub_get(f"/spaces/{space_id}")
        packet = runtime_packet(space)
        packet["attempts"] = attempts
        last_packet = packet
        stage = str(packet.get("runtime_stage") or "").upper()

        if stage in RUNNING_STAGES and packet.get("host"):
            return packet
        if stage in TERMINAL_FAILURE_STAGES:
            raise RuntimeError(f"Space {space_id} reached failure stage {stage}: {json.dumps(packet, sort_keys=True)}")
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Space {space_id} did not become RUNNING before timeout; "
                f"last state: {json.dumps(last_packet, sort_keys=True)}"
            )
        time.sleep(interval_seconds)


def parse_health_body(body: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def included_source_matches(deployment: dict[str, Any], expected_sha: str) -> bool:
    expected = expected_sha.strip()
    if not expected:
        return True
    included = deployment.get("included_sources")
    if not isinstance(included, list):
        return False
    for item in included:
        if not isinstance(item, dict):
            continue
        if str(item.get("source_git_sha") or "").strip() == expected:
            return True
    return False


def validate_deployment_identity(
    health_payload: dict[str, Any],
    *,
    expected_source_sha: str = "",
    expected_source_ref: str = "",
    expected_included_source_sha: str = "",
) -> dict[str, Any]:
    deployment = health_payload.get("deployment")
    if not isinstance(deployment, dict):
        deployment = {}
    expected_source_sha = expected_source_sha.strip()
    expected_source_ref = expected_source_ref.strip()
    expected_included_source_sha = expected_included_source_sha.strip()
    if expected_source_sha and str(deployment.get("source_git_sha") or "").strip() != expected_source_sha:
        raise RuntimeError(
            "Health endpoint is running a different source SHA: "
            f"expected={expected_source_sha} actual={deployment.get('source_git_sha') or 'missing'}"
        )
    if expected_source_ref and str(deployment.get("source_git_ref") or "").strip() != expected_source_ref:
        raise RuntimeError(
            "Health endpoint is running a different source ref: "
            f"expected={expected_source_ref} actual={deployment.get('source_git_ref') or 'missing'}"
        )
    if expected_included_source_sha and not included_source_matches(deployment, expected_included_source_sha):
        raise RuntimeError(
            "Health endpoint is missing expected included source SHA: "
            f"expected={expected_included_source_sha}"
        )
    return deployment


def wait_for_health(
    url: str,
    *,
    timeout_seconds: int,
    interval_seconds: int,
    expected_source_sha: str = "",
    expected_source_ref: str = "",
    expected_included_source_sha: str = "",
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    last_status = 0
    last_body = ""

    while True:
        attempts += 1
        status, body = http_get_json_or_text(url)
        last_status = status
        last_body = body[:500]
        if 200 <= status < 400:
            payload = parse_health_body(body)
            deployment = validate_deployment_identity(
                payload,
                expected_source_sha=expected_source_sha,
                expected_source_ref=expected_source_ref,
                expected_included_source_sha=expected_included_source_sha,
            )
            return {
                "url": url,
                "status": status,
                "attempts": attempts,
                "deployment": deployment,
            }
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Health endpoint did not pass before timeout: "
                f"url={url} status={last_status} body={last_body!r}"
            )
        time.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--space-id", default="", help="Override manifest space_id for this check.")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--expected-source-sha", default="", help="Require health deployment.source_git_sha to match this SHA.")
    parser.add_argument("--expected-source-ref", default="", help="Require health deployment.source_git_ref to match this ref.")
    parser.add_argument(
        "--expected-included-source-sha",
        default="",
        help="Require health deployment.included_sources to contain this source_git_sha.",
    )
    args = parser.parse_args()

    manifest = preflight_hf_space.load_manifest(args.manifest)
    space_id = (args.space_id or os.getenv("HF_SPACE_ID") or str(manifest.get("space_id") or "")).strip()
    if not space_id:
        print("manifest has no space_id and no --space-id/HF_SPACE_ID override was provided", file=sys.stderr)
        return 2
    if not preflight_hf_space.token_available():
        print("Hugging Face authentication unavailable; set HF_TOKEN or run `hf auth login`.", file=sys.stderr)
        return 2

    try:
        runtime = wait_for_running(
            space_id,
            timeout_seconds=args.timeout,
            interval_seconds=args.interval,
        )
        endpoint = str(manifest.get("health_endpoint") or "/")
        health = wait_for_health(
            health_url(str(runtime["host"]), endpoint),
            timeout_seconds=args.timeout,
            interval_seconds=args.interval,
            expected_source_sha=args.expected_source_sha,
            expected_source_ref=args.expected_source_ref,
            expected_included_source_sha=args.expected_included_source_sha,
        )
    except (RuntimeError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "space_id": space_id,
                "application": manifest.get("application"),
                "runtime": runtime,
                "health": health,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
