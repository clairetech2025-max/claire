from __future__ import annotations

from session_continuity import (
    SessionCapsule,
    SentimentMonitor,
    auto_checkpoint_session_capsule,
    build_cross_session_continuity_context,
    build_session_recovery,
    continuity_provider_lines,
    current_value,
    render_session_capsule_bootstrap,
)


def test_session_recovery_uses_repo_checkpoint_and_newest_memory():
    result = build_session_recovery(
        [
            {"summary": "older milestone", "timestamp_ns": 10, "source": "old_trace"},
            {"summary": "newer milestone", "timestamp_ns": 20, "source": "new_trace"},
        ],
        {
            "repo_checkpoint": {
                "active_project": "CLAIRE runtime",
                "next_action": "continue trace replay work",
                "blockers": ["provider unavailable"],
            },
            "company_profile": {"name": "Claire Systems"},
        },
    )

    assert result["recovery_status"] == "ready"
    assert result["active_project"] == "CLAIRE runtime"
    assert result["last_milestone"] == "newer milestone"
    assert result["last_milestone_source"] == "new_trace"
    assert result["next_action"] == "continue trace replay work"
    assert result["blockers"] == ["provider unavailable"]
    assert result["continuity_sources"]["recent_memory_count"] == 2


def test_session_recovery_falls_back_without_truth_or_memory():
    result = build_session_recovery([], {})

    assert result["recovery_status"] == "minimal"
    assert result["active_project"] == "CLAIRE"
    assert result["last_milestone"] == "No recent milestone recorded in governed memory."
    assert result["last_milestone_source"] == "none"
    assert result["next_action"] == "Inspect current repo/runtime state before acting."
    assert result["blockers"] == []
    assert result["current_file_repo_state"] is None


def test_session_recovery_ignores_malformed_memory_records():
    result = build_session_recovery(
        [None, "bad", {}, {"summary": "usable", "created_at": "2026-01-01", "lane": "SESSION"}],
        {"company_profile": {"name": "Claire Systems"}},
    )

    assert result["recovery_status"] == "ready"
    assert result["active_project"] == "Claire Systems"
    assert result["last_milestone"] == "usable"
    assert result["last_milestone_source"] == "SESSION"
    assert result["continuity_sources"]["recent_memory_count"] == 1


def test_session_recovery_redacts_secret_like_text():
    result = build_session_recovery(
        [{"summary": "The execution passphrase is BATTLEBORN_TESTSECRET", "timestamp_ns": 1}],
        {"repo_checkpoint": {"active_project": "CLAIRE", "next_action": "token is abcdefgh", "blockers": "api key is abcdefgh"}},
    )
    encoded = str(result)

    assert "BATTLEBORN_TESTSECRET" not in encoded
    assert "abcdefgh" not in encoded
    assert "[REDACTED_BY_DIODE]" in encoded


def test_cross_session_continuity_resolves_correction_without_rewriting_history():
    memories = [
        {
            "memory_id": "mem_old",
            "timestamp_ns": 100,
            "lane": "BUSINESS_FORMATION",
            "source": "chat_runtime",
            "summary": "Remember this: the project codename is ORCHARD.",
            "provenance_hash": "hash-old",
        },
        {
            "memory_id": "mem_new",
            "timestamp_ns": 200,
            "lane": "BUSINESS_FORMATION",
            "source": "chat_runtime",
            "summary": "Correction: remember this: the project codename is RIVERSTONE, replacing ORCHARD.",
            "provenance_hash": "hash-new",
        },
    ]

    context = build_cross_session_continuity_context(memories)

    assert context["current"]["project.codename"]["value"] == "RIVERSTONE"
    assert context["current"]["project.codename"]["memory_id"] == "mem_new"
    assert context["superseded"][0]["value"] == "ORCHARD"
    assert context["superseded"][0]["memory_id"] == "mem_old"
    assert len(context["history"]) == 2
    assert context["unresolved"] == []
    assert current_value(memories, "project", "codename") == "RIVERSTONE"


def test_cross_session_continuity_surfaces_unresolved_conflict_without_inventing_current_state():
    memories = [
        {
            "memory_id": "mem_a",
            "timestamp_ns": 100,
            "summary": "Remember this: the project codename is ORCHARD.",
        },
        {
            "memory_id": "mem_b",
            "timestamp_ns": 200,
            "summary": "Remember this: the project codename is RIVERSTONE.",
        },
    ]

    context = build_cross_session_continuity_context(memories)

    assert context["current"]["project.codename"]["value"] == "ORCHARD"
    assert context["unresolved"]
    assert context["unresolved"][0]["reason"] == "conflicting recalled values without explicit correction language"


def test_continuity_provider_lines_are_compact_and_evidence_backed():
    lines = continuity_provider_lines(
        [
            {
                "memory_id": "mem_old",
                "timestamp_ns": 100,
                "summary": "Remember this: the project codename is ORCHARD.",
            },
            {
                "memory_id": "mem_new",
                "timestamp_ns": 200,
                "summary": "Correction: remember this: the project codename is RIVERSTONE, replacing ORCHARD.",
            },
        ]
    )

    rendered = "\n".join(lines)
    assert "CURRENT project.codename = RIVERSTONE" in rendered
    assert "HISTORICAL project.codename = ORCHARD" in rendered
    assert "mem_new" in rendered


def test_session_capsule_bootstrap_contains_state_style_and_rules():
    capsule = SessionCapsule(
        scope="CLAIRE cross-AI continuity",
        current_state="Continuity and sentiment are merged into session capsule code.",
        changes=["Merged sentiment profile.", "Added bootstrap renderer."],
        failures=["Do not rely on conversational memory alone."],
        restore_point="Load the newest bootstrap before resuming work.",
        next_safe_step="Run the focused continuity tests.",
        do_not_repeat=["Do not restart from first principles."],
        active_tasks=["Session Capsule integration"],
        important_files=["session_continuity.py"],
    )

    rendered = render_session_capsule_bootstrap(capsule)

    assert "CLAIRE CONTINUITY + SENTIMENT BOOTSTRAP" in rendered
    assert "CLAIRE cross-AI continuity" in rendered
    assert "Run the focused continuity tests." in rendered
    assert "Speak plainly and directly." in rendered
    assert "Do not restart from first principles." in rendered


def test_sentiment_monitor_recommends_checkpoint_after_reorientation():
    state = SentimentMonitor().evaluate(
        [
            {"role": "user", "content": "You forgot the file."},
            {"role": "assistant", "content": "I will check."},
            {"role": "user", "content": "I already told you. Refresh your memory."},
        ],
        objective="merge continuity bootstrap",
    )

    assert state.reset_recommended is True
    assert state.drift >= 0.62
    assert state.reasons


def test_auto_checkpoint_saves_when_drift_threshold_is_met(tmp_path):
    capsule = SessionCapsule(
        scope="CLAIRE continuity",
        current_state="Testing checkpoint persistence.",
        changes=[],
        failures=[],
        restore_point="Continue from focused tests.",
        next_safe_step="merge continuity bootstrap",
        do_not_repeat=[],
    )

    result = auto_checkpoint_session_capsule(
        [
            {"role": "user", "content": "You forgot the file."},
            {"role": "assistant", "content": "I will check."},
            {"role": "user", "content": "I already told you. Refresh your memory."},
        ],
        capsule,
        tmp_path,
    )

    assert result["saved"]
    assert result["saved"]["json"].endswith(".json")
    assert result["saved"]["bootstrap"].endswith("_BOOTSTRAP.txt")
