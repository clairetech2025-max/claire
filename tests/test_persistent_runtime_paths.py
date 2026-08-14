from pathlib import Path

from claire_runtime_truth import RuntimeTruthSpine
from temporal_engine import TemporalEngine
from trace_logger import TraceLogger


def test_runtime_state_paths_follow_environment(monkeypatch, tmp_path: Path):
    trace_path = tmp_path / "traces" / "runtime.jsonl"
    trace_db_path = tmp_path / "traces" / "runtime.db"
    truth_path = tmp_path / "traces" / "truth.jsonl"
    degraded_path = tmp_path / "traces" / "truth-degraded.jsonl"
    temporal_path = tmp_path / "temporal" / "events.jsonl"

    monkeypatch.setenv("CLAIRE_TRACE_PATH", str(trace_path))
    monkeypatch.setenv("CLAIRE_TRACE_DB_PATH", str(trace_db_path))
    monkeypatch.setenv("CLAIRE_RUNTIME_TRUTH_SPINE", str(truth_path))
    monkeypatch.setenv("CLAIRE_RUNTIME_TRUTH_SPINE_DEGRADED", str(degraded_path))
    monkeypatch.setenv("CLAIRE_TEMPORAL_STATE_PATH", str(temporal_path))

    trace = TraceLogger()
    truth = RuntimeTruthSpine.from_env()
    temporal = TemporalEngine()

    assert trace.path == trace_path
    assert trace.db_path == trace_db_path
    assert truth.path == truth_path
    assert truth.degraded_path == degraded_path
    assert temporal.path == temporal_path
    assert trace_db_path.exists()
