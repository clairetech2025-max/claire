from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

import claire_vde.api as api_module
import claire_vde.worker as worker_module
from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde.collectors import CollectorRun, StaticEvidenceCollector
from claire_vde.evidence import AdmissionGate
from claire_vde.federal_register import FederalRegisterCollector, FederalRegisterCollectorConfig
from claire_vde.pipeline import VentureDiscoveryEngine
from claire_vde.q_insight_venture import QInsightField
from claire_vde.storage import VentureRepository


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "federal_register"


class FakeResponse:
    def __init__(self, body: dict, status_code: int = 200, headers: dict[str, str] | None = None):
        self._body = body
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> dict:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: list[object]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        if not self.responses:
            raise AssertionError("No fake response left")
        next_item = self.responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def make_store(root: Path) -> AREStore:
    return AREStore(AREConfig(root=root, hmac_key=b"federal-register-test-key", max_segment_records=2))


def make_repo(root: Path) -> VentureRepository:
    return VentureRepository(root / "venture.sqlite")


def make_collector(*, repo: VentureRepository | None = None, fixture_names: list[str] | None = None, **overrides) -> tuple[FederalRegisterCollector, FakeSession]:
    fixtures = [load_fixture(name) for name in (fixture_names or ["artificial_intelligence_page1.json"])]
    session = FakeSession([FakeResponse(body) for body in fixtures])
    config = FederalRegisterCollectorConfig(**overrides)
    collector = FederalRegisterCollector(repository=repo, config=config, session=session, cursor=repo.get_collector_cursor("federal_register") if repo else None)
    return collector, session


def admit_all(store: AREStore, repo: VentureRepository, evidence: list) -> None:
    gate = AdmissionGate(store, repository=repo)
    for item in evidence:
        gate.admit(item)


def test_successful_official_api_normalization_using_recorded_fixture():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = make_repo(root)
        collector, session = make_collector(repo=repo, fixture_names=["artificial_intelligence_page1.json"], max_pages=1, per_page=2)

        run = collector.collect()

        assert not run.errors
        assert run.metadata["collector"] == "federal_register"
        assert run.metadata["endpoint"] == "https://www.federalregister.gov/api/v1/documents.json"
        assert run.metadata["query"] == "artificial intelligence"
        assert run.evidence
        assert session.calls[0]["headers"]["User-Agent"].startswith("CLAIRE Venture Intelligence Federal Register Collector")
        first = run.evidence[0]
        assert first.title
        assert first.text
        assert first.source == "federal_register"
        assert first.provenance_url.startswith("https://www.federalregister.gov/documents/")
        assert first.metadata["source_record_id"] == "2026-14086"
        assert first.metadata["publication_date"] == "2026-07-13"
        assert first.metadata["document_type"] == "Notice"
        assert first.metadata["agency_names"] == ["Management and Budget Office"]
        assert first.metadata["content_hash"]
        assert first.metadata["parser_version"] == "federal_register_collector_v1"

        admit_all(store, repo, run.evidence)
        engine = VentureDiscoveryEngine(store, repository=repo)
        outcome = engine.run([StaticEvidenceCollector("federal_register", list(run.evidence))])

        assert store.verify()["valid"]
        assert outcome["projections"] == []
        assert repo.list_opportunity_events() == []
        store.stop()


def test_timeout_handling():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(Path(td))
        collector = FederalRegisterCollector(
            repository=repo,
            config=FederalRegisterCollectorConfig(retries=1, backoff_base_s=0.01),
            session=FakeSession([requests.Timeout("timed out"), requests.Timeout("timed out")]),
        )

        run = collector.collect()

        assert run.evidence == []
        assert any(detail["code"] == "timeout" for detail in run.error_details)


def test_retry_behavior(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(Path(td))
        delays: list[float] = []
        monkeypatch.setattr("claire_vde.federal_register.time.sleep", lambda seconds: delays.append(round(float(seconds), 3)))
        collector = FederalRegisterCollector(
            repository=repo,
            config=FederalRegisterCollectorConfig(retries=2, backoff_base_s=0.5, max_pages=1, per_page=2, respectful_delay_s=0),
            session=FakeSession([requests.Timeout("timed out"), requests.Timeout("timed out"), FakeResponse(load_fixture("artificial_intelligence_page1.json"))]),
        )

        run = collector.collect()

        assert run.evidence
        assert delays[:2] == [0.5, 1.0]


def test_malformed_api_response():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(Path(td))
        collector = FederalRegisterCollector(
            repository=repo,
            config=FederalRegisterCollectorConfig(retries=0, max_pages=1),
            session=FakeSession([FakeResponse({"description": "missing results"})]),
        )

        run = collector.collect()

        assert run.evidence == []
        assert any("malformed_response" in error for error in run.errors)


def test_duplicate_stable_source_id():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = make_repo(root)
        collector, _ = make_collector(repo=repo, fixture_names=["artificial_intelligence_page1.json"], max_pages=1)
        first_run = collector.collect()
        admit_all(store, repo, first_run.evidence)

        repeat_collector, _ = make_collector(repo=repo, fixture_names=["artificial_intelligence_page1.json"], max_pages=1)
        second_run = repeat_collector.collect()

        assert second_run.evidence == []
        assert any(item["reason"] == "duplicate_existing" for item in second_run.metadata["duplicates"])
        store.stop()


def test_repeated_content_hash():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(Path(td))
        collector, _ = make_collector(repo=repo, fixture_names=["duplicate_content.json"], max_pages=1)

        run = collector.collect()

        assert len(run.evidence) == 1
        assert len(run.metadata["duplicates"]) == 1
        assert run.metadata["duplicates"][0]["reason"] == "duplicate_within_batch"


def test_cursor_persistence_and_pagination_continuation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = make_repo(root)
        collector, _ = make_collector(repo=repo, fixture_names=["artificial_intelligence_page1.json"], max_pages=1)
        engine = VentureDiscoveryEngine(store, repository=repo)
        first_result = engine.ingest_collector(collector)

        assert first_result["next_cursor"]
        assert repo.get_collector_cursor("federal_register")

        second_collector, _ = make_collector(repo=repo, fixture_names=["artificial_intelligence_page2.json"], max_pages=1)
        second_run = second_collector.collect()

        assert second_run.evidence
        assert second_run.evidence[0].metadata["source_record_id"] == "2026-13928"
        store.stop()


def test_missing_optional_metadata():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(Path(td))
        collector, _ = make_collector(repo=repo, fixture_names=["minimal_metadata.json"], max_pages=1)
        run = collector.collect()

        assert run.evidence
        evidence = run.evidence[0]
        assert evidence.metadata["agency_names"] == []
        assert evidence.metadata["docket_number"] == ""
        assert evidence.metadata["source_url"]


def test_no_direct_q_insight_mutation():
    field = QInsightField()
    before = field.read("regulatory_pressure")
    collector, _ = make_collector(fixture_names=["artificial_intelligence_page1.json"], max_pages=1)

    run = collector.collect()
    after = field.read("regulatory_pressure")

    assert run.evidence
    assert before == after


def test_no_opportunity_ledger_entry_without_legitimate_qualification():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = make_repo(root)
        collector, _ = make_collector(repo=repo, fixture_names=["artificial_intelligence_page1.json"], max_pages=1)
        run = collector.collect()
        engine = VentureDiscoveryEngine(store, repository=repo)
        engine.run([StaticEvidenceCollector("federal_register", list(run.evidence))])

        assert repo.list_opportunity_events() == []
        store.stop()


def test_full_provenance_fields():
    collector, _ = make_collector(fixture_names=["artificial_intelligence_page1.json"], max_pages=1)
    run = collector.collect()
    evidence = run.evidence[0]

    assert evidence.metadata["source_record_id"]
    assert evidence.metadata["publication_date"]
    assert evidence.metadata["retrieved_at"]
    assert evidence.metadata["observed_at"]
    assert evidence.metadata["document_type"]
    assert evidence.metadata["content_hash"]
    assert evidence.metadata["parser_version"]
    assert evidence.metadata["endpoint"]
    assert evidence.metadata["query"]
    assert evidence.metadata["retrieval_cutoff"]
    assert evidence.metadata["search_terms"]


def test_fail_closed_behavior():
    collector = FederalRegisterCollector(
        repository=None,
        config=FederalRegisterCollectorConfig(retries=1, backoff_base_s=0.01, max_pages=1),
        session=FakeSession([FakeResponse({"description": "server error"}, status_code=500), FakeResponse({"description": "server error"}, status_code=500)]),
    )

    run = collector.collect()

    assert run.evidence == []
    assert any(detail["code"] == "http_500" for detail in run.error_details)


def test_worker_integration(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        monkeypatch.setenv("CLAIRE_ARE_ROOT", str(root / "are"))
        monkeypatch.setenv("CLAIRE_VDE_DB_PATH", str(root / "venture.sqlite"))
        monkeypatch.setenv("CLAIRE_VDE_COLLECTOR", "federal_register")
        monkeypatch.setenv("CLAIRE_VDE_FR_QUERY", "artificial intelligence")
        monkeypatch.setenv("CLAIRE_VDE_FR_MAX_PAGES", "1")

        fixture_run = CollectorRun(
            collector="federal_register",
            evidence=[],
            errors=[],
            next_cursor=json.dumps({"query": "artificial intelligence", "cutoff": "2024-01-01", "endpoint": "https://www.federalregister.gov/api/v1/documents.json", "page": 2, "next_page_url": None}, sort_keys=True),
            metadata={"collector": "federal_register", "result_count": 0, "pages_fetched": 1, "pagination_state": {"page": 2}},
            error_details=[],
        )

        monkeypatch.setattr("claire_vde.federal_register.FederalRegisterCollector.collect", lambda self: fixture_run)
        result = worker_module.run_once()

        assert result["collector"] == "federal_register"
        assert result["next_cursor"]


def test_api_readable_collected_result(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old_store = api_module.store
        old_repo = api_module.repository
        test_store = make_store(root / "are")
        test_repo = make_repo(root)
        api_module.store = test_store
        api_module.repository = test_repo
        try:
            sample_run = CollectorRun(
                collector="federal_register",
                evidence=list(make_collector(repo=test_repo, fixture_names=["artificial_intelligence_page1.json"], max_pages=1)[0].collect().evidence),
                errors=[],
                next_cursor=json.dumps({"query": "artificial intelligence", "cutoff": "2024-01-01", "endpoint": "https://www.federalregister.gov/api/v1/documents.json", "page": 2, "next_page_url": None}, sort_keys=True),
                metadata={"collector": "federal_register", "query": "artificial intelligence"},
                error_details=[],
            )
            monkeypatch.setattr("claire_vde.federal_register.FederalRegisterCollector.collect", lambda self: sample_run)
            client = TestClient(api_module.app)
            response = client.post("/v1/venture/federal-register/run", json={"admit": False})

            assert response.status_code == 200
            body = response.json()
            assert body["collector_run"]["collector"] == "federal_register"
            assert body["collector_run"]["evidence"]
            assert body["collector_run"]["metadata"]["query"] == "artificial intelligence"
        finally:
            test_store.stop()
            api_module.store = old_store
            api_module.repository = old_repo


def test_live_smoke_federal_register_collection():
    if os.environ.get("CLAIRE_VDE_FEDERAL_REGISTER_LIVE") != "1":
        pytest.skip("live smoke disabled; set CLAIRE_VDE_FEDERAL_REGISTER_LIVE=1 to enable")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = make_repo(root)
        collector = FederalRegisterCollector(repository=repo, session=requests.Session(), cursor=repo.get_collector_cursor("federal_register"))
        run = collector.collect()
        print(
            json.dumps(
                {
                    "collector": run.collector,
                    "errors": run.errors,
                    "result_count": run.metadata.get("result_count"),
                    "pages_fetched": run.metadata.get("pages_fetched"),
                    "next_cursor": run.next_cursor,
                    "first_evidence": asdict(run.evidence[0]) if run.evidence else None,
                },
                indent=2,
                sort_keys=True,
            )
        )
        assert run.collector == "federal_register"
        store.stop()
