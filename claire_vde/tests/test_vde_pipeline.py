from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde import EvidenceDraft, QInsightField, StaticEvidenceCollector, VentureDiscoveryEngine
from claire_vde.evidence import AdmissionGate
from claire_vde.fare import FAREProjector, VentureProjection
from claire_vde.sentinel import VDESentinel


def make_store(root: Path) -> AREStore:
    return AREStore(AREConfig(root=root, hmac_key=b"vde-test-key", max_segment_records=2))


def draft(plane: str, value: float, source: str) -> EvidenceDraft:
    return EvidenceDraft(
        title=f"{plane} signal",
        text=f"Public evidence indicates {plane} signal from {source}.",
        source=source,
        collector="test_collector",
        plane=plane,
        value=value,
        precision=2.0,
        confidence=0.8,
        provenance_url=f"https://example.test/{plane}/{source}",
        entity_refs=["example_entity"],
    )


def test_q_insight_does_not_orient_without_are_evidence():
    field = QInsightField()

    state = field.read("technology_maturity")

    assert state["bearing_state"] == "not_oriented"
    assert state["bearing"] is None
    assert state["evidence_count"] == 0


def test_unregistered_plane_is_rejected_after_are_admission():
    with tempfile.TemporaryDirectory() as td:
        store = make_store(Path(td))
        evidence = AdmissionGate(store).admit(draft("unregistered_plane", 0.5, "sec_edgar"))
        field = QInsightField()

        with pytest.raises(KeyError):
            field.admit(evidence)

        store.stop()


def test_admission_gate_commits_evidence_to_are_before_orientation():
    with tempfile.TemporaryDirectory() as td:
        store = make_store(Path(td))
        evidence = AdmissionGate(store).admit(draft("technology_maturity", 0.6, "patent_record"))
        field = QInsightField()

        field.admit(evidence)
        state = field.read("technology_maturity")

        assert evidence.are_hash
        assert state["bearing_state"] in {"low_confidence", "oriented"}
        assert state["are_hashes"] == [evidence.are_hash]
        assert store.verify()["valid"]
        store.stop()


def test_fare_and_sentinel_block_unsupported_projection():
    projection = VentureProjection(
        title="unsupported",
        path="unsupported claim",
        confidence=0.5,
        uncertainty=[],
        failure_conditions=[],
        analogs=[],
        are_hashes=[],
    )

    decision = VDESentinel().validate_projection(projection)

    assert not decision.allowed
    assert "missing_are_evidence" in decision.rules_triggered
    assert "missing_historical_analog" in decision.rules_triggered


def test_pipeline_generates_evidence_backed_projection_and_audit():
    with tempfile.TemporaryDirectory() as td:
        store = make_store(Path(td))
        engine = VentureDiscoveryEngine(store)
        collector = StaticEvidenceCollector(
            "test_collector",
            [
                draft("technology_maturity", 0.65, "patent_record"),
                draft("demand_pressure", 0.55, "job_postings"),
                draft("capital_movement", 0.4, "funding_announcements"),
            ],
        )

        result = engine.run([collector])

        assert result["collector_runs"][0]["admitted"]
        assert result["orientation"]["technology_maturity"]["are_hashes"]
        assert result["analogs"]
        assert result["projections"]
        for projection in result["projections"]:
            assert projection["are_hashes"]
            assert projection["analogs"]
            assert projection["sentinel"]["allowed"]
        event_types = [(row.get("payload") or {}).get("event_type") for row in store.audit_recent(limit=20)]
        assert "vde_collector_run" in event_types
        assert "vde_run" in event_types
        store.stop()


def test_fare_returns_no_projection_without_orientation_or_analogs():
    assert FAREProjector().project({}, []) == []
