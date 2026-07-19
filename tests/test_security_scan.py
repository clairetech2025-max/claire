from __future__ import annotations

from pathlib import Path

import pytest

from scripts import security_scan


def fixture_secret(prefix: str, body: str) -> str:
    return prefix + body


def test_security_scan_allows_secret_names_without_values(tmp_path: Path) -> None:
    path = tmp_path / "docs.md"
    path.write_text("Required secret names: HF_TOKEN, OPENAI_API_KEY, AZURE_CONNECTION_STRING\n")

    assert security_scan.scan_paths(tmp_path, [path]) == []


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        (f"key = '{fixture_secret('sk-', 'proj-abcdefghijklmnopqrstuvwxyz123456')}'\n", "openai_api_key"),
        (f"token = '{fixture_secret('hf', '_abcdefghijklmnopqrstuv')}'\n", "huggingface_token"),
        (f"token = '{fixture_secret('gh', 'p_abcdefghijklmnopqrstuv')}'\n", "github_token"),
        (
            "DefaultEndpointsProtocol=https;AccountName=x;Account"
            "Key=abcdefghijklmnopqrstuvwxyz==\n",
            "azure_connection_string",
        ),
        ("-----BEGIN " + "PRIVATE KEY-----\n", "private_key"),
    ],
)
def test_security_scan_detects_secret_shaped_values(
    tmp_path: Path,
    content: str,
    kind: str,
) -> None:
    path = tmp_path / "secret.txt"
    path.write_text(content)

    findings = security_scan.scan_paths(tmp_path, [path])

    assert len(findings) == 1
    assert findings[0].kind == kind
    assert findings[0].path == "secret.txt"


def test_security_scan_detects_prohibited_private_artifacts(tmp_path: Path) -> None:
    path = tmp_path / "uploads" / "matter.db"
    path.parent.mkdir()
    path.write_text("not secret, but private runtime data")

    findings = security_scan.scan_paths(tmp_path, [path])

    assert {finding.kind for finding in findings} == {"private_runtime_data", "database"}
