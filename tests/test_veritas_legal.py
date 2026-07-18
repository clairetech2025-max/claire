import hashlib
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from veritas_legal import EvidenceEngine, claire_explains_summary
from veritas_legal.courtlistener_client import lookup_case_law
from enhanced_governed_are import EnhancedGovernedAREStore


def load_claire_parser_module():
    parser_path = Path(__file__).resolve().parents[1] / "claire_parser"
    loader = importlib.machinery.SourceFileLoader("claire_parser_under_test", str(parser_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fake_are_append_factory(events):
    def fake_are_append(text: str):
        event = json.loads(text)
        events.append(event)
        sha = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:10]
        return {"record": {"ts": 123, "sha": sha, "text": text}}

    return fake_are_append


class VeritasLegalTests(unittest.TestCase):
    def test_ingest_hash_entities_dates_and_claire_explains(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "note.txt"
            src.write_text("On 2024-05-01 Steven Roth met Claire Systems about evidence.", encoding="utf-8")
            events = []
            engine = EvidenceEngine(root / "state", matter_id="matter alpha", are_append=fake_are_append_factory(events))
            record = engine.ingest_file(src)

            self.assertEqual(record.matter_id, "matter_alpha")
            self.assertTrue(record.source_doc_id.startswith("src_"))
            self.assertEqual(record.source_hash, record.source_sha256)
            self.assertEqual(len(record.source_sha256), 64)
            self.assertTrue(record.are_event_sha)
            self.assertIn("2024-05-01", record.dates)
            self.assertTrue(any("Steven Roth" in entity for entity in record.entities))
            self.assertEqual(events[0]["event_type"], "legal_source_ingested")
            self.assertEqual(events[0]["matter_id"], "matter_alpha")
            self.assertEqual(events[0]["source_doc_id"], record.source_doc_id)
            self.assertEqual(events[0]["source_hash"], record.source_hash)

            metadata = read_jsonl(root / "state" / "legal_metadata.jsonl")[0]
            self.assertEqual(metadata["matter_id"], "matter_alpha")
            self.assertEqual(metadata["source_doc_id"], record.source_doc_id)
            self.assertEqual(metadata["source_hash"], record.source_hash)
            self.assertIsNone(metadata["page_number"])
            self.assertIsNone(metadata["timecode"])
            self.assertIn("entity_tags", metadata)
            self.assertEqual(metadata["review_status"], "unreviewed")
            self.assertEqual(metadata["authority_level"], "attorney_review_required")
            self.assertEqual(metadata["are_event_sha"], record.are_event_sha)
            self.assertFalse(metadata["faiss_authority"])
            self.assertFalse(metadata["search_authority"])

            summary = engine.summary()
            self.assertEqual(summary["record_count"], 1)
            self.assertEqual(summary["matter_id"], "matter_alpha")
            self.assertEqual(summary["source_doc_count"], 1)
            self.assertEqual(summary["are_event_count"], 1)
            self.assertFalse(summary["faiss_authority"])
            self.assertEqual(summary["search_authority"], "source_records_and_are_events_only")
            self.assertEqual(summary["timeline"][0]["date"], "2024-05-01")

            explanation = claire_explains_summary(summary)
            self.assertIn("Veritas Legal is an evidence organizer", explanation)
            self.assertIn("not legal advice", explanation)

    def test_redacts_secret_like_text_and_writes_trace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "note.txt"
            src.write_text("API token abc123 appears on 2024-05-01.", encoding="utf-8")
            engine = EvidenceEngine(root / "state", are_append=fake_are_append_factory([]))
            record = engine.ingest_file(src)

            self.assertGreater(record.redactions, 0)
            self.assertIn("[REDACTED_SECRET_MARKER]", record.excerpt)
            self.assertTrue((root / "state" / "source_manifest.jsonl").exists())
            self.assertTrue((root / "state" / "trace.jsonl").exists())

    def test_matter_scope_changes_source_doc_id_without_changing_source_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "same.txt"
            src.write_text("Same evidence source on 2025-01-02.", encoding="utf-8")
            rec_a = EvidenceEngine(root / "state_a", matter_id="Matter A", are_append=fake_are_append_factory([])).ingest_file(src)
            rec_b = EvidenceEngine(root / "state_b", matter_id="Matter B", are_append=fake_are_append_factory([])).ingest_file(src)

            self.assertEqual(rec_a.source_hash, rec_b.source_hash)
            self.assertNotEqual(rec_a.matter_id, rec_b.matter_id)
            self.assertNotEqual(rec_a.source_doc_id, rec_b.source_doc_id)

    def test_parser_record_writes_are_event_and_governed_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_hash = hashlib.sha256(b"source bytes").hexdigest()
            events = []
            engine = EvidenceEngine(root / "state", matter_id="Case 17", are_append=fake_are_append_factory(events))
            record = engine.ingest_parser_record(
                {
                    "chunk_id": "chunk-001",
                    "source_path": "/case/evidence/report.pdf",
                    "file_sha256": source_hash,
                    "text": "On 2026-03-04 Jane Smith reported the incident.",
                    "extraction_method": "pdf",
                    "page_number": 3,
                    "media_seconds": None,
                }
            )

            self.assertEqual(record.matter_id, "Case_17")
            self.assertEqual(record.source_hash, source_hash)
            self.assertTrue(record.are_event_sha)
            self.assertEqual(events[0]["event_type"], "legal_parser_chunk_ingested")
            self.assertEqual(events[0]["parser_chunk_id"], "chunk-001")
            self.assertEqual(events[0]["page_number"], 3)
            self.assertEqual(events[0]["source_doc_id"], record.source_doc_id)

            metadata = read_jsonl(root / "state" / "legal_metadata.jsonl")[0]
            self.assertEqual(metadata["matter_id"], "Case_17")
            self.assertEqual(metadata["source_doc_id"], record.source_doc_id)
            self.assertEqual(metadata["source_hash"], source_hash)
            self.assertEqual(metadata["parser_chunk_id"], "chunk-001")
            self.assertEqual(metadata["page_number"], 3)
            self.assertIsNone(metadata["timecode"])
            self.assertIn("Jane Smith", metadata["entity_tags"])
            self.assertEqual(metadata["are_event_sha"], record.are_event_sha)
            self.assertFalse(metadata["faiss_authority"])
            self.assertFalse(metadata["search_authority"])

            trace = read_jsonl(root / "state" / "trace.jsonl")[0]
            self.assertEqual(trace["event"], "ingest_parser_record")
            self.assertEqual(trace["are_event_sha"], record.are_event_sha)

    def test_claire_parser_rejects_zip_slip_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zip_path = root / "malicious.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../evil.txt", "bad parent traversal")
                zf.writestr("/absolute_evil.txt", "bad absolute path")
                zf.writestr("C:/drive_evil.txt", "bad windows drive path")
                zf.writestr("safe/good.txt", "safe evidence on 2026-01-01")

            claire_parser = load_claire_parser_module()
            output_jsonl = root / "parser_output.jsonl"
            parser = claire_parser.ClaireParser(
                output_jsonl=output_jsonl,
                temp_root=root / "tmp",
                enable_ocr=False,
                enable_media=False,
            )
            count = parser.parse_zip(zip_path)

            self.assertEqual(count, 1)
            self.assertFalse((root / "evil.txt").exists())
            self.assertFalse((root / "tmp" / "absolute_evil.txt").exists())
            parsed = output_jsonl.read_text(encoding="utf-8")
            self.assertIn("safe evidence", parsed)
            self.assertNotIn("bad parent traversal", parsed)
            self.assertNotIn("bad absolute path", parsed)
            self.assertNotIn("bad windows drive path", parsed)

    def test_case_file_parser_output_becomes_are_linked_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zip_path = root / "case_file.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("case/note.txt", "On 2026-02-03 Maria Lopez sent notice to Claire Systems.")

            claire_parser = load_claire_parser_module()
            parser_output = root / "parser_output.jsonl"
            parser = claire_parser.ClaireParser(
                output_jsonl=parser_output,
                temp_root=root / "tmp",
                enable_ocr=False,
                enable_media=False,
            )
            self.assertEqual(parser.parse_zip(zip_path), 1)

            events = []
            engine = EvidenceEngine(root / "state", matter_id="Case File A", are_append=fake_are_append_factory(events))
            records = engine.ingest_parser_jsonl(parser_output)

            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record.matter_id, "Case_File_A")
            self.assertTrue(record.source_doc_id.startswith("src_"))
            self.assertEqual(len(record.source_hash), 64)
            self.assertTrue(record.are_event_sha)
            self.assertEqual(events[0]["event_type"], "legal_parser_chunk_ingested")
            self.assertEqual(events[0]["source_doc_id"], record.source_doc_id)
            self.assertEqual(events[0]["source_hash"], record.source_hash)

            metadata = read_jsonl(root / "state" / "legal_metadata.jsonl")[0]
            self.assertEqual(metadata["matter_id"], "Case_File_A")
            self.assertEqual(metadata["source_doc_id"], record.source_doc_id)
            self.assertEqual(metadata["source_hash"], record.source_hash)
            self.assertEqual(metadata["are_event_sha"], record.are_event_sha)
            self.assertEqual(metadata["review_status"], "unreviewed")
            self.assertEqual(metadata["authority_level"], "attorney_review_required")
            self.assertFalse(metadata["faiss_authority"])
            self.assertFalse(metadata["search_authority"])

            summary = engine.summary()
            self.assertEqual(summary["record_count"], 1)
            self.assertEqual(summary["source_doc_count"], 1)
            self.assertEqual(summary["are_event_count"], 1)

    def test_default_veritas_append_uses_enhanced_are_spine(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.chdir(root)
            try:
                src = root / "legal.txt"
                src.write_text("On 2026-04-05 Alex Rivera filed a notice.", encoding="utf-8")
                engine = EvidenceEngine(root / "state", matter_id="Default Spine Matter")
                record = engine.ingest_file(src)
                metadata = read_jsonl(root / "state" / "legal_metadata.jsonl")[0]

                self.assertTrue(record.are_event_sha)
                self.assertTrue(metadata["truth_hash"])
                spine_root = root / "data" / "veritas_legal_are"
                verifier = EnhancedGovernedAREStore(spine_root)
                self.assertTrue(verifier.verify_chain()["valid"])
                envelope = verifier.envelopes()[0]
                self.assertEqual(envelope["compat"]["sha"], record.are_event_sha)
                self.assertEqual(envelope["truth_hash"], metadata["truth_hash"])
                self.assertEqual(envelope["payload"]["metadata"]["matter_id"], "Default_Spine_Matter")
                self.assertEqual(envelope["payload"]["metadata"]["source_doc_id"], record.source_doc_id)
                verifier.stop()
            finally:
                os.chdir(old_cwd)

    def test_legacy_veritas_parser_wrapper_uses_hardened_parser_and_legal_are_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zip_path = root / "legacy_case.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../escape.txt", "bad escape")
                zf.writestr("case/note.txt", "On 2026-05-06 Taylor Green sent notice to Claire Systems.")

            loader = importlib.machinery.SourceFileLoader(
                "veritas_parser_wrapper_under_test",
                str(Path(__file__).resolve().parents[1] / "Veritas_parser.py"),
            )
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            sys.modules[loader.name] = module
            loader.exec_module(module)

            old_cwd = os.getcwd()
            os.chdir(root)
            try:
                summary = module.ingest(
                    zip_path,
                    matter_id="Legacy Matter",
                    state_root=root / "wrapper_state",
                    enable_ocr=False,
                    enable_media=False,
                )
            finally:
                os.chdir(old_cwd)

            self.assertTrue(summary["parser_first"])
            self.assertEqual(summary["matter_id"], "Legacy_Matter")
            self.assertEqual(summary["parsed_units"], 1)
            self.assertEqual(summary["legal_records_created"], 1)
            self.assertEqual(summary["record_count"], 1)
            self.assertEqual(summary["source_doc_count"], 1)
            self.assertEqual(summary["are_event_count"], 1)
            self.assertFalse((root / "escape.txt").exists())

            parser_output = Path(summary["parser_output"])
            self.assertTrue(parser_output.exists())
            self.assertIn("Taylor Green", parser_output.read_text(encoding="utf-8"))

            metadata = read_jsonl(Path(summary["legal_metadata_path"]))[0]
            self.assertEqual(metadata["matter_id"], "Legacy_Matter")
            self.assertTrue(metadata["source_doc_id"].startswith("src_"))
            self.assertEqual(len(metadata["source_hash"]), 64)
            self.assertTrue(metadata["are_event_sha"])
            self.assertFalse(metadata["faiss_authority"])
            self.assertFalse(metadata["search_authority"])

    def test_detect_contradictions_flags_conflicting_date_claims_with_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "notice_a.txt"
            second = root / "notice_b.txt"
            first.write_text("On 2024-05-01 Jane Smith signed the settlement agreement.", encoding="utf-8")
            second.write_text("On 2024-06-01 Jane Smith signed the settlement agreement.", encoding="utf-8")
            engine = EvidenceEngine(root / "state", matter_id="Conflict Matter", are_append=fake_are_append_factory([]))
            rec_a = engine.ingest_file(first)
            rec_b = engine.ingest_file(second)

            contradictions = engine.detect_contradictions("Conflict Matter")

            self.assertEqual(len(contradictions), 1)
            item = contradictions[0]
            self.assertEqual(item.contradiction_type, "conflicting_dates")
            self.assertEqual({item.source_doc_id_a, item.source_doc_id_b}, {rec_a.source_doc_id, rec_b.source_doc_id})
            self.assertEqual({item.source_hash_a, item.source_hash_b}, {rec_a.source_hash, rec_b.source_hash})
            self.assertIn("2024-05-01", item.excerpt_a + item.excerpt_b)
            self.assertIn("2024-06-01", item.excerpt_a + item.excerpt_b)

    def test_generate_review_packet_markdown_contains_index_timeline_and_contradictions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "notice_a.txt"
            second = root / "notice_b.txt"
            first.write_text("On 2024-05-01 Jane Smith signed the settlement agreement.", encoding="utf-8")
            second.write_text("On 2024-06-01 Jane Smith signed the settlement agreement.", encoding="utf-8")
            engine = EvidenceEngine(root / "state", matter_id="Packet Matter", are_append=fake_are_append_factory([]))
            rec_a = engine.ingest_file(first)
            rec_b = engine.ingest_file(second)

            with patch("veritas_legal.courtlistener_client.lookup_case_law") as mocked_lookup:
                from veritas_legal.courtlistener_client import CaseLawResult

                mocked_lookup.return_value = CaseLawResult(
                    status="UNAVAILABLE",
                    query="Packet Matter",
                    matter_id="Packet_Matter",
                    cases=[],
                    reason="mock unavailable",
                )
                packet_path = engine.generate_review_packet("Packet Matter", "markdown")

            self.assertTrue(packet_path.exists())
            body = packet_path.read_text(encoding="utf-8")
            self.assertIn("## Exhibit Index", body)
            self.assertIn(rec_a.source_hash, body)
            self.assertIn(rec_b.source_hash, body)
            self.assertIn("## Timeline", body)
            self.assertIn("## Contradictions", body)
            self.assertIn("Case-law verification unavailable: mock unavailable.", body)

    def test_courtlistener_failure_returns_unavailable_without_memory_substitute(self):
        class FailingSession:
            @staticmethod
            def get(*args, **kwargs):
                raise TimeoutError("network timeout")

        result = lookup_case_law("Paisley Park Boxill", "Court Matter", session=FailingSession())

        self.assertEqual(result.status, "UNAVAILABLE")
        self.assertEqual(result.cases, [])
        self.assertIn("network timeout", result.reason)



if __name__ == "__main__":
    unittest.main()
