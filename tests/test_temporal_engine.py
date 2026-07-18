from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from claire_runtime import ClaireRuntime
from are_memory_store import AREMemoryStore, MemoryEvent
from claire_runtime_truth import Runtime3CRPAuthority, RuntimeTruthEvent, RuntimeTruthSpine, TrailLinkSigner, q_insight_packet, recognition_packet_from_are
from temporal_engine import TemporalEngine, TemporalEvent, TemporalInstant, TemporalInterval, TrustedClock, parse_aware_datetime
from trace_logger import TraceLogger


BASE = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)


def engine(root: Path, *, now: datetime = BASE, monotonic_values: list[float] | None = None) -> TemporalEngine:
    return TemporalEngine(
        root / "temporal.jsonl",
        clock=TrustedClock(now, monotonic_values or [10.0, 11.0, 15.0, 18.0, 22.0, 30.0]),
        default_timezone="America/Los_Angeles",
    )


def instant(dt: datetime, tz: str = "America/Los_Angeles") -> TemporalInstant:
    return TemporalInstant.from_datetime(dt, timezone_name=tz, source="user_statement", verified=False, confidence=0.8)


def test_utc_local_conversion_and_timezone_aware_only():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        ctx = te.get_now("s", "t", "America/Los_Angeles")
        assert ctx.now_utc == "2026-07-15T16:00:00Z"
        assert ctx.now_local.endswith("-07:00")
        try:
            parse_aware_datetime(datetime(2026, 1, 1))
            raise AssertionError("naive datetime must fail")
        except ValueError:
            pass


def test_daylight_saving_transition_uses_iana_zone():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td), now=datetime(2026, 3, 8, 9, 30, tzinfo=UTC))
        before = te.get_now("s", "t", "America/Los_Angeles").now_local
        te.clock.advance(timedelta(hours=2))
        after = te.get_now("s", "t", "America/Los_Angeles").now_local
        assert before.endswith("-08:00")
        assert after.endswith("-07:00")


def test_monotonic_elapsed_and_clock_rollback():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td), monotonic_values=[100.0, 105.0, 115.0])
        te.start_session("s")
        te.start_turn("s", "t")
        te.clock.fixed_utc = BASE - timedelta(days=1)
        ctx = te.get_now("s", "t")
        assert ctx.session_elapsed_seconds >= 15.0
        assert ctx.turn_elapsed_seconds >= 10.0


def test_restart_reloads_sessions_and_events_but_not_monotonic_assumption():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        te = engine(root)
        te.start_session("s")
        te.register_event(TemporalEvent(event_id="e1", event_type="deadline", title="investor call", due_at=instant(BASE + timedelta(days=2))))
        reloaded = TemporalEngine(root / "temporal.jsonl", clock=TrustedClock(BASE + timedelta(hours=1)), default_timezone="America/Los_Angeles")
        assert "s" in reloaded.sessions
        assert "e1" in reloaded._events
        assert reloaded.get_now("s", "t").session_elapsed_seconds >= 3600


def test_cross_session_elapsed_time_from_previous_turn():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td), monotonic_values=[1.0, 2.0, 3.0, 4.0])
        te.start_session("s")
        te.start_turn("s", "t1")
        te.clock.advance(timedelta(hours=2))
        te.start_turn("s", "t2")
        ctx = te.get_now("s", "t2")
        assert ctx.previous_turn_at is not None
        assert ctx.elapsed_since_previous_turn_seconds >= 7200


def test_relative_date_parsing_and_ambiguous_date_detection():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        tomorrow = te.resolve_expression("tomorrow at 10am", BASE, "America/Los_Angeles")
        ambiguous = te.resolve_expression("send it tomorrow morning", BASE, "America/Los_Angeles")
        assert tomorrow["status"] == "resolved"
        assert tomorrow["expressions"][0]["instant"]["precision"] == "day"
        assert ambiguous["status"] == "ambiguous"


def test_this_friday_vs_next_friday_are_distinct():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        this_friday = te.resolve_expression("this Friday at noon", BASE, "America/Los_Angeles")
        next_friday = te.resolve_expression("next Friday at noon", BASE, "America/Los_Angeles")
        left = parse_aware_datetime(this_friday["expressions"][0]["instant"]["utc_timestamp"])
        right = parse_aware_datetime(next_friday["expressions"][0]["instant"]["utc_timestamp"])
        assert (right - left).days == 7


def test_deadline_approaching_and_overdue():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        te.register_event(TemporalEvent(event_id="soon", event_type="deadline", title="call", due_at=instant(BASE + timedelta(days=1))))
        te.register_event(TemporalEvent(event_id="late", event_type="deadline", title="filing", due_at=instant(BASE - timedelta(hours=1))))
        deadlines = te.evaluate_deadlines_at(BASE)
        assert [item["event_id"] for item in deadlines["upcoming"]] == ["soon"]
        assert [item["event_id"] for item in deadlines["overdue"]] == ["late"]


def test_recurring_events_are_exposed_in_context():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        te.register_event(TemporalEvent(event_id="weekly", event_type="review", title="weekly review", recurrence_rule="FREQ=WEEKLY"))
        assert te.get_now("s", "t").recurring_patterns[0]["event_id"] == "weekly"


def test_category_sensitive_freshness_for_software_and_biography():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        old = BASE - timedelta(days=180)
        sw = {"summary": "Qwen model configuration version", "timestamp_ns": int(old.timestamp() * 1_000_000_000)}
        bio = {"summary": "Steve birthday", "timestamp_ns": int(old.timestamp() * 1_000_000_000)}
        assert te.evaluate_memory_freshness(sw, BASE).freshness_state == "stale"
        assert te.evaluate_memory_freshness(bio, BASE).freshness_state in {"current", "aging", "recent"}


def test_superseded_project_decision_and_historical_query():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        old = te.register_event(TemporalEvent(event_id="old", event_type="decision", title="model", occurred_at=instant(BASE - timedelta(days=20))))
        new = te.update_event(old.event_id, {"title": "model", "event_type": "decision", "occurred_at": instant(BASE)})
        assert te._events["old"].status == "superseded"
        ranked = te.rank_temporal_relevance(
            [{"memory_id": "old", "summary": "old model", "timestamp_ns": int((BASE - timedelta(days=20)).timestamp() * 1_000_000_000)}],
            query_time=BASE - timedelta(days=20),
            now=BASE,
        )
        assert ranked[0]["memory_id"] == "old"
        assert new.status == "current"


def test_recognition_rail_temporal_gap_and_stale_record():
    packet = recognition_packet_from_are(
        current_input_ref="hash",
        query="continue what we were doing",
        memories=[{"memory_id": "m1", "temporal_metadata": {"freshness_state": "stale"}}],
        rejected=[],
        temporal_context={"elapsed_since_previous_turn_seconds": 90000},
        temporal_resolution={"status": "none"},
    )
    assert packet["continuation_score"] > 0.45
    assert packet["temporal"]["state_may_have_changed"] is True


def test_q_insight_temporal_ambiguity_and_3crp_denial():
    q = q_insight_packet(
        query="Schedule it tomorrow morning",
        recognition={"unresolved_references": [], "are_record_refs": []},
        lane="GENERAL_CHAT",
        temporal_resolution={"status": "ambiguous", "ambiguities": [{"reason": "part_of_day_without_exact_time"}]},
    )
    decision = Runtime3CRPAuthority().authorize_temporal_operation(operation="schedule", temporal_resolution={"status": "ambiguous"}, high_impact=True)
    assert q["clarification_required"] is True
    assert decision["allowed"] is False


def test_gyro_temporal_orientation_and_runtime_truth_temporal_fields():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rt = ClaireRuntime(
            memory_store=AREMemoryStore(root / "memory.db"),
            trace_logger=TraceLogger(root / "trace.jsonl", root / "trace.db"),
            temporal_engine=engine(root),
        )
        rt.runtime_truth = RuntimeTruthSpine(root / "truth.jsonl", signer=TrailLinkSigner(b"k", "unit"))
        result = rt.handle_user_message(
            "steve",
            "s",
            "The investor call is Friday at noon.",
            {"provider_generate": lambda messages, config: "Recorded as a current planning fact with trusted temporal context."},
        )
        events = rt.runtime_truth.events()
        types = [event["event_type"] for event in events]
        assert "temporal.context_created" in types
        assert "temporal.relative_time_resolved" in types
        assert "temporal.event_registered" in types
        assert result["gyro"]["temporal_bearing"]["timezone"] == "America/Los_Angeles"
        assert rt.runtime_truth.verify()["valid"] is True


def test_veritas_chronology_verification_and_no_false_causation():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        a = TemporalEvent(event_id="deploy", event_type="deployment", title="deployment", occurred_at=instant(BASE))
        b = TemporalEvent(event_id="bug", event_type="bug", title="bug", occurred_at=instant(BASE + timedelta(hours=1)))
        chronology = te.verify_temporal_claim("bug after deployment", [a, b])
        causation = te.verify_temporal_claim("deployment caused bug", [a, b])
        assert chronology["status"] == "verified_chronology"
        assert causation["status"] == "unsupported_causation"


def test_legacy_truth_spine_records_and_turn_verification_with_temporal_payloads():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        spine = RuntimeTruthSpine(root / "truth.jsonl", signer=TrailLinkSigner(b"k", "unit"))
        spine.append(RuntimeTruthEvent(event_type="legacy.import", session_id="s", turn_id="t", actor={"type": "component", "id": "legacy"}, payload={"legacy_verification": "partially_verified"}))
        spine.append(RuntimeTruthEvent(event_type="temporal.context_created", session_id="s", turn_id="t", actor={"type": "component", "id": "temporal"}, payload={"event_timestamp_utc": BASE.isoformat()}))
        capsule = spine.seal_turn(session_id="s", turn_id="t", input_text="x", final_output="y")
        assert spine.verify()["valid"] is True
        assert spine.verify_turn_capsule(capsule)["valid"] is True


def test_timezone_change_conflicting_dates_approximate_future_order_and_open_interval():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        la = te.get_now("s", "t", "America/Los_Angeles")
        ny = te.get_now("s", "t", "America/New_York")
        assert la.timezone_name != ny.timezone_name

        e1 = TemporalEvent(event_id="a", event_type="deadline", title="call", due_at=instant(BASE + timedelta(days=1)))
        e2 = TemporalEvent(event_id="b", event_type="deadline", title="call", due_at=instant(BASE + timedelta(days=2)))
        assert te.detect_temporal_conflicts([e1, e2])

        approx = TemporalInstant.from_datetime(BASE, timezone_name="America/Los_Angeles", precision="approximate", source="inferred", verified=False, confidence=0.4)
        future = TemporalEvent(event_id="future", event_type="event", title="future", occurred_at=instant(BASE + timedelta(days=10)))
        past = TemporalEvent(event_id="past", event_type="event", title="past", occurred_at=approx)
        interval = TemporalInterval(start=approx, end=None, open_end=True, confidence=0.5)
        assert approx.precision == "approximate"
        assert te.build_ordering([future, past]) == ["past", "future"]
        assert interval.open_end is True


def test_acceptance_scenario_deadline_change_staleness_and_causality():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rt = ClaireRuntime(
            memory_store=AREMemoryStore(root / "memory.db"),
            trace_logger=TraceLogger(root / "trace.jsonl", root / "trace.db"),
            temporal_engine=engine(root),
        )
        rt.runtime_truth = RuntimeTruthSpine(root / "truth.jsonl", signer=TrailLinkSigner(b"k", "unit"))
        provider = lambda messages, config: "Using the trusted temporal packet and preserved source records."

        first = rt.handle_user_message("steve", "s1", "The investor call is Friday at noon.", {"provider_generate": provider})
        second = rt.handle_user_message("steve", "s2", "How long until the call?", {"provider_generate": provider})
        third = rt.handle_user_message("steve", "s3", "They moved it to Monday at 10.", {"provider_generate": provider})

        assert first["truth_spine"]["verification"]["valid"] is True
        assert second["temporal"]["trusted_runtime_time"]["current_utc"] == "2026-07-15T16:00:00Z"
        assert any(event.status == "superseded" for event in rt.temporal_engine._events.values())
        old_config = MemoryEvent(
            memory_id="cfg",
            user_id="steve",
            lane="CLAIRE_SYSTEM_ARCHITECTURE",
            summary="Old model configuration version",
            timestamp_ns=int((BASE - timedelta(days=120)).timestamp() * 1_000_000_000),
        ).to_dict()
        stale = rt.temporal_engine.evaluate_memory_freshness(old_config, BASE)
        assert stale.freshness_state == "stale"
        assert rt.temporal_engine.verify_temporal_claim("deployment caused the bug", [])["status"] == "unsupported_causation"
        assert third["truth_spine"]["verification"]["valid"] is True


def test_behavioral_patterns_are_visible_correctable_deletable_disableable_and_non_punitive():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        inference = te.record_behavioral_pattern(
            category="debugging_pace",
            observation="Long debugging sessions have recently been associated with more command-entry corrections.",
            detected_pattern="More corrections after extended sessions.",
            tentative_inference="Offer one implementation step at a time during long debugging work.",
            evidence_references=["trace_a", "trace_b", "trace_c"],
            observation_count=3,
            time_range_start="2026-07-01T00:00:00Z",
            time_range_end="2026-07-15T00:00:00Z",
            confidence=0.71,
            allowed_purpose="pacing",
        )
        assert inference is not None
        visible = te.inspect_behavioral_inferences()
        assert visible[0]["evidence_references"] == ["trace_a", "trace_b", "trace_c"]
        assert visible[0]["user_status"] == "unconfirmed"
        assert te.authorize_behavioral_use(inference.inference_id, "pacing")["allowed"] is True
        assert te.authorize_behavioral_use(inference.inference_id, "employment", high_impact=True)["allowed"] is False
        corrected = te.correct_behavioral_inference(inference.inference_id, "Prefer one complete patch at a time.", confirmed=True)
        assert corrected.user_status == "confirmed"
        exported = te.export_behavioral_inferences()
        assert exported["rules"]["high_impact_decision_allowed"] is False
        te.delete_behavioral_inference(inference.inference_id)
        assert te.inspect_behavioral_inferences() == []
        te.disable_behavior_category("debugging_pace")
        skipped = te.record_behavioral_pattern(
            category="debugging_pace",
            observation="x",
            detected_pattern="x",
            tentative_inference="x",
            evidence_references=[],
            observation_count=1,
            time_range_start="2026-07-01T00:00:00Z",
            time_range_end="2026-07-15T00:00:00Z",
            confidence=0.5,
            allowed_purpose="pacing",
        )
        assert skipped is None


def test_behavioral_patterns_reject_diagnostic_or_character_judgments():
    with tempfile.TemporaryDirectory() as td:
        te = engine(Path(td))
        try:
            te.record_behavioral_pattern(
                category="character",
                observation="Unsupported label.",
                detected_pattern="Unsupported label.",
                tentative_inference="The user is unreliable.",
                evidence_references=["trace_x"],
                observation_count=1,
                time_range_start="2026-07-01T00:00:00Z",
                time_range_end="2026-07-15T00:00:00Z",
                confidence=0.9,
                allowed_purpose="authority_reduction",
            )
            raise AssertionError("punitive behavioral inference must be rejected")
        except ValueError:
            pass
