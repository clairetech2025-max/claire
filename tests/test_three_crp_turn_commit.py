from claire_turn_commit import (
    ThreeCRPTurnController,
    TurnState,
    gyro_orient_committed_turn,
    q_insight_completion_check,
)


def test_three_text_fragments_merge_before_send():
    controller = ThreeCRPTurnController()
    controller.add_fragment("I want to translate this.")
    controller.add_fragment("Tell Freddy I took two bales.")
    controller.add_fragment("Also tell him the money is on the hay hooks.")

    assert controller.buffer.state == TurnState.USER_DRAFTING
    assert controller.metrics.premature_model_calls_prevented == 3

    committed = controller.commit("send")

    assert committed.state == TurnState.TURN_COMMITTED
    assert committed.committed_prompt.count("\n") == 2
    assert "two bales" in committed.committed_prompt
    assert controller.metrics.committed_turns == 1
    assert controller.metrics.fragments_merged == 3


def test_voice_pauses_do_not_commit_without_explicit_handoff():
    controller = ThreeCRPTurnController()
    controller.add_fragment("I want to ask Claire")
    check = controller.check_completion("")

    assert check.recommends_waiting is True
    assert controller.buffer.state == TurnState.COMPLETION_CHECK
    assert controller.metrics.committed_turns == 0


def test_hold_on_recommends_waiting_and_continues():
    check = q_insight_completion_check("hold on, one more thing", "")

    assert check.recommends_waiting is True
    assert check.explicit_handoff is False
    assert any("wait" in reason.lower() or "continuation" in reason.lower() for reason in check.reasons)


def test_user_interrupts_claire_while_speaking():
    controller = ThreeCRPTurnController()
    controller.speak()
    controller.interrupt()

    assert controller.buffer.state == TurnState.INTERRUPTED
    assert controller.metrics.tts_interruptions == 1


def test_topic_change_before_commit_stays_one_canonical_turn():
    controller = ThreeCRPTurnController()
    controller.add_fragment("First translate this for Freddy.")
    controller.add_fragment("Actually also explain why the model returned a network error.")
    committed = controller.commit("done")

    assert "Freddy" in committed.committed_prompt
    assert "network error" in committed.committed_prompt
    assert committed.completion is not None
    assert committed.orientation is not None


def test_done_explicitly_commits_even_when_q_insight_is_uncertain():
    controller = ThreeCRPTurnController()
    controller.add_fragment("that")
    committed = controller.commit("done")

    assert committed.state == TurnState.TURN_COMMITTED
    assert committed.completion is not None
    assert committed.completion.explicit_handoff is True


def test_silence_timeout_enabled_and_disabled_behavior():
    disabled = ThreeCRPTurnController(silence_timeout_enabled=False)
    disabled.add_fragment("I am still thinking")
    assert disabled.check_completion("").recommends_waiting is True
    assert disabled.metrics.committed_turns == 0

    enabled = ThreeCRPTurnController(silence_timeout_enabled=True)
    enabled.add_fragment("I am still thinking")
    committed = enabled.commit("silence_timeout")
    assert committed.state == TurnState.TURN_COMMITTED
    assert enabled.metrics.automatic_commits == 1


def test_q_insight_uncertain_short_fragment_waits():
    check = q_insight_completion_check("also", "")

    assert check.confidence < 0.62
    assert check.recommends_waiting is True


def test_provider_failure_after_commit_preserves_committed_turn():
    controller = ThreeCRPTurnController()
    controller.add_fragment("Ask CourtListener about Wilson v Cook 1987.")
    committed = controller.commit("send")
    controller.think()
    controller.provider_failed("llama status 400")

    assert committed.committed_prompt.startswith("Ask CourtListener")
    assert controller.buffer.provider_error == "llama status 400"
    assert controller.buffer.state == TurnState.RETURNING_FLOOR


def test_draft_survives_refresh_round_trip():
    controller = ThreeCRPTurnController()
    controller.add_fragment("Line one before refresh.")
    controller.add_fragment("Line two before refresh.")

    restored = ThreeCRPTurnController.restore(controller.serialize())

    assert restored.buffer.state == TurnState.USER_DRAFTING
    assert restored.buffer.canonical_prompt() == "Line one before refresh.\nLine two before refresh."


def test_gyro_orients_legal_queries_to_research_lane():
    orientation = gyro_orient_committed_turn("Research Wilson v Cook 1987 and CCR 4331.")

    assert orientation.active_c3rp_lane == "legal_research"
    assert "courtlistener" in orientation.required_tools
