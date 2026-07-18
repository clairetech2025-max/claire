import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import claire_are.api as api_module
from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_are.gateway import GovernedGateway


class ClaireAREPluginTests(unittest.TestCase):
    def make_store(self, root: Path) -> AREStore:
        return AREStore(AREConfig(root=root, hmac_key=b"test-key", max_segment_records=2))

    def test_records_can_be_ingested_and_recalled(self):
        with tempfile.TemporaryDirectory() as td:
            store = self.make_store(Path(td))
            ingest = store.ingest(text="ARE is the memory authority.", lane="architecture", source="test")
            recalled = store.recall(query="What is ARE authority?", lane="architecture", limit=5)
            self.assertTrue(ingest["accepted"])
            self.assertEqual(recalled["memories"][0]["text"], "ARE is the memory authority.")
            self.assertTrue(recalled["recall_event_sha"])
            store.stop()

    def test_corrupted_memory_records_fail_verification(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            store.ingest(text="Original payload", lane="general", source="test")
            store.stop()
            segment = next((root / "segments").glob("*.jsonl"))
            row = json.loads(segment.read_text(encoding="utf-8").splitlines()[0])
            row["payload"]["text"] = "Tampered payload"
            segment.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
            verifier = self.make_store(root)
            self.assertFalse(verifier.verify()["valid"])
            verifier.stop()

    def test_llm_completion_requires_recall_first(self):
        with tempfile.TemporaryDirectory() as td:
            store = self.make_store(Path(td))
            store.ingest(text="ARE records experience before reasoning.", lane="architecture", source="test")
            gateway = GovernedGateway(store)
            result = gateway.complete(prompt="Explain ARE.", lane="architecture", model="local/stub")
            self.assertTrue(result["recall_event_sha"])
            self.assertTrue(result["completion_event_sha"])
            audit_types = [(e.get("payload") or {}).get("event_type") for e in store.audit_recent(limit=5)]
            self.assertLess(audit_types.index("recall"), audit_types.index("llm_complete"))
            store.stop()

    def test_legal_lane_cannot_read_architecture_lane(self):
        with tempfile.TemporaryDirectory() as td:
            store = self.make_store(Path(td))
            store.ingest(text="Architecture-only memory.", lane="architecture", source="test")
            recalled = store.recall(query="Architecture", lane="legal", limit=5)
            self.assertEqual(recalled["memories"], [])
            store.stop()

    def test_archive_not_delete_segment_rotation_preserves_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = self.make_store(root)
            for idx in range(5):
                store.ingest(text=f"memory {idx}", lane="general", source="test")
            self.assertGreater(len(list((root / "segments").glob("*.jsonl"))), 1)
            self.assertTrue(store.verify()["valid"])
            store.stop()

    def test_public_api_ingest_recall_complete_verify_and_audit(self):
        with tempfile.TemporaryDirectory() as td:
            old_store = api_module.store
            old_gateway = api_module.gateway
            test_store = self.make_store(Path(td))
            api_module.store = test_store
            api_module.gateway = GovernedGateway(test_store)
            try:
                client = TestClient(api_module.app)
                ingest = client.post(
                    "/v1/memory/ingest",
                    json={
                        "text": "ARE is governed memory.",
                        "lane": "architecture",
                        "source": "api_test",
                        "metadata": {"case": "plugin"},
                    },
                )
                self.assertEqual(ingest.status_code, 200)
                self.assertTrue(ingest.json()["accepted"])

                recall = client.post(
                    "/v1/memory/recall",
                    json={"query": "governed memory", "lane": "architecture", "limit": 8},
                )
                self.assertEqual(recall.status_code, 200)
                self.assertEqual(recall.json()["memories"][0]["text"], "ARE is governed memory.")

                complete = client.post(
                    "/v1/llm/complete",
                    json={"prompt": "Explain ARE.", "lane": "architecture", "model": "local/stub", "metadata": {}},
                )
                self.assertEqual(complete.status_code, 200)
                self.assertTrue(complete.json()["recall_event_sha"])
                self.assertTrue(complete.json()["completion_event_sha"])

                verify = client.get("/v1/memory/verify")
                self.assertEqual(verify.status_code, 200)
                self.assertTrue(verify.json()["valid"])

                audit = client.get("/v1/audit/recent")
                self.assertEqual(audit.status_code, 200)
                event_types = [(row.get("payload") or {}).get("event_type") for row in audit.json()["events"]]
                self.assertIn("recall", event_types)
                self.assertIn("llm_complete", event_types)
            finally:
                test_store.stop()
                api_module.store = old_store
                api_module.gateway = old_gateway



if __name__ == "__main__":
    unittest.main()
