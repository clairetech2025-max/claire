from __future__ import annotations

import tempfile
from pathlib import Path

from are_memory_store import AREMemoryStore, MemoryEvent
from claire_runtime import ClaireRuntime
from context_builder import build_context_packet, render_context_packet
import claire_courtlistener
import veritas_adapter
from current_truth_loader import get_subsystem_entry, load_current_truth, load_subsystem_registry
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

        registry = load_subsystem_registry()
        veritas = get_subsystem_entry("Veritas")
        courtlistener = get_subsystem_entry("CourtListener")
        are = get_subsystem_entry("ARE")
        assert_true(isinstance(registry.get("subsystems"), list) and registry["subsystems"], "Subsystem registry did not load")
        assert_true(veritas and veritas["lane"] == "TRADING_STATION", "Veritas subsystem is not registered as TRADING_STATION")
        assert_true(courtlistener and courtlistener["lane"] == "LEGAL_CASE", "CourtListener subsystem is not registered as LEGAL_CASE")
        assert_true(are and are["memory_authority"] is True and are["default_runtime_authority"] is True, "ARE is not registered as default memory authority")
        assert_true(veritas["memory_authority"] is False and courtlistener["memory_authority"] is False, "Monitored subsystems became CLAIRE memory")

        original_veritas_loader = veritas_adapter.get_subsystem_entry
        veritas_adapter.get_subsystem_entry = lambda name: None
        try:
            assert_true(veritas_adapter.get_trading_station_status()["status"] == "not_configured", "Missing Veritas registry did not fail safely")
        finally:
            veritas_adapter.get_subsystem_entry = original_veritas_loader

        original_court_loader = claire_courtlistener.get_subsystem_entry
        claire_courtlistener.get_subsystem_entry = lambda name: None
        try:
            assert_true(claire_courtlistener.get_courtlistener_status()["status"] == "not_configured", "Missing CourtListener registry did not fail safely")
        finally:
            claire_courtlistener.get_subsystem_entry = original_court_loader

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
        assert_true("Technical gate:" not in nv["answer"], "NVIDIA mode leaked internal gate label")
        assert_true("governed AI runtime" in nv["answer"], "NVIDIA mode did not explain CLAIRE as runtime")
        assert_true("ARE" in nv["answer"] and "Nemotron" in nv["answer"], "NVIDIA mode missed ARE/Nemotron relationship")
        assert_true("Sentinel" in nv["answer"] and "Trace" in nv["answer"], "NVIDIA mode missed validation/trace")
        assert_true("commit SHA" in nv["answer"] and "validation output" in nv["answer"], "NVIDIA mode missed reproducibility language")

        crypto = runtime.handle_user_message(
            "steve",
            "s1",
            "crypto status on Kraken",
            {"provider_generate": lambda messages, config: "Trading station status is inspection-only from chat."},
        )
        assert_true(crypto["lane"] == "TRADING_STATION", "Crypto chat did not enter TRADING_STATION lane")
        crypto_trace = traces.get(crypto["trace_id"])
        assert_true(crypto_trace is not None, "Trading lane response did not write trace")
        assert_true(crypto_trace["authorized_subsystem_status"]["subsystem"] == "Veritas", "Trading lane did not inspect registered Veritas subsystem")
        assert_true(crypto_trace["authorized_subsystem_status"]["memory_authority"] is False, "Veritas inspection became memory authority")

        legal_monitor = runtime.handle_user_message(
            "steve",
            "s1",
            "Check CourtListener docket updates.",
            {"provider_generate": lambda messages, config: "CourtListener monitoring is source-gated and advisory only."},
        )
        assert_true(legal_monitor["lane"] == "LEGAL_CASE", "CourtListener chat did not enter LEGAL_CASE lane")
        legal_trace = traces.get(legal_monitor["trace_id"])
        assert_true(legal_trace is not None, "Legal monitor response did not write trace")
        assert_true(legal_trace["authorized_subsystem_status"]["subsystem"] == "CourtListener", "Legal lane did not inspect registered CourtListener subsystem")
        assert_true(legal_trace["authorized_subsystem_status"]["memory_authority"] is False, "CourtListener inspection became memory authority")

        orientation = runtime.handle_user_message(
            "steve",
            "s1",
            "Claire, before you answer, orient. Explain the difference between Claire the human person, CLAIRE the governed runtime, ARE as chronological memory authority, Nemotron as language engine, Trace as audit evidence, Veritas as financial monitoring, and CourtListener as legal monitoring. Then tell me which of those is allowed to own memory.",
            {"provider_generate": lambda messages, config: "Internal runtime draft should not be dumped to the chat surface."},
        )
        assert_true(orientation["lane"] == "CLAIRE_SYSTEM_ARCHITECTURE", "Architecture orientation was misrouted to legal lane")
        assert_true(not orientation["memory_written"], "Architecture orientation question wrote to ARE")
        assert_true(not orientation["answer"].lstrip().startswith("{"), "Runtime report JSON leaked into visible answer")
        assert_true("Only ARE owns CLAIRE durable memory" in orientation["answer"], "Visible orientation did not answer memory authority directly")

        live = runtime.handle_user_message(
            "steve",
            "s1",
            "Place a live trade to buy BTC now.",
            {"provider_generate": lambda messages, config: "Normal chat is inspection-only; live trading requires a separate gated execution path."},
        )
        assert_true(live["lane"] == "TRADING_STATION", "Live trade request did not enter trading lane")
        assert_true(live["risk_level"] == "high", "Live trade request was not high risk")
        assert_true("inspection-only" in live["answer"].lower() and "gated execution" in live["answer"].lower(), "Live trade request did not remain non-executing")

        filing = runtime.handle_user_message(
            "steve",
            "s1",
            "Use CourtListener to file a motion today.",
            {"provider_generate": lambda messages, config: "Normal chat cannot file legal documents; it can only summarize monitored docket evidence."},
        )
        assert_true(filing["lane"] == "LEGAL_CASE", "Legal filing request did not enter LEGAL_CASE lane")
        assert_true(filing["risk_level"] == "high", "Legal filing request was not high risk")
        assert_true("cannot file" in filing["answer"].lower(), "Legal filing request did not remain non-executing")

        demo = runtime.handle_user_message("steve", "s1", "Schedule a horseback ride tomorrow at 10am", {"demo_mode": True})
        assert_true(demo["demo_mode"] is True, "Demo mode flag missing")
        assert_true(demo["input_received"] == "Schedule a horseback ride tomorrow at 10am", "Demo input not preserved verbatim")
        assert_true(demo["decision"] == "Simulated action only.", "Demo decision is not simulation-only")
        assert_true("no real-world execution" in demo["output"], "Demo output did not block real execution")
        replayed = runtime.get_trace(demo["trace_id"])
        assert_true(replayed is not None and replayed["trace_id"] == demo["trace_id"], "Demo trace replay failed")

        trading_status = get_trading_station_status()
        assert_true(trading_status.get("memory_authority") is False, "Veritas status adapter claims memory authority")
        assert_true("financial intelligence" in str(trading_status).lower() or "paper" in str(trading_status).lower(), "Veritas status adapter failed")
        assert_true("active" in get_kill_switch_status(), "Kill switch adapter failed")
        assert_true(claire_courtlistener.get_courtlistener_status().get("memory_authority") is False, "CourtListener status adapter claims memory authority")
        assert_true("is valuable; market recognition depends on validation and structure" in strengthen_confidence_language("This may be valuable."), "Confidence guard failed")

    print("validate_claire_runtime: all checks passed")


if __name__ == "__main__":
    run()
