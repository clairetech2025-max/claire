from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "deploy"))

import hf_deploy_status  # noqa: E402
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


def run_status(monkeypatch, manifest: Path, build_dir: Path, *extra: str) -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        ["hf_deploy_status.py", "--target", str(manifest), str(build_dir), *extra],
    )
    return hf_deploy_status.main()


def test_space_id_override_uses_manifest_filename() -> None:
    manifest = Path("deploy/huggingface/veritas.manifest.json")
    overrides = {"veritas.manifest.json": "Blackstormhorse/Veritas_Legal"}

    result = hf_deploy_status.effective_space_id_for_status(
        manifest,
        {"application": "Veritas Legal", "space_id": ""},
        overrides,
    )

    assert result == "Blackstormhorse/Veritas_Legal"


def test_status_reports_blank_space_id_blocker(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest, space_id="")
    monkeypatch.delenv("HF_SPACE_ID", raising=False)
    monkeypatch.setattr(hf_deploy_status, "hf_auth_status", lambda: {"available": True})

    result = run_status(monkeypatch, manifest, build_dir, "--skip-remote")

    payload = json.loads(capsys.readouterr().out)
    assert result == 2
    assert payload["ok"] is False
    assert "manifest has no space_id" in payload["targets"][0]["blockers"][0]


def test_status_reports_missing_auth_blocker(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest)
    monkeypatch.setattr(hf_deploy_status, "hf_auth_status", lambda: {"available": False})

    result = run_status(monkeypatch, manifest, build_dir)

    payload = json.loads(capsys.readouterr().out)
    assert result == 2
    assert "Hugging Face authentication unavailable" in payload["targets"][0]["blockers"]


def test_status_skip_remote_keeps_missing_auth_as_warning(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest)
    monkeypatch.setattr(hf_deploy_status, "hf_auth_status", lambda: {"available": False})

    result = run_status(monkeypatch, manifest, build_dir, "--skip-remote")

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["mode"] == "local-only"
    assert payload["targets"][0]["local_ready"] is True
    assert payload["targets"][0]["ready_for_upload"] is False
    assert not payload["targets"][0]["blockers"]
    assert payload["targets"][0]["warnings"]


def test_status_blocks_unapproved_sdk_transition(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest, sdk="docker")
    monkeypatch.setenv("HF_TOKEN", "token-present")
    monkeypatch.setattr(hf_deploy_status, "hf_auth_status", lambda: {"available": True})
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {"id": "Blackstormhorse/Test", "sdk": "gradio", "sha": "abc123"},
    )
    monkeypatch.delenv(preflight_hf_space.APPROVAL_ENV, raising=False)

    result = run_status(monkeypatch, manifest, build_dir)

    payload = json.loads(capsys.readouterr().out)
    assert result == 2
    assert payload["targets"][0]["space"]["checked"] is True
    assert any("requires HF_APPROVE_SDK_TRANSITION=true" in item for item in payload["targets"][0]["blockers"])


def test_status_allows_approved_ready_target(tmp_path: Path, monkeypatch, capsys) -> None:
    build_dir = tmp_path / "build"
    manifest = tmp_path / "manifest.json"
    write_valid_tree(build_dir)
    write_manifest(manifest, sdk="docker")
    monkeypatch.setenv("HF_TOKEN", "token-present")
    monkeypatch.setenv(preflight_hf_space.APPROVAL_ENV, "true")
    monkeypatch.setattr(hf_deploy_status, "hf_auth_status", lambda: {"available": True})
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {"id": "Blackstormhorse/Test", "sdk": "docker", "sha": "abc123"},
    )

    result = run_status(monkeypatch, manifest, build_dir)

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["ok"] is True
    assert payload["targets"][0]["ready_for_upload"] is True
