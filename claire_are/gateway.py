from __future__ import annotations

from typing import Any, Callable

from claire_are.core import AREStore

LLMProvider = Callable[[str, str, str, dict[str, Any]], str]


def default_llm_provider(prompt: str, context: str, model: str, metadata: dict[str, Any]) -> str:
    if context.strip():
        return f"Governed response using ARE recall first: {context[:500]}"
    return "Governed response: no matching ARE memory was found, so no memory-backed claim is made."


class GovernedGateway:
    """Enforces consult-before-LLM execution."""

    def __init__(self, store: AREStore, llm_provider: LLMProvider | None = None) -> None:
        self.store = store
        self.llm_provider = llm_provider or default_llm_provider

    def complete(self, *, prompt: str, lane: str, model: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        recall = self.store.recall(query=prompt, lane=lane, limit=8, log=True)
        if not recall.get("recall_event_sha"):
            raise RuntimeError("ARE recall event missing; refusing LLM completion")
        memories = recall.get("memories") or []
        context = "\n".join(f"- {item['text']}" for item in memories)
        answer = self.llm_provider(prompt, context, model, metadata or {})
        completion_event = self.store.log_event(
            text=f"LLM completion lane={lane} model={model} prompt={prompt[:500]}",
            lane="audit",
            source="are_gateway",
            event_type="llm_complete",
            metadata={
                "requesting_lane": lane,
                "model": model,
                "recall_event_sha": recall["recall_event_sha"],
                "memories_used": [item["sha"] for item in memories],
            },
        )
        return {
            "prompt": prompt,
            "lane": lane,
            "model": model,
            "recall_event_sha": recall["recall_event_sha"],
            "completion_event_sha": completion_event["sha"],
            "memories_used": memories,
            "answer": answer,
        }
