from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import preflight_hf_space
from validate_hf_tree import validate_tree


def command_available(command: str) -> bool:
    try:
        result = subprocess.run(
            [command, "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def hf_auth_status() -> dict[str, object]:
    if os.getenv("HF_TOKEN"):
        return {
            "available": True,
            "method": "HF_TOKEN",
            "identity": "token-present",
        }
    try:
        result = subprocess.run(
            ["hf", "auth", "whoami"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "method": "hf auth whoami",
            "error": str(exc),
        }
    if result.returncode != 0:
        return {
            "available": False,
            "method": "hf auth whoami",
            "error": (result.stderr or result.stdout).strip(),
        }
    identity = (result.stdout or "").strip().splitlines()[0] if result.stdout.strip() else "logged-in"
    return {
        "available": True,
        "method": "hf auth whoami",
        "identity": identity,
    }


def github_secret_status(repo: str, required_secrets: list[str]) -> dict[str, object]:
    required = [secret.strip() for secret in required_secrets if secret.strip()]
    if not repo:
        return {
            "checked": False,
            "reason": "GitHub repository not provided",
            "required_secrets": required,
            "missing_secrets": required,
        }
    if not required:
        return {
            "checked": False,
            "reason": "no required GitHub secrets requested",
            "repo": repo,
            "required_secrets": [],
            "missing_secrets": [],
        }
    if not command_available("gh"):
        return {
            "checked": False,
            "reason": "gh CLI unavailable",
            "repo": repo,
            "required_secrets": required,
            "missing_secrets": required,
        }
    try:
        result = subprocess.run(
            ["gh", "secret", "list", "--repo", repo],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "checked": False,
            "reason": str(exc),
            "repo": repo,
            "required_secrets": required,
            "missing_secrets": required,
        }
    if result.returncode != 0:
        return {
            "checked": False,
            "reason": (result.stderr or result.stdout).strip() or "gh secret list failed",
            "repo": repo,
            "required_secrets": required,
            "missing_secrets": required,
        }
    present = {
        line.split()[0].strip()
        for line in (result.stdout or "").splitlines()
        if line.strip()
    }
    missing = [secret for secret in required if secret not in present]
    return {
        "checked": True,
        "repo": repo,
        "required_secrets": required,
        "missing_secrets": missing,
        "present": not missing,
    }


def inspect_space(space_id: str, *, remote: bool) -> dict[str, object]:
    if not remote:
        return {"checked": False, "reason": "remote check disabled"}
    if not preflight_hf_space.token_available():
        return {
            "checked": False,
            "reason": "Hugging Face authentication unavailable",
        }
    try:
        space = preflight_hf_space.hub_get(f"/spaces/{space_id}")
    except RuntimeError as exc:
        return {
            "checked": False,
            "error": str(exc),
        }
    runtime = space.get("runtime") if isinstance(space.get("runtime"), dict) else {}
    return {
        "checked": True,
        "id": space.get("id") or space_id,
        "private": space.get("private"),
        "sdk": preflight_hf_space.live_space_sdk(space) or "unknown",
        "sha": space.get("sha"),
        "host": space.get("host"),
        "runtime_stage": runtime.get("stage"),
        "hardware": runtime.get("hardware") or runtime.get("requested_hardware"),
    }


def space_id_override_map(values: list[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("--space-id entries must use MANIFEST=SPACE_ID")
        manifest, space_id = value.split("=", 1)
        overrides[manifest.strip()] = space_id.strip()
    return overrides


def manifest_key(path: Path) -> str:
    return path.as_posix()


def effective_space_id_for_status(manifest_path: Path, manifest: dict[str, Any], overrides: dict[str, str]) -> str:
    for key in {manifest_key(manifest_path), manifest_path.name, manifest.get("application", "")}:
        if key and key in overrides:
            return overrides[key]
    return preflight_hf_space.effective_space_id(manifest)


def manifest_status(
    manifest_path: Path,
    build_dir: Path,
    *,
    remote: bool,
    space_id_overrides: dict[str, str],
) -> dict[str, Any]:
    manifest = preflight_hf_space.load_manifest(manifest_path)
    errors = validate_tree(build_dir)
    space_id = effective_space_id_for_status(manifest_path, manifest, space_id_overrides)
    package_sdk = str(manifest.get("sdk") or "").strip().lower()
    blockers: list[str] = []
    warnings: list[str] = []

    if errors:
        blockers.extend(errors)
    if not space_id:
        blockers.append("manifest has no space_id and HF_SPACE_ID is unset")
    if not package_sdk:
        blockers.append("manifest missing sdk")

    auth = hf_auth_status()
    if remote and not auth["available"]:
        blockers.append("Hugging Face authentication unavailable")
    elif not remote and not auth["available"]:
        warnings.append("Hugging Face authentication unavailable; remote Space inspection skipped")

    space = inspect_space(space_id, remote=remote) if space_id else {"checked": False}
    live_sdk = str(space.get("sdk") or "").strip().lower() if space.get("checked") else ""
    if live_sdk and package_sdk and live_sdk != package_sdk:
        transition_approved = preflight_hf_space.approval_enabled()
        message = f"Space SDK transition: current={live_sdk}, package={package_sdk}"
        if transition_approved:
            warnings.append(message + " approved by HF_APPROVE_SDK_TRANSITION")
        else:
            blockers.append(message + " requires HF_APPROVE_SDK_TRANSITION=true")

    return {
        "application": manifest.get("application"),
        "manifest": str(manifest_path),
        "build_dir": str(build_dir),
        "space_id": space_id,
        "package_sdk": package_sdk,
        "local_tree_valid": not errors,
        "remote_check_enabled": remote,
        "auth": auth,
        "space": space,
        "warnings": warnings,
        "blockers": blockers,
        "local_ready": not errors and bool(space_id) and bool(package_sdk),
        "ready_for_upload": remote and not blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        action="append",
        nargs=2,
        metavar=("MANIFEST", "BUILD_DIR"),
        required=True,
        help="Manifest and already-built Space tree to evaluate.",
    )
    parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Do not inspect live Spaces. This still reports auth and local build status.",
    )
    parser.add_argument(
        "--space-id",
        action="append",
        default=[],
        metavar="MANIFEST=SPACE_ID",
        help=(
            "Override a blank or environment-derived Space ID for one target. "
            "MANIFEST may be the manifest path, manifest filename, or application name."
        ),
    )
    parser.add_argument(
        "--github-repo",
        default="",
        help="Optional GitHub repository, for example clairetech2025-max/claire, used to check deploy secret names.",
    )
    parser.add_argument(
        "--require-github-secret",
        action="append",
        default=[],
        metavar="SECRET_NAME",
        help="Require a GitHub Actions secret name to exist in --github-repo. Secret values are never read.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Always exit 0 after printing status JSON. The JSON ok field still reports readiness truthfully.",
    )
    args = parser.parse_args()
    try:
        overrides = space_id_override_map(args.space_id)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2

    statuses = [
        manifest_status(
            Path(manifest),
            Path(build_dir),
            remote=not args.skip_remote,
            space_id_overrides=overrides,
        )
        for manifest, build_dir in args.target
    ]
    ok = (
        all(status["local_ready"] for status in statuses)
        if args.skip_remote
        else all(status["ready_for_upload"] for status in statuses)
    )
    github_actions = github_secret_status(args.github_repo, args.require_github_secret)
    if args.require_github_secret and github_actions.get("missing_secrets"):
        ok = False
    payload = {
        "ok": ok,
        "mode": "local-only" if args.skip_remote else "remote-preflight",
        "github_actions": github_actions,
        "targets": statuses,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.report_only:
        return 0
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
