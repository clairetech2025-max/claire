from __future__ import annotations

import json
import tempfile
from pathlib import Path

from are_memory_store import AREMemoryStore
from claire_runtime import ClaireRuntime
from claire_runtime_truth import RuntimeTruthEvent, RuntimeTruthSpine, TrailLinkSigner, canonical_json, sha256_value
from trace_logger import TraceLogger


def make_spine(root: Path) -> RuntimeTruthSpine:
    return RuntimeTruthSpine(root / "runtime_truth.jsonl", signer=TrailLinkSigner(b"unit-key", "unit"))


def test_deterministic_hashing_is_stable():
    left = {"b": 2, "a": {"z": 3, "m": [1, 2]}}
    right = {"a": {"m": [1, 2], "z": 3}, "b": 2}

    assert canonical_json(left) == canonical_json(right)
    assert sha256_value(left) == sha256_value(right)


def test_valid_append_and_chain_verification():
    with tempfile.TemporaryDirectory() as td:
        spine = make_spine(Path(td))
        first = spine.append(RuntimeTruthEvent(
            event_type="3crp.ingress",
            session_id="s",
            turn_id="t",
            actor={"type": "component", "id": "3crp", "component": "ingress"},
            payload={"input_hash": "abc"},
        ))
        second = spine.append(RuntimeTruthEvent(
            event_type="output.released",
            session_id="s",
            turn_id="t",
            actor={"type": "component", "id": "runtime", "component": "output"},
            parent_event_ids=[first["event_id"]],
        ))

        verify = spine.verify()
        assert verify["valid"] is True
        assert verify["records"] == 2
        assert second["previous_hash"] == first["record_hash"]


def test_payload_tampering_is_detected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        spine = make_spine(root)
        spine.append(RuntimeTruthEvent(
            event_type="q_insight.result",
            session_id="s",
            turn_id="t",
            actor={"type": "component", "id": "q", "component": "q_insight"},
            payload={"confidence": 0.8},
        ))
        path = root / "runtime_truth.jsonl"
        row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        row["payload"]["confidence"] = 0.1
        path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

        assert spine.verify()["reason"] == "payload_hash_mismatch"


def test_previous_hash_tampering_is_detected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        spine = make_spine(root)
        spine.append(RuntimeTruthEvent(event_type="a", session_id="s", turn_id="t", actor={"type": "component", "id": "a"}))
        spine.append(RuntimeTruthEvent(event_type="b", session_id="s", turn_id="t", actor={"type": "component", "id": "b"}))
        path = root / "runtime_truth.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[1]["previous_hash"] = "bad"
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

        assert spine.verify()["reason"] == "previous_hash_mismatch"


def test_duplicate_event_id_rejected():
    with tempfile.TemporaryDirectory() as td:
        spine = make_spine(Path(td))
        event = RuntimeTruthEvent(event_id="evt_duplicate", event_type="a", session_id="s", turn_id="t", actor={"type": "component", "id": "a"})
        spine.append(event)
        try:
            spine.append(event)
            raise AssertionError("duplicate event id should fail")
        except ValueError as exc:
            assert "duplicate" in str(exc)


def test_turn_capsule_verifies_against_events():
    with tempfile.TemporaryDirectory() as td:
        spine = make_spine(Path(td))
        spine.append(RuntimeTruthEvent(event_type="3crp.ingress", session_id="s", turn_id="t", actor={"type": "component", "id": "3crp"}))
        spine.append(RuntimeTruthEvent(event_type="gyro.orientation", session_id="s", turn_id="t", actor={"type": "component", "id": "gyro"}))
        spine.append(RuntimeTruthEvent(event_type="output.released", session_id="s", turn_id="t", actor={"type": "component", "id": "runtime"}))

        capsule = spine.seal_turn(session_id="s", turn_id="t", input_text="hello", final_output="hi")

        assert capsule["event_count"] == 3
        assert spine.verify_turn_capsule(capsule)["valid"] is True


def test_runtime_model_call_is_after_governance_events():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runtime = ClaireRuntime(
            memory_store=AREMemoryStore(root / "memory.db"),
            trace_logger=TraceLogger(root / "traces.jsonl", root / "traces.db"),
        )
        runtime.runtime_truth = make_spine(root)

        result = runtime.handle_user_message(
            "steve",
            "s",
            "Explain CLAIRE runtime architecture in one sentence.",
            {"provider_generate": lambda messages, config: "CLAIRE is a governed runtime with recall, orientation, validation, and trace."},
        )

        events = runtime.runtime_truth.events()
        event_types = [event["event_type"] for event in events if event["turn_id"] == result["truth_spine"]["turn_id"]]
        assert "3crp.ingress" in event_types
        assert "are.consulted" in event_types
        assert "recognition_rail.result" in event_types
        assert "q_insight.result" in event_types
        assert "gyro.orientation" in event_types
        assert "3crp.post_gyro_authorization" in event_types
        assert event_types.index("model.authorization") < event_types.index("model.invocation")
        assert event_types.index("3crp.post_gyro_authorization") < event_types.index("model.authorization")
        assert event_types[-1] == "turn.sealed"
        assert result["truth_spine"]["verification"]["valid"] is True


def test_clarification_gate_blocks_model_invocation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runtime = ClaireRuntime(
            memory_store=AREMemoryStore(root / "memory.db"),
            trace_logger=TraceLogger(root / "traces.jsonl", root / "traces.db"),
        )
        runtime.runtime_truth = make_spine(root)

        def fail_if_called(messages, config):
            raise AssertionError("model should not run when Q Insight/3CRP holds the turn")

        result = runtime.handle_user_message(
            "steve",
            "s",
            "that",
            {"provider_generate": fail_if_called},
        )
        event_types = [event["event_type"] for event in runtime.runtime_truth.events() if event["turn_id"] == result["truth_spine"]["turn_id"]]

        assert "3crp.post_gyro_authorization" in event_types
        assert "model.invocation" not in event_types
        assert result["answer_mode"] == "clarify"


def test_memory_write_authorization_precedes_durable_commit(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runtime = ClaireRuntime(
            memory_store=AREMemoryStore(root / "memory.db"),
            trace_logger=TraceLogger(root / "traces.jsonl", root / "traces.db"),
        )
        runtime.runtime_truth = make_spine(root)

        monkeypatch.setattr(
            "claire_runtime.should_commit_memory",
            lambda message, lane, eligibility: (True, "forced test durable write"),
        )

        def fake_commit_memory(**kwargs):
            del kwargs
            event_types = [event["event_type"] for event in runtime.runtime_truth.events()]
            assert "3crp.memory_write_authorization" in event_types
            assert "memory.commit_result" not in event_types
            return True, {
                "memory_id": "mem_test_authorized",
                "source": "test",
            }

        monkeypatch.setattr(runtime, "_commit_memory", fake_commit_memory)

        result = runtime.handle_user_message(
            "steve",
            "s",
            "Remember this: the architecture checkpoint is memory gate first.",
            {"provider_generate": lambda messages, config: "Recorded with authorization first."},
        )

        event_types = [
            event["event_type"]
            for event in runtime.runtime_truth.events()
            if event["turn_id"] == result["truth_spine"]["turn_id"]
        ]
        assert event_types.index("3crp.memory_write_authorization") < event_types.index("memory.commit_result")
        assert result["memory_written"] is True
