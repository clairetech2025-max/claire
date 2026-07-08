from __future__ import annotations

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claire_sentinel.audit import SentinelAuditLog
from claire_sentinel.are_capsules import SENTINEL_MEMORY_LANE, SentinelARECapsuleWriter
from claire_sentinel.models import ActionRequest
from claire_sentinel.policy import SentinelPolicy
from claire_sentinel.runner import ClaireSentinelRunner
from are_memory_store import AREMemoryStore


def make_runner(tmp: str, policy: SentinelPolicy | None = None) -> ClaireSentinelRunner:
    return ClaireSentinelRunner(
        policy=policy or SentinelPolicy(allowlist={"127.0.0.1", "localhost"}),
        audit_log=SentinelAuditLog(Path(tmp) / "actions.jsonl"),
    )


def test_unauthorized_target_is_blocked_and_logged():
    with tempfile.TemporaryDirectory() as tmp:
        runner = make_runner(tmp)
        result = runner.run(ActionRequest("dig", target="example.com", reason="scope test", dry_run=True))
        assert result.decision.allowed is False
        assert "not on the Sentinel allowlist" in result.decision.reason
        assert "dig" in Path(tmp, "actions.jsonl").read_text(encoding="utf-8")


def test_active_scan_requires_operator_approval():
    with tempfile.TemporaryDirectory() as tmp:
        runner = make_runner(tmp)
        result = runner.run(ActionRequest("nmap", target="127.0.0.1", reason="local owned host", dry_run=True))
        assert result.decision.allowed is False
        assert result.decision.requires_approval is True


def test_active_scan_allows_dry_run_when_approved_and_allowlisted():
    with tempfile.TemporaryDirectory() as tmp:
        runner = make_runner(tmp)
        result = runner.run(ActionRequest("nmap", target="127.0.0.1", reason="local owned host", operator_approved=True, dry_run=True))
        assert result.decision.allowed is True
        assert result.output_summary == "Dry run only; command not executed."


def test_forbidden_tool_is_blocked_even_with_approval():
    with tempfile.TemporaryDirectory() as tmp:
        runner = make_runner(tmp)
        result = runner.run(ActionRequest("hydra", target="127.0.0.1", reason="should block", operator_approved=True, dry_run=True))
        assert result.decision.allowed is False
        assert "forbidden" in result.decision.reason.lower()


def test_reason_is_required():
    with tempfile.TemporaryDirectory() as tmp:
        runner = make_runner(tmp)
        result = runner.run(ActionRequest("dig", target="localhost", reason="", dry_run=True))
        assert result.decision.allowed is False
        assert "reason is required" in result.decision.reason


def test_secret_like_output_is_redacted_in_audit_log():
    with tempfile.TemporaryDirectory() as tmp:
        log = SentinelAuditLog(Path(tmp) / "actions.jsonl")
        log.append({"output_summary": "token: abcdef12345"})
        text = Path(tmp, "actions.jsonl").read_text(encoding="utf-8")
        assert "abcdef12345" not in text
        assert "[REDACTED_SECRET]" in text


def test_sentinel_action_writes_safe_are_capsule():
    with tempfile.TemporaryDirectory() as tmp:
        store = AREMemoryStore(Path(tmp) / "memory.db")
        runner = ClaireSentinelRunner(
            policy=SentinelPolicy(allowlist={"127.0.0.1"}),
            audit_log=SentinelAuditLog(Path(tmp) / "actions.jsonl"),
            are_writer=SentinelARECapsuleWriter(store),
        )
        result = runner.run(ActionRequest(
            "nmap",
            target="127.0.0.1",
            reason="local owned smoke test",
            operator_approved=True,
            dry_run=True,
        ))
        records = store.recall_for_lanes("sentinel", [SENTINEL_MEMORY_LANE], limit=10)
        assert result.decision.allowed is True
        assert len(records) == 1
        assert records[0]["lane"] == SENTINEL_MEMORY_LANE
        assert records[0]["memory_scope"] == "COMPANY_INTERNAL"
        assert "Dry run only" in records[0]["raw_excerpt"]
        assert "nmap" in records[0]["summary"]


def run_all() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()


if __name__ == "__main__":
    run_all()
    print("test_claire_sentinel: all checks passed")
