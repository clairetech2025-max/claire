import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_are.gateway import GovernedGateway
from veritas_legal import EvidenceEngine


def test_component_real_work_reads_searches_ingests_recalls_saves_and_reports_failure():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        doc = root / "case_note.txt"
        doc.write_text("On 2026-04-02 Claire Systems received the signed agreement from Riverstone.", encoding="utf-8")

        # Real local document read.
        text = doc.read_text(encoding="utf-8")
        assert "signed agreement" in text

        # Real repository search against the checked-out source tree.
        repo_hits = list(Path(__file__).resolve().parent.rglob("claire_runtime.py"))
        assert repo_hits and repo_hits[0].is_file()

        # Real ARE ingest, recall, and restart from durable local storage.
        are_root = root / "are"
        store = AREStore(AREConfig(root=are_root, hmac_key=b"test-key"))
        ingest = store.ingest(text=text, lane="legal", source=str(doc), metadata={"test": "real_work"})
        recall = store.recall(query="signed agreement Riverstone", lane="legal")
        assert ingest["accepted"] is True
        assert recall["memories"]
        store.stop()

        restarted = AREStore(AREConfig(root=are_root, hmac_key=b"test-key"))
        restarted_recall = restarted.recall(query="Riverstone agreement", lane="legal")
        assert restarted_recall["memories"]

        # Governed completion logs recall before completion; local/stub is not a real external provider.
        gateway = GovernedGateway(restarted)
        completion = gateway.complete(prompt="Summarize the agreement evidence.", lane="legal", model="local/stub")
        assert completion["recall_event_sha"]
        assert completion["completion_event_sha"]
        restarted.stop()

        # Real Veritas evidence workflow and saved artifact.
        events = []

        def fake_are_append(payload: str):
            events.append(payload)
            return {"record": {"ts": 123, "sha": hashlib.sha256(payload.encode()).hexdigest()[:10], "text": payload}}

        engine = EvidenceEngine(root / "veritas_state", matter_id="Matter Real Work", are_append=fake_are_append)
        record = engine.ingest_file(doc)
        assert record.source_doc_id.startswith("src_")
        assert len(record.source_hash) == 64
        assert record.are_event_sha

        with patch("veritas_legal.courtlistener_client.lookup_case_law") as lookup:
            lookup.return_value.status = "UNAVAILABLE"
            lookup.return_value.reason = "mocked unavailable"
            lookup.return_value.cases = []
            packet = engine.generate_review_packet(output_format="markdown")
        assert packet.exists()
        packet_text = packet.read_text(encoding="utf-8")
        assert "## Exhibit Index" in packet_text
        assert record.source_hash in packet_text
        assert "## Timeline" in packet_text

        # Honest failure path for unsupported export format.
        try:
            engine.generate_review_packet(output_format="docx")
            raise AssertionError("unsupported packet format should fail")
        except ValueError as exc:
            assert "output_format" in str(exc)
