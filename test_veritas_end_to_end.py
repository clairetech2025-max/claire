import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from veritas_legal import EvidenceEngine


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_veritas_evidence_workflow_preserves_source_provenance_and_are_reference():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        evidence = root / "incident_note.txt"
        evidence.write_text(
            "On 2026-05-14 Maria Lopez reported the hallway incident to Claire Systems. "
            "This is evidence text, not a legal conclusion.",
            encoding="utf-8",
        )
        source_hash = hashlib.sha256(evidence.read_bytes()).hexdigest()
        are_payloads = []

        def append_are(payload: str):
            are_payloads.append(json.loads(payload))
            return {"record": {"ts": 123, "sha": hashlib.sha256(payload.encode()).hexdigest()[:10], "text": payload}}

        engine = EvidenceEngine(root / "state", matter_id="Matter E2E", are_append=append_are)
        record = engine.ingest_file(evidence)

        assert record.matter_id == "Matter_E2E"
        assert record.source_hash == source_hash
        assert record.source_sha256 == source_hash
        assert record.source_doc_id.startswith("src_")
        assert record.are_event_sha
        assert "2026-05-14" in record.dates
        assert are_payloads[0]["event_type"] == "legal_source_ingested"
        assert are_payloads[0]["source_hash"] == source_hash

        metadata = read_jsonl(root / "state" / "legal_metadata.jsonl")[0]
        assert metadata["matter_id"] == "Matter_E2E"
        assert metadata["source_doc_id"] == record.source_doc_id
        assert metadata["source_hash"] == source_hash
        assert metadata["are_event_sha"] == record.are_event_sha
        assert metadata["review_status"] == "unreviewed"
        assert metadata["authority_level"] == "attorney_review_required"
        assert metadata["provenance_status"] == "source_linked"
        assert metadata["faiss_authority"] is False
        assert metadata["search_authority"] is False

        timeline = engine.build_timeline()
        assert timeline
        assert timeline[0]["source_doc_id"] == record.source_doc_id
        assert timeline[0]["are_event_sha"] == record.are_event_sha

        with patch("veritas_legal.courtlistener_client.lookup_case_law") as lookup:
            lookup.return_value.status = "UNAVAILABLE"
            lookup.return_value.reason = "mocked unavailable"
            lookup.return_value.cases = []
            packet = engine.generate_review_packet(output_format="markdown")
        packet_text = packet.read_text(encoding="utf-8")
        assert record.source_doc_id in packet_text
        assert source_hash in packet_text
        assert "## Contradictions" in packet_text
        assert "not legal advice" in packet_text.lower()
