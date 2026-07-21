import tempfile
from pathlib import Path

from are_memory_store import AREMemoryStore
from claire_runtime import ClaireRuntime
from trace_logger import TraceLogger


def make_runtime(root: Path) -> ClaireRuntime:
    return ClaireRuntime(
        memory_store=AREMemoryStore(root / "memory.db"),
        trace_logger=TraceLogger(root / "traces.jsonl", root / "traces.db"),
    )


def test_five_turn_project_fact_correction_uses_relevant_memory_only():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runtime = make_runtime(root)
        provider_contexts: list[str] = []

        def provider(messages, config):
            context = messages[1]["content"] if len(messages) > 1 else ""
            user = messages[-1]["content"]
            provider_contexts.append(context)
            lowered = user.lower()
            if "two plus two" in lowered:
                assert "ORCHARD" not in context
                assert "RIVERSTONE" not in context
                return "Two plus two is 4."
            if "codename did i give" in lowered:
                assert "ORCHARD" in context
                assert "RIVERSTONE" not in context
                return "You previously gave ORCHARD as the project codename."
            if "current project codename" in lowered:
                assert "ORCHARD" in context
                assert "RIVERSTONE" in context
                assert "CURRENT project.codename = RIVERSTONE" in context
                assert "HISTORICAL project.codename = ORCHARD" in context
                return "Current accepted codename is RIVERSTONE. History: ORCHARD was first saved, then corrected to RIVERSTONE."
            return "Recorded."

        turn1 = runtime.handle_user_message(
            "steve",
            "session-a",
            "Remember this: the project codename is ORCHARD.",
            {"provider_generate": provider, "trusted_device": True},
        )
        turn2 = runtime.handle_user_message(
            "steve",
            "session-a",
            "What is two plus two?",
            {"provider_generate": provider, "trusted_device": True},
        )
        turn3 = runtime.handle_user_message(
            "steve",
            "session-a",
            "What codename did I give you earlier?",
            {"provider_generate": provider, "trusted_device": True},
        )
        turn4 = runtime.handle_user_message(
            "steve",
            "session-a",
            "Correction: remember this: the project codename is RIVERSTONE, replacing ORCHARD.",
            {"provider_generate": provider, "trusted_device": True},
        )
        turn5 = runtime.handle_user_message(
            "steve",
            "session-a",
            "What is the current project codename, and what changed?",
            {"provider_generate": provider, "trusted_device": True},
        )

        assert turn1["memory_written"] is True
        assert turn2["used_memory"] == []
        assert turn3["used_memory"]
        assert "ORCHARD" in turn3["answer"]
        assert turn4["memory_written"] is True
        assert len(turn5["used_memory"]) >= 2
        assert "RIVERSTONE" in turn5["answer"]
        assert "ORCHARD" in turn5["answer"]

        trace = runtime.trace_logger.get(turn5["trace_id"])
        assert trace is not None
        assert trace["steps"].index("are_chronological_recall") < trace["steps"].index("nemotron_prompt_construction")
        assert trace["memories_recalled"] == turn5["used_memory"]
        assert len(provider_contexts) == 5
