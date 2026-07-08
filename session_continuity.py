from __future__ import annotations

from typing import Any


def build_session_recovery(recent_memories: list[dict[str, Any]], current_truth: dict[str, Any]) -> dict[str, Any]:
    last = recent_memories[-1] if recent_memories else None
    return {
        "active_project": (current_truth.get("repo_checkpoint") or {}).get("active_project") or (current_truth.get("company_profile") or {}).get("name") or "CLAIRE",
        "last_milestone": last.get("summary") if last else "No recent milestone recorded in governed memory.",
        "next_action": (current_truth.get("repo_checkpoint") or {}).get("next_action") or "Inspect current repo/runtime state before acting.",
        "blockers": (current_truth.get("repo_checkpoint") or {}).get("blockers") or [],
        "current_file_repo_state": current_truth.get("repo_checkpoint"),
    }
