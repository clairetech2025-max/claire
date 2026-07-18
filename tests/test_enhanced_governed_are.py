import json
import tempfile
import unittest
from pathlib import Path

from enhanced_governed_are import ARERecord, EnhancedGovernedAREStore, ParserManifest, copy_store_without_line, sha256_file


class EnhancedGovernedARETests(unittest.TestCase):
    def make_store(self, root: Path, *, max_segment_records: int = 1000) -> EnhancedGovernedAREStore:
        return EnhancedGovernedAREStore(root, hmac_key=b"test-key", max_segment_records=max_segment_records)

    def test_flush_and_shutdown_wait_for_disk_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            result = store.append(ARERecord(text="first legal event"))
            store.flush()
            self.assertTrue((root / "manifest.json").exists())
            self.assertTrue(Path(result["memory_file"]).exists())
            self.assertEqual(store.last_n(1)[0]["text"], "first legal event")
            store.stop()

    def test_tampering_payload_breaks_verify_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            store.append(ARERecord(text="original payload"))
            store.stop()
            segment = next((root / "segments").glob("*.jsonl"))
            row = json.loads(segment.read_text(encoding="utf-8").splitlines()[0])
            row["payload"]["text"] = "tampered payload"
            segment.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

            verifier = self.make_store(root)
            self.assertFalse(verifier.verify_chain()["valid"])
            verifier.stop()

    def test_tampering_previous_hash_breaks_verify_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            store.append(ARERecord(text="one"))
            store.append(ARERecord(text="two"))
            store.stop()
            segment = next((root / "segments").glob("*.jsonl"))
            rows = [json.loads(line) for line in segment.read_text(encoding="utf-8").splitlines()]
            rows[1]["previous_hash"] = "bad"
            segment.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

            verifier = self.make_store(root)
            self.assertEqual(verifier.verify_chain()["reason"], "previous_hash_mismatch")
            verifier.stop()

    def test_deleting_or_reordering_segment_lines_breaks_verify_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            for item in ["one", "two", "three"]:
                store.append(ARERecord(text=item))
            store.stop()

            deleted_root = root.parent / (root.name + "_deleted")
            copy_store_without_line(root, deleted_root, skip_line_index=1)
            deleted = self.make_store(deleted_root)
            self.assertFalse(deleted.verify_chain()["valid"])
            deleted.stop()

            segment = next((root / "segments").glob("*.jsonl"))
            rows = segment.read_text(encoding="utf-8").splitlines()
            rows[0], rows[1] = rows[1], rows[0]
            segment.write_text("\n".join(rows) + "\n", encoding="utf-8")
            reordered = self.make_store(root)
            self.assertFalse(reordered.verify_chain()["valid"])
            reordered.stop()

    def test_chain_valid_across_segment_rotation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root, max_segment_records=2)
            for item in ["one", "two", "three", "four", "five"]:
                store.append(ARERecord(text=item))
            store.stop()
            verifier = self.make_store(root, max_segment_records=2)
            self.assertGreater(len(list((root / "segments").glob("*.jsonl"))), 1)
            self.assertTrue(verifier.verify_chain()["valid"])
            verifier.stop()

    def test_rejected_write_is_audited_chained_and_excluded_from_recall_and_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            accepted = store.append(ARERecord(text="ordinary legal event"))
            rejected = store.append(ARERecord(text="password=secret should be rejected"))
            store.stop()

            verifier = self.make_store(root)
            self.assertTrue(verifier.verify_chain()["valid"])
            envelopes = verifier.envelopes()
            self.assertEqual(len(envelopes), 2)
            self.assertFalse(envelopes[1]["decision"]["allowed"])
            self.assertEqual(rejected["truth_hash"], envelopes[1]["truth_hash"])
            self.assertEqual([row["sha"] for row in verifier.last_n(5)], [accepted["record"]["sha"]])
            index = verifier.rebuild_index()
            self.assertEqual([row["truth_hash"] for row in index.records], [accepted["truth_hash"]])
            self.assertEqual(index.search("secret"), [])
            verifier.stop()

    def test_manifest_restart_continues_previous_hash_and_segment_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root, max_segment_records=2)
            first = store.append(ARERecord(text="first"))
            second = store.append(ARERecord(text="second"))
            store.stop()

            restarted = self.make_store(root, max_segment_records=2)
            self.assertEqual(restarted.manifest["previous_hash"], second["truth_hash"])
            self.assertEqual(restarted.manifest["current_segment_records"], 2)
            third = restarted.append(ARERecord(text="third"))
            restarted.stop()

            verifier = self.make_store(root, max_segment_records=2)
            self.assertTrue(verifier.verify_chain()["valid"])
            self.assertEqual(verifier.envelopes()[-1]["previous_hash"], second["truth_hash"])
            self.assertEqual(verifier.envelopes()[-1]["truth_hash"], third["truth_hash"])
            verifier.stop()

    def test_legal_metadata_and_original_are_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            result = store.append(
                ARERecord(
                    text="On 2026-02-03 Maria Lopez sent notice.",
                    metadata={
                        "matter_id": "matter_a",
                        "source_doc_id": "src_123",
                        "source_hash": "a" * 64,
                        "page_number": 2,
                        "timecode": None,
                        "chunk_id": "chunk-1",
                        "entity_tags": ["Maria Lopez"],
                        "review_status": "unreviewed",
                        "authority_level": "attorney_review_required",
                        "provenance_status": "source_linked",
                        "fact_type": "source_fact",
                        "generated_by": "test",
                    },
                )
            )
            store.stop()
            self.assertEqual(set(result["record"].keys()), {"ts", "sha", "text"})
            self.assertEqual(len(result["record"]["sha"]), 10)

            verifier = self.make_store(root)
            envelope = verifier.envelopes()[0]
            metadata = envelope["payload"]["metadata"]
            self.assertEqual(metadata["matter_id"], "matter_a")
            self.assertEqual(metadata["source_doc_id"], "src_123")
            self.assertEqual(metadata["source_hash"], "a" * 64)
            self.assertEqual(envelope["compat"], result["record"])
            verifier.stop()

    def test_parser_manifest_helper_and_index_is_downstream_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            source.write_text("legal source text", encoding="utf-8")
            manifest = ParserManifest.from_path(source, matter_id="matter_a")
            self.assertEqual(manifest.source_sha256, sha256_file(source))
            self.assertTrue(manifest.source_doc_id.startswith("src_"))

            store = self.make_store(root / "are")
            result = store.append(ARERecord(text="legal source text", metadata=manifest.__dict__))
            store.stop()
            verifier = self.make_store(root / "are")
            verifier.rebuild_index()
            self.assertEqual(verifier.index.records[0]["truth_hash"], result["truth_hash"])
            self.assertTrue(verifier.verify_chain()["valid"])
            verifier.stop()


if __name__ == "__main__":
    unittest.main()
