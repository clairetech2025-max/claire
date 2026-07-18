from __future__ import annotations

from typing import Any

from session_continuity import continuity_provider_lines


class ContextBuilder:
    def build(
        self,
        *,
        lane_result: Any,
        user_goal: str,
        current_truth: dict[str, Any],
        entities: list[dict[str, Any]],
        recent_path: list[dict[str, Any]],
        long_term_memories: list[dict[str, Any]],
        constraints: list[str],
        risks: list[str],
    ) -> dict[str, Any]:
        return build_context_packet(
            lane_result=lane_result,
            user_goal=user_goal,
            current_truth=current_truth,
            entities=entities,
            recent_path=recent_path,
            long_term_memories=long_term_memories,
            constraints=constraints,
            risks=risks,
        )


def build_context_packet(
    *,
    lane_result: Any,
    user_goal: str,
    current_truth: dict[str, Any],
    entities: list[dict[str, Any]],
    recent_path: list[dict[str, Any]],
    long_term_memories: list[dict[str, Any]],
    constraints: list[str],
    risks: list[str],
    temporal_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lane = lane_result.lane if hasattr(lane_result, "lane") else str(lane_result)
    packet = {
        "system_orientation": {
            "current_lane": lane,
            "user_goal": user_goal,
            "known_project": infer_project(lane, current_truth),
            "relevant_entities": entities,
            "recent_path": compact_memories(recent_path),
            "long_term_memories": compact_memories(long_term_memories),
            "cross_session_continuity": continuity_provider_lines(recent_path + long_term_memories),
            "current_truth": current_truth,
            "temporal_context": temporal_context or {},
            "constraints": constraints,
            "risks": risks,
            "what_not_to_assume": [
                "Do not treat model output as historical fact.",
                "Do not invent current time, elapsed time, deadline status, event order, or freshness when temporal context is silent.",
                "Do not cross legal, trading, horse, business, and architecture lanes unless admitted by this packet.",
                "Do not invent current project status when current truth files are silent.",
            ],
        }
    }
    return packet


def compact_memories(memories: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    compact = []
    for item in memories[:limit]:
        compact.append({
            "memory_id": item.get("memory_id"),
            "timestamp_ns": item.get("timestamp_ns"),
            "lane": item.get("lane"),
            "summary": item.get("summary"),
            "source": item.get("source"),
            "provenance_hash": item.get("provenance_hash"),
            "importance_score": item.get("importance_score"),
        })
    return compact


def infer_project(lane: str, current_truth: dict[str, Any]) -> str:
    if lane == "NVIDIA_PATHWAY":
        return "NVIDIA evaluation pathway"
    if lane == "TRADING_STATION":
        return "VERITAS financial intelligence station"
    if lane == "HORSE_STEWARDSHIP":
        return "horse stewardship mission"
    if lane == "BUSINESS_FORMATION":
        return "Claire Systems LLC formation"
    return str((current_truth.get("company_profile") or {}).get("name") or "CLAIRE")


def render_context_packet(packet: dict[str, Any]) -> str:
    orientation = packet.get("system_orientation", {})
    lines = ["SYSTEM ORIENTATION:"]
    labels = [
        ("Current lane", orientation.get("current_lane")),
        ("User goal", orientation.get("user_goal")),
        ("Known project", orientation.get("known_project")),
        ("Relevant entities", orientation.get("relevant_entities")),
        ("Recent path", orientation.get("recent_path")),
        ("Long-term memories", orientation.get("long_term_memories")),
        ("Cross-session continuity", orientation.get("cross_session_continuity")),
        ("Trusted temporal context", orientation.get("temporal_context")),
        ("Constraints", orientation.get("constraints")),
        ("Risks", orientation.get("risks")),
        ("What not to assume", orientation.get("what_not_to_assume")),
        ("Current truth", orientation.get("current_truth")),
    ]
    for label, value in labels:
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)
