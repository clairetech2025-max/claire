from __future__ import annotations

import tempfile
from pathlib import Path

from are_memory_store import AREMemoryStore, MemoryEvent
from claire_runtime import ClaireRuntime
from context_builder import build_context_packet, render_context_packet
from current_truth_loader import load_current_truth
from entity_registry import identify_entities
from lane_classifier import classify_lane
from language_guard import strengthen_confidence_language
from memory_eligibility import evaluate_memory_eligibility
from nemotron_adapter import build_messages
from sentinel_validator import validate_response
from trace_logger import TraceLogger
from veritas_adapter import get_kill_switch_status, get_trading_station_status


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = AREMemoryStore(tmp_path / "memory.db")
        traces = TraceLogger(tmp_path / "traces.jsonl", tmp_path / "traces.db")

        assert_true(classify_lane("NVIDIA Nemotron reproducible benchmark").lane == "NVIDIA_PATHWAY", "NVIDIA lane classification failed")
        assert_true(classify_lane("Pedro needs hay support").lane == "HORSE_STEWARDSHIP", "Horse lane classification failed")
        assert_true(classify_lane("Veritas backtest on Kraken OHLCV").lane == "TRADING_STATION", "Trading lane classification failed")

        truth = load_current_truth()
        founding = truth["founding_team"]
        assert_true(founding["Steve Roth"] == "Founder, CEO & Chief Architect", "Steve role missing")
        assert_true("Equine Stewardship" in founding["Claire"], "Claire person role missing")
        assert_true("Equine Stewardship" in founding["Brisa"], "Brisa role missing")
        assert_true("potential officer" in founding["Jason"].lower(), "Jason role missing")
        assert_true("horse stewardship" in truth["company_profile"]["structure"].lower(), "Company dual mission missing")
        assert_true("central mission assets, not a side project" in truth["mission_statement"].lower(), "Mission statement weakens horses")

        names = [entity["name"] for entity in identify_entities("Claire and CLAIRE are different; Nemotron is downstream.")]
        assert_true("Claire" in names, "Claire person not identified")
        assert_true("CLAIRE" in names, "CLAIRE system not identified")

        old = MemoryEvent(
            user_id="steve",
            session_id="s1",
            lane="BUSINESS_FORMATION",
            summary="Old memory says Steve is not CEO.",
            raw_excerpt="Old memory says Steve is not CEO.",
            related_entities=["Steve Roth"],
            timestamp_ns=1,
        )
        new = MemoryEvent(
            user_id="steve",
            session_id="s1",
            lane="BUSINESS_FORMATION",
            summary="Steve is Founder, CEO & Chief Architect.",
            raw_excerpt="Steve is Founder, CEO & Chief Architect.",
            related_entities=["Steve Roth"],
            timestamp_ns=2,
        )
        store.append_memory_event(old)
        store.append_memory_event(new)
        recalled = store.recall_recent("steve", lane="BUSINESS_FORMATION", limit=2)
        assert_true([item["summary"] for item in recalled][-1] == "Steve is Founder, CEO & Chief Architect.", "ARE recall is not chronological")
        assert_true(not store.recall_recent("steve", lane="LEGAL_CASE", limit=5), "Irrelevant lane memory leaked")

        eligibility = evaluate_memory_eligibility("Remember this: NVIDIA pathway milestone reached.", "NVIDIA_PATHWAY")
        assert_true(eligibility.should_consider_write, "Explicit remember did not become writable")
        sensitive = evaluate_memory_eligibility("remember this password: secret", "GENERAL_CHAT")
        assert_true(sensitive.requires_confirmation and not sensitive.should_consider_write, "Sensitive memory was not quarantined")

        packet = build_context_packet(
            lane_result=classify_lane("NVIDIA pathway"),
            user_goal="NVIDIA pathway",
            current_truth=truth,
            entities=[],
            recent_path=[],
            long_term_memories=[],
            constraints=[],
            risks=[],
        )
        rendered = render_context_packet(packet)
        assert_true("SYSTEM ORIENTATION" in rendered and "Current lane" in rendered, "Context packet missing orientation")
        messages = build_messages(packet, "NVIDIA pathway")
        assert_true("SYSTEM ORIENTATION" in messages[1]["content"], "Nemotron prompt missing orientation context")

        bad = validate_response("This can guarantee risk-free profit and buy now.", packet, "TRADING_STATION")
        assert_true(not bad["approved"], "Sentinel missed trading contradiction/risk")

        runtime = ClaireRuntime(memory_store=store, trace_logger=traces)
        result = runtime.handle_user_message("steve", "s1", "Remember this: CLAIRE routes Nemotron through a governed runtime.")
        for key in ["answer", "lane", "used_memory", "risk_level", "trace_id", "memory_written"]:
            assert_true(key in result, f"Runtime schema missing {key}")
        assert_true(result["memory_written"], "Explicit durable runtime fact was not written")
        assert_true(traces.get(result["trace_id"]) is not None, "Trace logger did not write response")

        nv = runtime.handle_user_message("steve", "s1", "NVIDIA pathway status and next gate?")
        assert_true(nv["lane"] == "NVIDIA_PATHWAY", "Runtime failed NVIDIA lane")
        assert_true("Technical gate" in nv["answer"], "NVIDIA mode did not preserve reproducibility language")

        demo = runtime.handle_user_message("steve", "s1", "Schedule a horseback ride tomorrow at 10am", {"demo_mode": True})
        assert_true(demo["demo_mode"] is True, "Demo mode flag missing")
        assert_true(demo["input_received"] == "Schedule a horseback ride tomorrow at 10am", "Demo input not preserved verbatim")
        assert_true(demo["decision"] == "Simulated action only.", "Demo decision is not simulation-only")
        assert_true("no real-world execution" in demo["output"], "Demo output did not block real execution")
        replayed = runtime.get_trace(demo["trace_id"])
        assert_true(replayed is not None and replayed["trace_id"] == demo["trace_id"], "Demo trace replay failed")

        assert_true("financial intelligence" in str(get_trading_station_status()).lower() or "paper" in str(get_trading_station_status()).lower(), "Veritas status adapter failed")
        assert_true("active" in get_kill_switch_status(), "Kill switch adapter failed")
        assert_true("is valuable; market recognition depends on validation and structure" in strengthen_confidence_language("This may be valuable."), "Confidence guard failed")

    print("validate_claire_runtime: all checks passed")


if __name__ == "__main__":
    run()
