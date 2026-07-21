from __future__ import annotations

import json

from fastapi.testclient import TestClient

import claire_gui


def _events(response_text: str) -> list[dict]:
    return [json.loads(line) for line in response_text.splitlines() if line.strip()]


def test_reply_stream_post_route_exists_for_long_prompts(monkeypatch):
    monkeypatch.setattr(
        claire_gui,
        "build_reply",
        lambda q, debug=False: ("GO", f"streamed response for {len(q)} chars", "trace_test_stream"),
    )
    client = TestClient(claire_gui.app)
    prompt = "Deep research assignment. " * 120

    response = client.post("/reply-stream", json={"q": prompt})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _events(response.text)
    assert events[0]["type"] == "start"
    assert any(event["type"] == "chunk" for event in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["data"]["source"] == "GO"
    assert done["data"]["trace_id"] == "trace_test_stream"


def test_reply_get_stream_query_route_exists(monkeypatch):
    monkeypatch.setattr(
        claire_gui,
        "build_reply",
        lambda q, debug=False: ("GO", "short streamed response", "trace_test_get_stream"),
    )
    client = TestClient(claire_gui.app)

    response = client.get("/reply", params={"stream": "true", "q": "hello"})

    assert response.status_code == 200
    events = _events(response.text)
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"
    assert events[-1]["data"]["trace_id"] == "trace_test_get_stream"


def test_trace_route_returns_runtime_trace_when_demo_trace_missing(monkeypatch):
    trace_id = "trace_runtime_route_test"
    runtime_trace = {"trace_id": trace_id, "steps": ["runtime_trace_logging"], "source": "runtime"}

    class Runtime:
        def get_trace(self, requested_trace_id):
            assert requested_trace_id == trace_id
            return runtime_trace

    monkeypatch.setattr(claire_gui, "CLAIRE_GOVERNED_RUNTIME", Runtime())
    client = TestClient(claire_gui.app)

    response = client.get(f"/trace/{trace_id}")

    assert response.status_code == 200
    assert response.json() == runtime_trace
