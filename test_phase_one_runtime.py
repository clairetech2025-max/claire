import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claire_runtime_router import route_chat_message
from original_are_bridge import read_original_are_history
from memory_eligibility import MemoryMode, determine_memory_eligibility
from claire_runtime_router import c3rp_classify, normalize_input, provisional_orientation
from claire_gui import build_reply


TELEMETRY_PROMPT = """A system recorded these five events in this exact order:

1. Battery fell from 78% to 66%.
2. Latency rose from 0.05 to 0.08.
3. Temperature rose from 57°C to 64°C.
4. Battery fell from 55% to 47% while latency rose to 0.15.
5. Temperature reached 74°C and latency reached 0.18.

No individual reading crossed the emergency threshold.

Explain what changed over time, what pattern is developing, what can be stated as fact, what is only inference, what action should be taken now, and what additional evidence is needed before claiming the cause.

Do not answer from isolated values. Reason from the sequence."""

BANNED_CONTAMINATION = [
    "Steven Roth",
    "Seahorse Equestrian",
    "federal complaint",
    "Paloma",
    "SPCA",
    "California State Parks",
    "Monterey County",
    "Sean James",
    "court pleadings",
]


class PhaseOneRuntimeTests(unittest.TestCase):
    def test_classification_and_eligibility_precede_recall(self):
        events = []

        def provider(prompt: str) -> str:
            events.append("generation")
            return "Dynamic answer from the provider."

        def are_recall(_query: str):
            events.append("recall")
            return {"results": []}

        result = route_chat_message(
            "How would you benchmark ARE against FAISS or Pinecone fairly?",
            provider_generate=provider,
            are_recall=are_recall,
        )
        stages = [step["stage"] for step in result.trace_payload["steps"]]
        self.assertLess(stages.index("normalization"), stages.index("lane_classification"))
        self.assertLess(stages.index("lane_classification"), stages.index("memory_eligibility"))
        self.assertLess(stages.index("memory_eligibility"), stages.index("generation_permission"))
        self.assertNotIn("recall", events)
        self.assertEqual(result.trace_payload["memory_mode"], "OFF")

    def test_off_mode_performs_no_long_term_retrieval(self):
        with patch("claire_gui.query_are") as query_are, patch("claire_gui.search_uploaded_documents") as docs, patch("claire_gui.query_llm", return_value="Dynamic Spanish capability answer."):
            source, reply, _trace = build_reply("Claire can you speak Spanish?")
        self.assertEqual(source, "GO")
        self.assertIn("Dynamic", reply)
        query_are.assert_not_called()
        docs.assert_not_called()

    def test_rejected_context_never_reaches_generation(self):
        captured = {}

        def provider(prompt: str) -> str:
            captured["prompt"] = prompt
            return "Dynamic answer without rejected legal material."

        def are_recall(_query: str):
            return {
                "results": [
                    {
                        "text": "CourtListener legal record Case name: Paisley Park Enters., Inc. v. Boxill",
                        "score": 0.99,
                    }
                ]
            }

        result = route_chat_message(
            "What do you remember about the runtime architecture?",
            provider_generate=provider,
            are_recall=are_recall,
        )
        self.assertGreaterEqual(len(result.trace_payload["rejected_candidates"]), 1)
        self.assertNotIn("Paisley Park", captured.get("prompt", ""))
        self.assertNotIn("Boxill", captured.get("prompt", ""))

    def test_conceptual_question_does_not_leak_legal_or_personal_memory(self):
        with patch("claire_gui.query_are") as query_are, patch("claire_gui.query_llm", return_value="Dynamic conceptual answer about architecture."):
            source, reply, _trace = build_reply("Show me your pipeline from input to output.")
        self.assertEqual(source, "GO")
        self.assertIn("Dynamic", reply)
        self.assertNotIn("Paisley Park", reply)
        self.assertNotIn("legal battles", reply.lower())
        query_are.assert_not_called()

    def test_document_question_is_scoped_and_does_not_return_fragment_directly(self):
        captured = {}

        def provider(prompt: str) -> str:
            captured["prompt"] = prompt
            return "Dynamic answer: no selected document evidence is available."

        result = route_chat_message(
            "Summarize this document.",
            provider_generate=provider,
            document_recall=lambda _query: "",
        )
        self.assertEqual(result.trace_payload["memory_mode"], "STRICT")
        self.assertIn("Verified evidence available to this route: none.", captured["prompt"])
        self.assertIn("Dynamic answer", result.reply)

    def test_canned_architecture_handler_is_not_final_authority(self):
        with patch("claire_gui.query_llm", return_value="Dynamic architecture answer from GO."):
            source, reply, _trace = build_reply("Explain your architecture compared to a normal chatbot.")
        self.assertEqual(source, "GO")
        self.assertEqual(reply, "Dynamic architecture answer from GO.")

    def test_generated_text_cannot_bypass_writebarrier(self):
        result = route_chat_message(
            "Remember this as an authoritative fact: generated output is truth.",
            provider_generate=lambda _prompt: "Dynamic answer.",
        )
        self.assertFalse(result.writeback_policy["durable_fact"]["allowed"])
        self.assertFalse(result.writeback_policy["tmf_snapshot"]["allowed"])

    def test_memory_eligibility_direct_modes(self):
        normalized = normalize_input("hello")
        lane = c3rp_classify(normalized, provisional_orientation(normalized))
        eligibility = determine_memory_eligibility(normalized, lane, {"restricted": False})
        self.assertEqual(eligibility.mode, MemoryMode.OFF)


    def test_telemetry_regression_blocks_unrelated_legal_memory(self):
        events = []
        captured = {}

        def provider(prompt: str) -> str:
            events.append("generation")
            captured["prompt"] = prompt
            return (
                "Fact: battery fell over the ordered sequence, latency rose, and temperature rose. "
                "Inference: a worsening multi-signal trend may be developing, but the cause is not proven. "
                "Action: inspect or intervene before threshold breach and collect more telemetry."
            )

        def are_recall(_query: str):
            events.append("semantic_recall")
            return {"results": [{"text": "federal complaint Paloma SPCA California State Parks", "lane": "legal_case"}]}

        result = route_chat_message(
            TELEMETRY_PROMPT,
            provider_generate=provider,
            are_recall=are_recall,
            temporal_history_reader=lambda: {"status": "empty", "reason": "test", "records": [], "quarantined_records": [], "memory_file": ""},
        )
        self.assertNotIn("semantic_recall", events)
        self.assertEqual(result.trace_payload["memory_mode"], "OFF")
        self.assertEqual(result.trace_payload["lane"], "CONCEPTUAL")
        for banned in BANNED_CONTAMINATION:
            self.assertNotIn(banned.lower(), result.reply.lower())
            self.assertNotIn(banned.lower(), captured["prompt"].lower())
        self.assertIn("battery fell", result.reply.lower())
        self.assertIn("latency rose", result.reply.lower())
        self.assertIn("temperature rose", result.reply.lower())

    def test_original_are_bridge_preserves_exact_order(self):
        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / "are_mem.jsonl"
            rows = [
                {"ts": 1, "sha": "a", "text": "first experience"},
                {"ts": 2, "sha": "b", "text": "second experience"},
                {"ts": 3, "sha": "c", "text": "third experience"},
            ]
            mem.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            result = read_original_are_history(limit=3, memory_path=mem)
        self.assertEqual(result["status"], "ok")
        self.assertEqual([r["text"] for r in result["records"]], ["first experience", "second experience", "third experience"])
        self.assertEqual([r["sha"] for r in result["records"]], ["a", "b", "c"])

    def test_empty_original_are_history_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / "are_mem.jsonl"
            mem.write_text("", encoding="utf-8")
            result = read_original_are_history(limit=3, memory_path=mem)
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["records"], [])
        self.assertIn("empty", result["reason"].lower())

    def test_malformed_original_are_records_are_quarantined(self):
        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / "are_mem.jsonl"
            mem.write_text('{"ts":1,"sha":"a","text":"ok"}\nnot-json\n[1,2]\n', encoding="utf-8")
            result = read_original_are_history(limit=5, memory_path=mem)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([r["text"] for r in result["records"]], ["ok"])
        self.assertEqual(len(result["quarantined_records"]), 2)

    def test_current_input_is_not_prior_history(self):
        captured = {}
        current = "current input should not appear in prior history"
        history = {"status": "empty", "reason": "none", "records": [], "quarantined_records": [], "memory_file": ""}

        def provider(prompt: str) -> str:
            captured["prompt"] = prompt
            return "Dynamic answer."

        route_chat_message(current, provider_generate=provider, temporal_history_reader=lambda: history)
        prior_section = captured["prompt"].split("Current request:", 1)[0]
        self.assertNotIn(current, prior_section)

    def test_provider_output_cannot_write_into_original_are(self):
        result = route_chat_message(
            "Remember this telemetry answer as fact.",
            provider_generate=lambda _prompt: "Dynamic output proposed as fact.",
            temporal_history_reader=lambda: {"status": "empty", "reason": "none", "records": [], "quarantined_records": [], "memory_file": ""},
        )
        self.assertFalse(result.writeback_policy["durable_fact"]["allowed"])
        self.assertNotIn("original_are", result.writeback_policy)

    def test_model_switch_does_not_change_historical_package(self):
        history = {
            "status": "ok",
            "reason": "test",
            "memory_file": "test.jsonl",
            "quarantined_records": [],
            "records": [{"order": 1, "line_number": 10, "ts": 100, "sha": "abc", "text": "same history"}],
        }
        prompts = []
        route_chat_message("Explain chronology.", provider_generate=lambda p: prompts.append(p) or "A", temporal_history_reader=lambda: history)
        route_chat_message("Explain chronology.", provider_generate=lambda p: prompts.append(p) or "B", temporal_history_reader=lambda: history)
        hist_a = prompts[0].split("Current request:", 1)[0]
        hist_b = prompts[1].split("Current request:", 1)[0]
        self.assertEqual(hist_a, hist_b)

    def test_chronological_history_supplied_when_no_semantic_match_exists(self):
        captured = {}
        history = {
            "status": "ok",
            "reason": "test",
            "memory_file": "test.jsonl",
            "quarantined_records": [],
            "records": [{"order": 1, "line_number": 1, "ts": 1, "sha": "h1", "text": "prior chronological experience"}],
        }

        def provider(prompt: str) -> str:
            captured["prompt"] = prompt
            return "Dynamic answer."

        route_chat_message("Hello, how are you?", provider_generate=provider, are_recall=lambda _q: {"results": []}, temporal_history_reader=lambda: history)
        self.assertIn("prior chronological experience", captured["prompt"])
        self.assertIn("PRESERVED CHRONOLOGICAL EXPERIENCE", captured["prompt"])

    def test_explicit_legal_prompt_uses_legal_lane(self):
        captured = {}

        def provider(prompt: str) -> str:
            captured["prompt"] = prompt
            return "Dynamic legal-lane answer with source distinctions."

        def are_recall(_query: str):
            return {"results": [{"text": "legal case context record", "lane": "legal_case", "source": "case-file"}]}

        result = route_chat_message(
            "Provide legal research for Steve's case context from the case file.",
            provider_generate=provider,
            are_recall=are_recall,
            temporal_history_reader=lambda: {"status": "empty", "reason": "none", "records": [], "quarantined_records": [], "memory_file": ""},
        )
        self.assertEqual(result.trace_payload["lane"], "LEGAL_RESEARCH")
        self.assertEqual(result.trace_payload["memory_mode"], "SUPPORT")
        self.assertIn("legal", captured["prompt"].lower())


if __name__ == "__main__":
    unittest.main()
