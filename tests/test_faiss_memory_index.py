from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from are_memory_store import AREMemoryStore, MemoryEvent
from faiss_memory_index import FaissMemoryIndex, faiss_dependency_status
from governed_are import GovernedARE
from original_are_bridge import append_original_are_memory, read_original_are_history


class FaissMemoryIndexTests(unittest.TestCase):
    def test_chronological_are_records_remain_source_of_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "are_mem.jsonl"
            first = append_original_are_memory("first horse stewardship note", memory_path)
            second = append_original_are_memory("second NVIDIA runtime note", memory_path)

            history = read_original_are_history(limit=10, memory_path=memory_path)
            self.assertEqual([row["sha"] for row in history["records"]], [first["record"]["sha"], second["record"]["sha"]])

            governed = GovernedARE(original_memory_path=memory_path)
            result = governed.recall(query="NVIDIA runtime", allowed_scopes=["PUBLIC"])
            self.assertEqual(result["source_of_truth"]["chronology"], "original_are_jsonl")
            self.assertEqual([row["sha"] for row in result["chronology"]], [first["record"]["sha"], second["record"]["sha"]])

    def test_faiss_returns_relevant_record_ids_not_final_answers(self) -> None:
        index = FaissMemoryIndex()
        index.build([
            {"memory_id": "horse_1", "summary": "horse hoof mold impression farrier", "lane": "HORSE_STEWARDSHIP", "memory_scope": "PUBLIC"},
            {"memory_id": "trade_1", "summary": "Kraken BTC market observation", "lane": "TRADING_STATION", "memory_scope": "PUBLIC"},
        ])

        hits = index.search("hoof impression kit", top_k=1)
        self.assertEqual(hits[0]["memory_id"], "horse_1")
        self.assertIn("memory_lead", hits[0])
        self.assertNotIn("answer", hits[0])

    def test_lane_and_scope_filtering_happens_before_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AREMemoryStore(Path(tmp) / "memory.db")
            store.append_memory_event(MemoryEvent(
                user_id="steve",
                session_id="s",
                lane="LEGAL_CASE",
                summary="CourtListener docket evidence context",
                raw_excerpt="CourtListener docket evidence context",
                memory_scope="LEGAL_SENSITIVE",
            ))
            store.append_memory_event(MemoryEvent(
                user_id="steve",
                session_id="s",
                lane="TRADING_STATION",
                summary="Kraken BTC paper observation",
                raw_excerpt="Kraken BTC paper observation",
                memory_scope="TRADING_SENSITIVE",
            ))

            governed = GovernedARE(memory_store=store)
            result = governed.recall(
                query="CourtListener docket",
                user_id="steve",
                lane="LEGAL_CASE",
                allowed_lanes=["LEGAL_CASE"],
                allowed_scopes=["LEGAL_SENSITIVE"],
                include_original_are=False,
            )
            self.assertEqual([lead["memory_id"] for lead in result["memory_leads"]], [result["memory_leads"][0]["memory_id"]])
            self.assertTrue(all(lead["lane"] == "LEGAL_CASE" for lead in result["memory_leads"]))
            self.assertTrue(any(row["reason"] == "lane_not_allowed" for row in result["rejected"]) or all(row["lane"] == "LEGAL_CASE" for row in result["chronology"]))

    def test_secret_like_strings_are_redacted_or_excluded_before_indexing(self) -> None:
        index = FaissMemoryIndex()
        index.build([
            {
                "memory_id": "secret_1",
                "summary": "Kraken api key is ABCDEFGH123456",
                "raw_excerpt": "execution passphrase is BATTLEBORN_LT",
                "lane": "TRADING_STATION",
                "memory_scope": "PUBLIC",
            }
        ])
        hits = index.search("Kraken api key", top_k=1, min_score=-1.0)
        encoded = json.dumps(hits, ensure_ascii=False)
        self.assertNotIn("ABCDEFGH123456", encoded)
        self.assertNotIn("BATTLEBORN_LT", encoded)
        self.assertIn("[REDACTED_BY_DIODE]", encoded)

    def test_missing_faiss_dependency_falls_back_safely(self) -> None:
        status = faiss_dependency_status()
        index = FaissMemoryIndex()
        build = index.build([
            {"memory_id": "m1", "summary": "analog recall engine glasses", "lane": "CLAIRE_SYSTEM_ARCHITECTURE", "memory_scope": "PUBLIC"}
        ])
        hits = index.search("ARE glasses", top_k=1)
        self.assertEqual(hits[0]["memory_id"], "m1")
        if not status["available"]:
            self.assertFalse(build["faiss_available"])
            self.assertEqual(hits[0]["retrieval_source"], "deterministic_memory_index")

    def test_no_raw_memory_dump_appears_in_user_facing_shape(self) -> None:
        index = FaissMemoryIndex()
        index.build([
            {"memory_id": "long", "summary": "x" * 2000, "lane": "GENERAL_CHAT", "memory_scope": "PUBLIC"}
        ])
        hit = index.search("x", top_k=1, min_score=-1.0)[0]
        self.assertLessEqual(len(hit["memory_lead"]), 500)
        self.assertNotIn("raw_excerpt", hit)

    def test_veritas_legal_context_not_confused_with_trading_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AREMemoryStore(Path(tmp) / "memory.db")
            store.append_memory_event(MemoryEvent(
                user_id="steve",
                session_id="s",
                lane="LEGAL_CASE",
                summary="Veritas Legal CourtListener docket evidence package",
                raw_excerpt="Veritas Legal CourtListener docket evidence package",
                memory_scope="LEGAL_SENSITIVE",
            ))
            store.append_memory_event(MemoryEvent(
                user_id="steve",
                session_id="s",
                lane="TRADING_STATION",
                summary="Veritas Kraken paper trading market state",
                raw_excerpt="Veritas Kraken paper trading market state",
                memory_scope="TRADING_SENSITIVE",
            ))

            governed = GovernedARE(memory_store=store)
            legal = governed.recall(
                query="Veritas Legal docket evidence",
                user_id="steve",
                lane="LEGAL_CASE",
                allowed_lanes=["LEGAL_CASE"],
                allowed_scopes=["LEGAL_SENSITIVE"],
                include_original_are=False,
            )
            trading = governed.recall(
                query="Veritas Kraken market state",
                user_id="steve",
                lane="TRADING_STATION",
                allowed_lanes=["TRADING_STATION"],
                allowed_scopes=["TRADING_SENSITIVE"],
                include_original_are=False,
            )

            self.assertTrue(all(lead["lane"] == "LEGAL_CASE" for lead in legal["memory_leads"]))
            self.assertTrue(all(lead["lane"] == "TRADING_STATION" for lead in trading["memory_leads"]))


if __name__ == "__main__":
    unittest.main()

