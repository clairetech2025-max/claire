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


def test_green_restart_restores_durable_memory_and_trace_store():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        first = make_runtime(root)
        first_result = first.handle_user_message(
            "steve",
            "restart-session",
            "Remember this: the project codename is ORCHARD.",
            {"provider_generate": lambda messages, config: "Recorded.", "trusted_device": True},
        )
        assert first_result["memory_written"] is True
        assert first.trace_logger.get(first_result["trace_id"]) is not None

        second = make_runtime(root)

        def provider(messages, config):
            context = messages[1]["content"] if len(messages) > 1 else ""
            assert "ORCHARD" in context
            assert "CURRENT project.codename = ORCHARD" in context
            return "The restored durable memory says the project codename is ORCHARD."

        recalled = second.handle_user_message(
            "steve",
            "restart-session",
            "What codename did I give you earlier?",
            {"provider_generate": provider, "trusted_device": True},
        )
        assert recalled["used_memory"]
        assert "ORCHARD" in recalled["answer"]
        assert second.trace_logger.get(recalled["trace_id"]) is not None
