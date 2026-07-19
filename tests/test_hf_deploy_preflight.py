from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "deploy"))

import preflight_hf_space  # noqa: E402


def write_valid_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Test Space\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def write_manifest(path: Path, *, space_id: str = "Blackstormhorse/Test", sdk: str = "docker") -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "claire-hf-deployment.v1",
                "application": "Test",
                "space_id": space_id,
                "sdk": sdk,
            }
        ),
        encoding="utf-8",
    )


def run_preflight(monkeypatch, manifest: Path, build_dir: Path, *extra: str) -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        ["preflight_hf_space.py", str(manifest), str(build_dir), *extra],
    )
    return preflight_hf_space.main()


def test_preflight_refuses_blank_space_id(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest, space_id="")
    monkeypatch.delenv("HF_SPACE_ID", raising=False)

    result = run_preflight(monkeypatch, manifest, build_dir, "--skip-remote")

    captured = capsys.readouterr()
    assert result == 2
    assert "manifest has no space_id" in captured.err


def test_preflight_skip_remote_accepts_env_space_id(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest, space_id="")
    monkeypatch.setenv("HF_SPACE_ID", "Blackstormhorse/Veritas_Legal")

    result = run_preflight(monkeypatch, manifest, build_dir, "--skip-remote")

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["ok"] is True
    assert payload["mode"] == "local-only"
    assert payload["space_id"] == "Blackstormhorse/Veritas_Legal"


def test_preflight_blocks_unapproved_sdk_transition(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest, sdk="docker")
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {"sdk": "gradio", "sha": "abc123", "runtime": {"stage": "SLEEPING"}},
    )
    monkeypatch.delenv(preflight_hf_space.APPROVAL_ENV, raising=False)

    result = run_preflight(monkeypatch, manifest, build_dir)

    captured = capsys.readouterr()
    assert result == 2
    assert "Space SDK transition requires explicit approval" in captured.err


def test_preflight_allows_approved_sdk_transition(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest, sdk="docker")
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {
            "sdk": "gradio",
            "sha": "abc123",
            "host": "https://example.hf.space",
            "runtime": {"stage": "SLEEPING"},
        },
    )
    monkeypatch.setenv(preflight_hf_space.APPROVAL_ENV, "true")

    result = run_preflight(monkeypatch, manifest, build_dir)

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["ok"] is True
    assert payload["current_sdk"] == "gradio"
    assert payload["package_sdk"] == "docker"
    assert payload["current_sha"] == "abc123"
