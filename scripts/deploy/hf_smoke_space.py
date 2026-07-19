from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import preflight_hf_space
from hf_wait_for_space import parse_health_body, validate_deployment_identity


def http_request(
    method: str,
    url: str,
    *,
    payload: dict[str, object] | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    data = None
    headers = {"User-Agent": "claire-hf-smoke/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body, response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body, exc.headers.get("content-type", "")
    except urllib.error.URLError as exc:
        return 0, str(exc.reason), ""


def join_url(base_url: str, endpoint: str) -> str:
    return base_url.rstrip("/") + "/" + endpoint.lstrip("/")


def derived_space_url(space_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", space_id.strip().lower()).strip("-")
    return f"https://{slug}.hf.space"


def resolve_base_url(manifest: dict[str, Any], *, space_id: str = "") -> str:
    effective_space_id = (space_id or os.getenv("HF_SPACE_ID") or str(manifest.get("space_id") or "")).strip()
    if effective_space_id and preflight_hf_space.token_available():
        try:
            space = preflight_hf_space.hub_get(f"/spaces/{effective_space_id}")
        except RuntimeError:
            pass
        else:
            runtime = space.get("runtime") if isinstance(space.get("runtime"), dict) else {}
            host = str(space.get("host") or runtime.get("host") or "").strip()
            if host:
                return host.rstrip("/")

    manifest_url = str(manifest.get("space_url") or "").strip()
    if manifest_url:
        return manifest_url.rstrip("/")
    if effective_space_id:
        return derived_space_url(effective_space_id)
    raise RuntimeError("cannot resolve Space URL; provide --base-url, --space-id, HF_SPACE_ID, or manifest space_url")


def require_status(name: str, status: int, body: str, *, allowed: tuple[int, ...] = (200,)) -> None:
    if status not in allowed:
        raise RuntimeError(f"{name} returned HTTP {status}: {body[:300]!r}")


def smoke_health(
    base_url: str,
    endpoint: str,
    *,
    expected_source_sha: str = "",
    expected_source_ref: str = "",
    expected_included_source_sha: str = "",
) -> dict[str, Any]:
    status, body, _ = http_request("GET", join_url(base_url, endpoint))
    require_status("health", status, body)
    payload = parse_health_body(body)
    if not payload:
        raise RuntimeError("health endpoint did not return JSON")
    deployment = validate_deployment_identity(
        payload,
        expected_source_sha=expected_source_sha,
        expected_source_ref=expected_source_ref,
        expected_included_source_sha=expected_included_source_sha,
    )
    return {"status": status, "deployment": deployment}


def smoke_root(base_url: str) -> dict[str, object]:
    status, body, content_type = http_request("GET", join_url(base_url, "/"))
    require_status("root", status, body)
    if not body.strip():
        raise RuntimeError("root endpoint returned an empty body")
    return {"status": status, "content_type": content_type, "bytes": len(body)}


def smoke_claire(base_url: str) -> list[dict[str, object]]:
    checks = [dict(name="root", **smoke_root(base_url))]
    query = urllib.parse.urlencode(
        {
            "q": "Schedule a horseback ride tomorrow at 10am",
            "demo": "true",
        }
    )
    status, body, _ = http_request("GET", join_url(base_url, f"/reply?{query}"), timeout=45)
    require_status("claire demo reply", status, body)
    payload = parse_health_body(body)
    if not payload.get("trace_id") or not payload.get("demo_mode"):
        raise RuntimeError("CLAIRE demo reply did not include trace_id and demo_mode")
    if "Simulated" not in str(payload.get("decision") or "") and "simulat" not in str(payload.get("output") or "").lower():
        raise RuntimeError("CLAIRE demo reply did not clearly remain simulated")
    checks.append(
        {
            "name": "stableride_demo",
            "status": status,
            "trace_id": payload.get("trace_id"),
            "demo_mode": payload.get("demo_mode"),
        }
    )
    return checks


def smoke_veritas(base_url: str) -> list[dict[str, object]]:
    checks = [dict(name="root", **smoke_root(base_url))]
    guided_status, guided_body, guided_type = http_request("GET", join_url(base_url, "/guided"))
    require_status("guided", guided_status, guided_body)
    if "Create New Case" not in guided_body and "Resume Last Case" not in guided_body:
        raise RuntimeError("guided Veritas page did not render case-entry controls")
    checks.append({"name": "guided", "status": guided_status, "content_type": guided_type, "bytes": len(guided_body)})

    status, body, _ = http_request("POST", join_url(base_url, "/demo-matter"), payload={}, timeout=45)
    require_status("demo matter", status, body)
    payload = parse_health_body(body)
    matter = payload.get("matter") if isinstance(payload.get("matter"), dict) else payload
    title = str(matter.get("title") or matter.get("case_name") or payload.get("case_name") or "")
    if "Harbor Point" not in title:
        raise RuntimeError("Veritas demo matter did not load Harbor Point sample data")
    checks.append({"name": "demo_matter", "status": status, "title": title})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safe post-deploy smoke checks against a Hugging Face Space.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--application", choices=("claire", "veritas"), required=True)
    parser.add_argument("--base-url", default="", help="Override resolved Space base URL.")
    parser.add_argument("--space-id", default="", help="Override manifest space_id.")
    parser.add_argument("--expected-source-sha", default="")
    parser.add_argument("--expected-source-ref", default="")
    parser.add_argument("--expected-included-source-sha", default="")
    args = parser.parse_args()

    try:
        manifest = preflight_hf_space.load_manifest(args.manifest)
        base_url = args.base_url.rstrip("/") if args.base_url else resolve_base_url(manifest, space_id=args.space_id)
        health_endpoint = str(manifest.get("health_endpoint") or "/health")
        checks = [
            dict(
                name="health",
                **smoke_health(
                    base_url,
                    health_endpoint,
                    expected_source_sha=args.expected_source_sha,
                    expected_source_ref=args.expected_source_ref,
                    expected_included_source_sha=args.expected_included_source_sha,
                ),
            )
        ]
        if args.application == "claire":
            checks.extend(smoke_claire(base_url))
        else:
            checks.extend(smoke_veritas(base_url))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "application": args.application,
                "base_url": base_url,
                "checks": checks,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
