from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_value(args: list[str], default: str = "unknown", *, cwd: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=cwd or Path.cwd(),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        ).strip() or default
    except (OSError, subprocess.SubprocessError):
        return default


def source_identity(root: Path, source: str) -> dict | None:
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = (root / source_path).resolve()
    probe_path = source_path if source_path.exists() else source_path.parent
    if not probe_path.exists():
        return None
    git_root = git_value(["rev-parse", "--show-toplevel"], "", cwd=probe_path)
    if not git_root:
        return None
    git_root_path = Path(git_root)
    try:
        rel = source_path.relative_to(root).as_posix()
    except ValueError:
        rel = source
    return {
        "path": rel,
        "git_root_name": git_root_path.name,
        "source_git_sha": git_value(["rev-parse", "HEAD"], cwd=git_root_path),
        "source_git_ref": git_value(["branch", "--show-current"], cwd=git_root_path),
    }


def included_source_identities(manifest: dict) -> list[dict]:
    root = Path.cwd()
    identities: list[dict] = []
    seen: set[tuple[str, str]] = set()
    sources = []
    if manifest.get("root_source_path"):
        sources.append(str(manifest["root_source_path"]))
    sources.extend(str(item) for item in manifest.get("source_paths", []))
    for source in sources:
        identity = source_identity(root, source)
        if not identity:
            continue
        key = (str(identity["git_root_name"]), str(identity["source_git_sha"]))
        if key in seen:
            continue
        seen.add(key)
        identities.append(identity)
    return identities


def deployment_identity(manifest: dict) -> dict:
    source_sha = os.getenv("GITHUB_SHA") or git_value(["rev-parse", "HEAD"])
    source_ref = os.getenv("GITHUB_REF_NAME") or git_value(["branch", "--show-current"])
    return {
        "schema_version": "claire-hf-deployment-identity.v1",
        "application": manifest.get("application") or "unknown",
        "space_id": manifest.get("space_id") or "",
        "source_repository": os.getenv("GITHUB_REPOSITORY") or "clairetech2025-max/claire",
        "source_git_sha": source_sha,
        "source_git_ref": source_ref,
        "included_sources": included_source_identities(manifest),
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def should_exclude(path: Path, patterns: list[str]) -> bool:
    text = path.as_posix()
    for pattern in patterns:
        clean = pattern.strip()
        if not clean:
            continue
        if clean.endswith("/"):
            dirname = clean.rstrip("/")
            if text == dirname or text.startswith(clean) or dirname in path.parts:
                return True
        if fnmatch.fnmatch(text, clean) or fnmatch.fnmatch(path.name, clean):
            return True
    return False


def copy_source(
    root: Path,
    source: str,
    target: Path,
    excludes: list[str],
    *,
    flatten: bool = False,
) -> None:
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = (root / source_path).resolve()
    if not source_path.exists():
        return
    destination = target / source_path.name
    if source_path.is_file():
        rel = source_path.relative_to(root) if source_path.is_relative_to(root) else Path(source_path.name)
        if should_exclude(rel, excludes):
            return
        if flatten:
            destination = target / source_path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        return
    for item in source_path.rglob("*"):
        rel = item.relative_to(root) if item.is_relative_to(root) else item.relative_to(source_path.parent)
        if flatten:
            rel = item.relative_to(source_path)
        if should_exclude(rel, excludes):
            continue
        dest = target / rel
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    root = Path.cwd()
    manifest = load_manifest(args.manifest)
    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)
    root_source = manifest.get("root_source_path")
    if root_source:
        copy_source(root, str(root_source), args.output, manifest.get("exclude", []), flatten=True)
    for source in manifest["source_paths"]:
        copy_source(root, source, args.output, manifest.get("exclude", []))
    for pattern in manifest.get("source_globs", []):
        for path in sorted(root.glob(pattern)):
            copy_source(root, path.as_posix(), args.output, manifest.get("exclude", []))
    (args.output / "deployment.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output / "deployment.identity.json").write_text(
        json.dumps(deployment_identity(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
