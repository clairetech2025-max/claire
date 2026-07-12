from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde.evidence import AdmissionGate, EvidenceDraft
from claire_vde.ledger import OpportunityHypothesis, OpportunityLedger
from claire_vde.reconciliation import reconcile_orphaned_evidence
from claire_vde.storage import VentureRepository


def make_store(root: Path) -> AREStore:
    return AREStore(AREConfig(root=root, hmac_key=b"venture-integrity-key", max_segment_records=2))


def make_draft(*, text: str, source: str = "public_patent_snapshot") -> EvidenceDraft:
    return EvidenceDraft(
        title="edge ai compliance signal",
        text=text,
        source=source,
        collector="patents",
        plane="technology_maturity",
        value=0.7,
        precision=2.0,
        confidence=0.8,
        provenance_url="https://example.test/patent",
        entity_refs=["edge_ai"],
    )


def count_vde_memory_events(store: AREStore) -> int:
    return sum(
        1
        for row in store.audit_recent(limit=200)
        if (row.get("payload") or {}).get("event_type") == "memory"
        and str((row.get("payload") or {}).get("metadata", {}).get("kind") or "") == "vde_evidence"
    )


def test_orphan_reconciliation_repairs_missing_subordinate_row_and_keeps_single_are_event():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        gate = AdmissionGate(store, repository=repo)
        draft = make_draft(text="Public patent activity increased for edge AI inference.")

        calls = {"count": 0}
        original_insert = repo.insert_evidence

        def fail_once(evidence):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("simulated subordinate insert failure")
            return original_insert(evidence)

        repo.insert_evidence = fail_once  # type: ignore[method-assign]

        with pytest.raises(RuntimeError):
            gate.admit(draft)

        assert repo.list_evidence() == []
        assert count_vde_memory_events(store) == 1
        assert store.verify()["valid"]

        repo.insert_evidence = original_insert  # type: ignore[method-assign]
        repaired = reconcile_orphaned_evidence(store, repo)
        assert repaired["status"] == "ok"
        assert repaired["repaired"] == 1
        assert len(repo.list_evidence()) == 1

        retry = gate.admit(draft)
        assert retry.are_hash
        assert len(repo.list_evidence()) == 1
        assert count_vde_memory_events(store) == 1
        assert store.verify()["valid"]
        store.stop()


def test_retry_after_partial_failure_does_not_create_second_are_commit():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        gate = AdmissionGate(store, repository=repo)
        draft = make_draft(text="Another patent signal for edge AI compliance.")

        calls = {"count": 0}
        original_insert = repo.insert_evidence

        def fail_once(evidence):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("simulated subordinate insert failure")
            return original_insert(evidence)

        repo.insert_evidence = fail_once  # type: ignore[method-assign]

        with pytest.raises(RuntimeError):
            gate.admit(draft)

        repo.insert_evidence = original_insert  # type: ignore[method-assign]
        retry = gate.admit(draft)

        assert retry.are_hash
        assert len(repo.list_evidence()) == 1
        assert count_vde_memory_events(store) == 1
        assert store.verify()["valid"]
        store.stop()


def test_venture_opportunity_ledger_chain_verification_detects_direct_tamper():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        ledger = OpportunityLedger(store, repo)

        first = ledger.create_hypothesis(
            OpportunityHypothesis(
                hypothesis="Edge AI compliance tooling may become a funded category.",
                evidence_ids=["truth_a"],
                evidence_content_hashes=["hash_a"],
                confidence=0.6,
                probability=0.4,
                assumptions=["Demand evidence remains current"],
                falsification_conditions=["No budgets appear in 90 days"],
            )
        )
        ledger.append_outcome(
            opportunity_id=first["opportunity_id"],
            outcome="Pilot demand confirmed by public procurement notice.",
            evidence_ids=["truth_b"],
        )

        assert ledger.verify_ledger_chain()["valid"]

        with repo.connect() as conn:
            conn.execute(
                "UPDATE opportunity_events SET payload_json = ? WHERE event_id = ?",
                ('{"tampered": true}', first["event_id"]),
            )

        chain = ledger.verify_ledger_chain()
        assert not chain["valid"]
        assert chain["reason"] in {"event_hash_mismatch", "previous_hash_mismatch"}
        assert chain["event_id"] == first["event_id"]
        store.stop()


def test_opportunity_ledger_replay_guard_blocks_duplicate_hypothesis_creation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        ledger = OpportunityLedger(store, repo)

        hypothesis = OpportunityHypothesis(
            hypothesis="A venture category may form around edge AI compliance.",
            evidence_ids=["truth_a"],
            evidence_content_hashes=["content_hash_1"],
            confidence=0.6,
            probability=0.4,
            assumptions=["Public evidence remains valid"],
            falsification_conditions=["No budget evidence appears"],
        )

        first = ledger.create_hypothesis(hypothesis)
        with pytest.raises(ValueError, match="replayed_evidence"):
            ledger.create_hypothesis(hypothesis)

        events = ledger.list_events(first["opportunity_id"])
        assert len(events) == 1
        assert events[0]["event_type"] == "hypothesis_created"
        assert events[0]["payload"]["evidence_content_hashes"] == ["content_hash_1"]
        store.stop()


def test_concurrent_same_content_hash_admission_persists_once():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        gate = AdmissionGate(store, repository=repo)
        draft = make_draft(text="Concurrent admission should remain single-writer.")

        def submit() -> str:
            return gate.admit(draft).are_hash

        with ThreadPoolExecutor(max_workers=8) as pool:
            hashes = list(pool.map(lambda _: submit(), range(8)))

        assert len(set(hashes)) == 1
        assert len(repo.list_evidence()) == 1
        assert count_vde_memory_events(store) == 1
        assert store.verify()["valid"]
        store.stop()


def test_concurrent_distinct_content_hash_admission_persists_all():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        gate = AdmissionGate(store, repository=repo)
        drafts = [
            make_draft(text=f"Distinct signal {idx}.")
            for idx in range(8)
        ]

        def submit(draft: EvidenceDraft) -> str:
            return gate.admit(draft).are_hash

        with ThreadPoolExecutor(max_workers=8) as pool:
            hashes = list(pool.map(submit, drafts))

        assert len(set(hashes)) == 8
        assert len(repo.list_evidence()) == 8
        assert count_vde_memory_events(store) == 8
        assert store.verify()["valid"]
        store.stop()
