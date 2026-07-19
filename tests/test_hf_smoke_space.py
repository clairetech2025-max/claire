from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "deploy"))

import hf_smoke_space  # noqa: E402
import preflight_hf_space  # noqa: E402


def test_derived_space_url_matches_hugging_face_host_shape() -> None:
    assert (
        hf_smoke_space.derived_space_url("Blackstormhorse/CLAIRE_Control_Interface")
        == "https://blackstormhorse-claire-control-interface.hf.space"
    )


def test_resolve_base_url_prefers_live_hub_host(monkeypatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "token-present")
    monkeypatch.setattr(preflight_hf_space, "token_available", lambda: True)
    monkeypatch.setattr(
        preflight_hf_space,
        "hub_get",
        lambda path: {"host": "https://live.example.hf.space", "runtime": {"stage": "RUNNING"}},
    )

    result = hf_smoke_space.resolve_base_url({"space_url": "https://manifest.example"}, space_id="Owner/Space")

    assert result == "https://live.example.hf.space"


def test_smoke_health_validates_deployment_identity(monkeypatch) -> None:
    body = json.dumps(
        {
            "ok": True,
            "deployment": {
                "source_git_sha": "abc123",
                "source_git_ref": "main",
                "included_sources": [{"source_git_sha": "veritas456"}],
            },
        }
    )
    monkeypatch.setattr(hf_smoke_space, "http_request", lambda *args, **kwargs: (200, body, "application/json"))

    result = hf_smoke_space.smoke_health(
        "https://space.example",
        "/health",
        expected_source_sha="abc123",
        expected_source_ref="main",
        expected_included_source_sha="veritas456",
    )

    assert result["status"] == 200
    assert result["deployment"]["source_git_sha"] == "abc123"


def test_smoke_claire_requires_trace_and_simulated_demo(monkeypatch) -> None:
    urls: list[str] = []

    def fake_request(method: str, url: str, **kwargs):
        urls.append(url)
        if url.endswith("/"):
            return 200, "<html>CLAIRE</html>", "text/html"
        return (
            200,
            json.dumps(
                {
                    "trace_id": "trace_1",
                    "demo_mode": True,
                    "decision": "Simulated action only",
                    "output": "No real-world execution performed.",
                }
            ),
            "application/json",
        )

    monkeypatch.setattr(hf_smoke_space, "http_request", fake_request)

    checks = hf_smoke_space.smoke_claire("https://space.example")

    assert checks[0]["name"] == "root"
    assert checks[1]["name"] == "stableride_demo"
    assert checks[1]["trace_id"] == "trace_1"
    assert any("Schedule+a+horseback+ride+tomorrow" in url for url in urls)


def test_smoke_veritas_loads_guided_page_and_demo_matter(monkeypatch) -> None:
    def fake_request(method: str, url: str, **kwargs):
        if url.endswith("/guided"):
            return 200, "<button>Create New Case</button>", "text/html"
        if url.endswith("/demo-matter"):
            return 200, json.dumps({"matter": {"title": "Harbor Point Commercial Dispute"}}), "application/json"
        return 200, "<html>Veritas</html>", "text/html"

    monkeypatch.setattr(hf_smoke_space, "http_request", fake_request)

    checks = hf_smoke_space.smoke_veritas("https://space.example")

    assert [check["name"] for check in checks] == ["root", "guided", "demo_matter"]


def test_smoke_claire_rejects_non_simulated_demo(monkeypatch) -> None:
    def fake_request(method: str, url: str, **kwargs):
        if url.endswith("/"):
            return 200, "<html>CLAIRE</html>", "text/html"
        return 200, json.dumps({"trace_id": "trace_1", "demo_mode": True, "decision": "Scheduled"}), "application/json"

    monkeypatch.setattr(hf_smoke_space, "http_request", fake_request)

    with pytest.raises(RuntimeError, match="simulated"):
        hf_smoke_space.smoke_claire("https://space.example")
