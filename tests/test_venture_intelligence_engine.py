from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import claire_vde.api as api_module
from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde import EvidenceDraft, StaticEvidenceCollector, VentureDiscoveryEngine
from claire_vde.collectors import JsonlEvidenceCollector, NotConfiguredCollector
from claire_vde.evidence import AdmissionGate
from claire_vde.ledger import OpportunityHypothesis, OpportunityLedger
from claire_vde.security import VentureSecurity
from claire_vde.storage import VentureRepository


def make_store(root: Path) -> AREStore:
    return AREStore(AREConfig(root=root, hmac_key=b"venture-test-key", max_segment_records=2))


def draft(text: str = "Public patent activity increased for edge AI inference.") -> EvidenceDraft:
    return EvidenceDraft(
        title="edge AI patent signal",
        text=text,
        source="public_patent_snapshot",
        collector="patents",
        plane="technology_maturity",
        value=0.7,
        precision=2.0,
        confidence=0.8,
        provenance_url="https://example.test/patent",
        entity_refs=["edge_ai"],
    )


def test_admission_gate_dedupes_metadata_without_second_truth_spine_write():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        gate = AdmissionGate(store, repository=repo)

        first = gate.admit(draft())
        second = gate.admit(draft())

        assert first.are_hash == second.are_hash
        assert len(repo.list_evidence()) == 1
        memory_events = [
            row for row in store.audit_recent(limit=20)
            if (row.get("payload") or {}).get("event_type") == "memory"
        ]
        assert len(memory_events) == 1
        assert store.verify()["valid"]
        store.stop()


def test_jsonl_collector_supports_incremental_cursor():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.jsonl"
        rows = [
            draft("First signal").__dict__,
            draft("Second signal").__dict__,
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

        first = JsonlEvidenceCollector("patents", path).collect()
        second = JsonlEvidenceCollector("patents", path, cursor=first.next_cursor).collect()

        assert len(first.evidence) == 2
        assert first.next_cursor == "2"
        assert second.evidence == []
        assert second.next_cursor == "2"


def test_not_configured_external_collector_fails_honestly():
    run = NotConfiguredCollector("sec").collect()

    assert run.evidence == []
    assert run.errors == ["collector_not_configured"]


def test_pipeline_persists_collector_state_projection_and_truth_references():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        engine = VentureDiscoveryEngine(store, repository=repo)

        result = engine.run(
            [
                StaticEvidenceCollector(
                    "test_collector",
                    [
                        draft("Technology maturity is rising."),
                        EvidenceDraft(
                            title="demand signal",
                            text="Public hiring and customer pull increased for edge AI inference.",
                            source="public_hiring_snapshot",
                            collector="test_collector",
                            plane="demand_pressure",
                            value=0.65,
                            precision=2.0,
                            confidence=0.8,
                        ),
                    ],
                )
            ]
        )

        assert result["collector_runs"][0]["admitted"]
        assert result["orientation"]["technology_maturity"]["are_hashes"]
        assert result["projections"]
        assert repo.get_collector_cursor("test_collector") == "2"
        events = [
            row for row in store.audit_recent(limit=50)
            if (row.get("payload") or {}).get("event_type") == "vde_projection"
        ]
        assert events
        store.stop()


def test_opportunity_ledger_is_append_only_and_truth_backed():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        ledger = OpportunityLedger(store, repo)

        created = ledger.create_hypothesis(
            OpportunityHypothesis(
                hypothesis="Edge AI compliance tooling may become a funded category.",
                evidence_ids=["truth_a"],
                confidence=0.6,
                probability=0.4,
                assumptions=["Demand evidence remains current"],
                falsification_conditions=["No budgets appear in 90 days"],
            )
        )
        outcome = ledger.append_outcome(
            opportunity_id=created["opportunity_id"],
            outcome="Pilot demand confirmed by public procurement notice.",
            evidence_ids=["truth_b"],
        )

        events = ledger.list_events(created["opportunity_id"])
        assert [event["event_type"] for event in events] == ["hypothesis_created", "outcome_recorded"]
        assert created["truth_hash"]
        assert outcome["truth_hash"]
        assert store.verify()["valid"]
        store.stop()


def test_venture_api_admit_run_orientation_opportunity():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old_store = api_module.store
        old_repo = api_module.repository
        old_security = api_module.security
        test_store = make_store(root / "are")
        test_repo = VentureRepository(root / "venture.sqlite")
        api_module.store = test_store
        api_module.repository = test_repo
        api_module.security = VentureSecurity(
            test_repo,
            read_token="read-token",
            write_token="write-token",
            admin_token="admin-token",
            rate_limit_per_minute=100,
        )
        try:
            client = TestClient(api_module.app)
            health = client.get("/v1/venture/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            payload = draft().__dict__
            admitted = client.post("/v1/venture/evidence/admit", json=payload, headers={"Authorization": "Bearer write-token"})
            assert admitted.status_code == 200
            assert admitted.json()["truth_spine_authority"]

            orientation = client.get("/v1/venture/orientation")
            assert orientation.status_code == 200
            assert orientation.json()["orientation"]["technology_maturity"]["are_hashes"]

            opportunity = client.post(
                "/v1/venture/opportunities",
                json={
                    "hypothesis": "A venture category may form around edge AI compliance.",
                    "evidence_ids": [admitted.json()["truth_spine_authority"]],
                    "confidence": 0.6,
                    "probability": 0.4,
                    "assumptions": ["Public evidence remains valid"],
                    "falsification_conditions": ["No budget evidence appears"],
                    "metadata": {},
                },
                headers={"Authorization": "Bearer write-token"},
            )
            assert opportunity.status_code == 200
            assert opportunity.json()["truth_hash"]
        finally:
            test_store.stop()
            api_module.store = old_store
            api_module.repository = old_repo
            api_module.security = old_security
