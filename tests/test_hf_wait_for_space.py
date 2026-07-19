from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "deploy"))

import hf_wait_for_space  # noqa: E402
import preflight_hf_space  # noqa: E402


def write_manifest(path: Path, *, space_id: str = "Blackstormhorse/Test", endpoint: str = "/health") -> None:
    path.write_text(
        json.dumps(
            {
                "application": "Test",
                "space_id": space_id,
                "health_endpoint": endpoint,
            }
        ),
        encoding="utf-8",
    )


def run_wait(monkeypatch, manifest: Path, *extra: str) -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        ["hf_wait_for_space.py", str(manifest), "--timeout", "1", "--interval", "0", *extra],
    )
    return hf_wait_for_space.main()


def test_health_url_normalizes_slashes() -> None:
    assert hf_wait_for_space.health_url("https://example.hf.space/", "health") == "https://example.hf.space/health"
    assert hf_wait_for_space.health_url("https://example.hf.space", "/") == "https://example.hf.space/"


def test_wait_reports_running_space_and_health(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest)
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {
            "id": "Blackstormhorse/Test",
            "sha": "abc123",
            "host": "https://test.hf.space",
            "sdk": "docker",
            "runtime": {"stage": "RUNNING", "hardware": "cpu-basic"},
        },
    )
    monkeypatch.setattr(
        hf_wait_for_space,
        "http_get_json_or_text",
        lambda url: (200, '{"ok": true, "deployment": {"source_git_sha": "src123"}}'),
    )

    result = run_wait(monkeypatch, manifest)

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["ok"] is True
    assert payload["runtime"]["runtime_stage"] == "RUNNING"
    assert payload["health"]["url"] == "https://test.hf.space/health"
    assert payload["health"]["deployment"]["source_git_sha"] == "src123"


def test_wait_can_require_expected_source_sha(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest)
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {
            "id": "Blackstormhorse/Test",
            "sha": "abc123",
            "host": "https://test.hf.space",
            "sdk": "docker",
            "runtime": {"stage": "RUNNING", "hardware": "cpu-basic"},
        },
    )
    monkeypatch.setattr(
        hf_wait_for_space,
        "http_get_json_or_text",
        lambda url: (200, '{"ok": true, "deployment": {"source_git_sha": "src123"}}'),
    )

    result = run_wait(monkeypatch, manifest, "--expected-source-sha", "src123")

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["health"]["deployment"]["source_git_sha"] == "src123"


def test_wait_rejects_stale_source_sha(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest)
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {
            "id": "Blackstormhorse/Test",
            "sha": "abc123",
            "host": "https://test.hf.space",
            "sdk": "docker",
            "runtime": {"stage": "RUNNING", "hardware": "cpu-basic"},
        },
    )
    monkeypatch.setattr(
        hf_wait_for_space,
        "http_get_json_or_text",
        lambda url: (200, '{"ok": true, "deployment": {"source_git_sha": "old456"}}'),
    )

    result = run_wait(monkeypatch, manifest, "--expected-source-sha", "src123")

    assert result == 1
    assert "different source SHA" in capsys.readouterr().err


def test_wait_can_require_included_source_sha(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest)
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {
            "id": "Blackstormhorse/Test",
            "sha": "abc123",
            "host": "https://test.hf.space",
            "sdk": "docker",
            "runtime": {"stage": "RUNNING", "hardware": "cpu-basic"},
        },
    )
    monkeypatch.setattr(
        hf_wait_for_space,
        "http_get_json_or_text",
        lambda url: (
            200,
            json.dumps(
                {
                    "ok": True,
                    "deployment": {
                        "source_git_sha": "claire123",
                        "included_sources": [{"name": "veritas", "source_git_sha": "veritas456"}],
                    },
                }
            ),
        ),
    )

    result = run_wait(monkeypatch, manifest, "--expected-included-source-sha", "veritas456")

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["health"]["deployment"]["included_sources"][0]["source_git_sha"] == "veritas456"


def test_wait_fails_without_auth(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest)
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: False)

    result = run_wait(monkeypatch, manifest)

    assert result == 2
    assert "Hugging Face authentication unavailable" in capsys.readouterr().err


def test_wait_fails_on_runtime_error_stage(monkeypatch) -> None:
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {"id": "Blackstormhorse/Test", "runtime": {"stage": "RUNTIME_ERROR"}},
    )

    try:
        hf_wait_for_space.wait_for_running("Blackstormhorse/Test", timeout_seconds=1, interval_seconds=0)
    except RuntimeError as exc:
        assert "RUNTIME_ERROR" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
