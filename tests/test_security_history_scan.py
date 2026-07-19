from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import security_history_scan


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def commit(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def init_repo(repo: Path) -> None:
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test User")


def test_history_scan_detects_removed_secret_without_printing_value(tmp_path: Path) -> None:
    init_repo(tmp_path)
    (tmp_path / "config.py").write_text(
        "AZURE = 'DefaultEndpointsProtocol=https;AccountName=x;Account"
        "Key=abcdefghijklmnopqrstuvwxyz=='\n",
        encoding="utf-8",
    )
    exposed_commit = commit(tmp_path, "add exposed config")
    (tmp_path / "config.py").write_text("AZURE = None\n", encoding="utf-8")
    commit(tmp_path, "sanitize config")

    findings = security_history_scan.scan_history(tmp_path)

    assert findings == [
        {
            "kind": "azure_connection_string",
            "commit": exposed_commit,
            "path": "config.py",
            "line": 1,
        }
    ]


def test_history_scan_passes_clean_history(tmp_path: Path) -> None:
    init_repo(tmp_path)
    (tmp_path / "config.py").write_text("AZURE_CONNECTION_STRING = 'set via env'\n")
    commit(tmp_path, "add clean config")

    assert security_history_scan.scan_history(tmp_path) == []
