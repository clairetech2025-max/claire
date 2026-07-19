from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from security_scan import SECRET_PATTERNS
except ModuleNotFoundError:
    from scripts.security_scan import SECRET_PATTERNS


def git_lines(root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def commit_paths(root: Path, commit: str) -> list[str]:
    return git_lines(root, ["ls-tree", "-r", "--name-only", commit])


def show_file(root: Path, commit: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0 or b"\0" in result.stdout[:4096]:
        return None
    return result.stdout.decode("utf-8", errors="ignore")


def scan_text(commit: str, path: str, text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "kind": kind,
                        "commit": commit,
                        "path": path,
                        "line": line_number,
                    }
                )
    return findings


def scan_history(root: Path, *, max_commits: int | None = None) -> list[dict[str, object]]:
    commits = git_lines(root, ["rev-list", "--all"])
    if max_commits is not None:
        commits = commits[:max_commits]

    findings: list[dict[str, object]] = []
    seen_blobs: set[tuple[str, str]] = set()
    for commit in commits:
        for path in commit_paths(root, commit):
            blob = git_lines(root, ["rev-parse", f"{commit}:{path}"])
            blob_key = (blob[0], path) if blob else (commit, path)
            if blob_key in seen_blobs:
                continue
            seen_blobs.add(blob_key)
            text = show_file(root, commit, path)
            if text is None:
                continue
            findings.extend(scan_text(commit, path, text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan Git history for secret-shaped values without printing secret contents."
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=None,
        help="Optional cap for local testing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of text lines.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Always exit 0 after reporting findings.",
    )
    args = parser.parse_args()

    root = Path.cwd().resolve()
    findings = scan_history(root, max_commits=args.max_commits)
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=2, sort_keys=True))
    elif findings:
        for finding in findings:
            print(
                f"{finding['kind']}: {finding['commit']}:{finding['path']}:{finding['line']}",
                file=sys.stderr,
            )
    else:
        print("security history scan passed")

    if args.report_only:
        return 0
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
