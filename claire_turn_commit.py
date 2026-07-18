from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TurnState(str, Enum):
    IDLE = "IDLE"
    USER_FLOOR_OPEN = "USER_FLOOR_OPEN"
    USER_DRAFTING = "USER_DRAFTING"
    COMPLETION_CHECK = "COMPLETION_CHECK"
    TURN_COMMITTED = "TURN_COMMITTED"
    ORIENTING = "ORIENTING"
    ROUTING = "ROUTING"
    THINKING = "THINKING"
    CLAIRE_SPEAKING = "CLAIRE_SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    RETURNING_FLOOR = "RETURNING_FLOOR"


EXPLICIT_COMMIT_TRIGGERS = {
    "send",
    "done",
    "over",
    "ctrl_enter",
    "mic_done",
    "voice_over",
    "silence_timeout",
}


@dataclass
class CompletionCheck:
    complete: bool
    confidence: float
    explicit_handoff: bool
    recommends_waiting: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class GyroOrientation:
    current_subject: str
    user_intent: str
    continuation: bool
    topic_change: bool
    active_c3rp_lane: str
    required_memory_mode: str
    required_tools: list[str] = field(default_factory=list)


@dataclass
class TurnMetrics:
    fragments_merged: int = 0
    premature_model_calls_prevented: int = 0
    retrieval_calls_prevented: int = 0
    generated_tokens_avoided: int = 0
    input_tokens_avoided: int = 0
    committed_turns: int = 0
    explicit_commits: int = 0
    automatic_commits: int = 0
    false_early_commits: int = 0
    false_delayed_commits: int = 0
    tts_interruptions: int = 0
    total_open_turn_seconds: float = 0.0

    @property
    def average_open_turn_duration(self) -> float:
        if self.committed_turns <= 0:
            return 0.0
        return self.total_open_turn_seconds / self.committed_turns


@dataclass
class TurnBuffer:
    state: TurnState = TurnState.IDLE
    fragments: list[str] = field(default_factory=list)
    opened_at: float | None = None
    committed_prompt: str = ""
    completion: CompletionCheck | None = None
    orientation: GyroOrientation | None = None
    commit_trigger: str | None = None
    provider_error: str | None = None

    def canonical_prompt(self) -> str:
        return "\n".join(fragment.strip() for fragment in self.fragments if fragment.strip()).strip()


def estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text or "")))


def normalize_fragments(fragments: list[str]) -> list[str]:
    normalized: list[str] = []
    for fragment in fragments:
        clean = re.sub(r"[ \t]+", " ", str(fragment or "")).strip()
        if clean:
            normalized.append(clean)
    return normalized


def q_insight_completion_check(text: str, trigger: str = "") -> CompletionCheck:
    clean = str(text or "").strip()
    lowered = clean.lower()
    explicit = trigger in EXPLICIT_COMMIT_TRIGGERS or bool(re.search(r"\b(over|done)\s*[.!?]?$", lowered))
    reasons: list[str] = []

    if not clean:
        return CompletionCheck(False, 0.0, explicit, True, ["No user content is present."])

    wait_markers = [
        "hold on",
        "wait",
        "one more thing",
        "another thing",
        "let me finish",
        "not done",
        "stand by",
        "standby",
    ]
    continuation_markers = [
        "and ",
        "also",
        "plus",
        "then",
        "because",
        "but",
        "except",
    ]
    unresolved_refs = [
        "that",
        "this",
        "it",
        "those",
        "them",
    ]

    if any(marker in lowered for marker in wait_markers):
        reasons.append("User used a wait or continuation marker.")
    if re.search(r"(and|also|plus|another thing)[: ]*$", lowered):
        reasons.append("Turn appears to end with an unresolved continuation.")
    if lowered.endswith((" and", " but", " because", " so", ",")):
        reasons.append("Turn ends with an incomplete connector.")
    if len(clean) < 18 and any(re.fullmatch(word, lowered) for word in unresolved_refs):
        reasons.append("Short unresolved reference detected.")

    punctuation_complete = clean.endswith((".", "?", "!", '"', "'"))
    multi_line = "\n" in clean
    enough_content = estimate_tokens(clean) >= 6
    starts_with_continuation = any(lowered.startswith(marker) for marker in continuation_markers)

    confidence = 0.35
    if punctuation_complete:
        confidence += 0.2
    if enough_content:
        confidence += 0.2
    if multi_line:
        confidence += 0.1
    if explicit:
        confidence = max(confidence, 0.95)
        reasons.append("User explicitly handed over the turn.")
    if starts_with_continuation:
        confidence -= 0.12
        reasons.append("Turn begins as a continuation.")
    if reasons and not explicit:
        confidence -= 0.25

    confidence = round(max(0.0, min(1.0, confidence)), 3)
    recommends_waiting = (not explicit) and (bool(reasons) or confidence < 0.62)
    return CompletionCheck(
        complete=not recommends_waiting,
        confidence=confidence,
        explicit_handoff=explicit,
        recommends_waiting=recommends_waiting,
        reasons=reasons or ["No continuation marker detected."],
    )


def gyro_orient_committed_turn(text: str, prior_subject: str = "") -> GyroOrientation:
    lowered = str(text or "").lower()
    if any(token in lowered for token in ["courtlistener", "case", "citation", "statute", "ccr", "docket", "judge"]):
        lane = "legal_research"
        intent = "research_or_legal_analysis"
        tools = ["courtlistener", "web_search"]
        memory_mode = "evidence_support"
    elif any(token in lowered for token in ["upload", "document", "pdf", "file", "ingest"]):
        lane = "document_ingest"
        intent = "document_processing"
        tools = ["document_ingest"]
        memory_mode = "matter_scoped"
    elif any(token in lowered for token in ["why", "how", "architecture", "are", "truth spine", "q insight", "gyro"]):
        lane = "architecture_reasoning"
        intent = "reasoning_first"
        tools = []
        memory_mode = "support_only"
    else:
        lane = "conversation"
        intent = "general_assistance"
        tools = []
        memory_mode = "bounded_recall"

    subject_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{3,}", text or "")
    current_subject = " ".join(subject_words[:6]) or "general"
    previous = str(prior_subject or "").strip().lower()
    topic_change = bool(previous and current_subject.lower() not in previous and previous not in current_subject.lower())
    continuation = bool(re.search(r"\b(also|and|then|same|that|this|continue)\b", lowered))

    return GyroOrientation(
        current_subject=current_subject,
        user_intent=intent,
        continuation=continuation,
        topic_change=topic_change,
        active_c3rp_lane=lane,
        required_memory_mode=memory_mode,
        required_tools=tools,
    )


class ThreeCRPTurnController:
    def __init__(self, silence_timeout_enabled: bool = False) -> None:
        self.buffer = TurnBuffer()
        self.metrics = TurnMetrics()
        self.silence_timeout_enabled = silence_timeout_enabled
        self._last_subject = ""

    def open_floor(self) -> None:
        self.buffer = TurnBuffer(state=TurnState.USER_FLOOR_OPEN, opened_at=time.time())

    def add_fragment(self, fragment: str) -> None:
        if self.buffer.state in {TurnState.IDLE, TurnState.RETURNING_FLOOR}:
            self.open_floor()
        self.buffer.state = TurnState.USER_DRAFTING
        self.buffer.fragments = normalize_fragments([*self.buffer.fragments, fragment])
        self.metrics.premature_model_calls_prevented += 1
        self.metrics.retrieval_calls_prevented += 1
        self.metrics.input_tokens_avoided += estimate_tokens(fragment)

    def check_completion(self, trigger: str = "") -> CompletionCheck:
        self.buffer.state = TurnState.COMPLETION_CHECK
        self.buffer.completion = q_insight_completion_check(self.buffer.canonical_prompt(), trigger)
        return self.buffer.completion

    def commit(self, trigger: str = "send") -> TurnBuffer:
        completion = self.check_completion(trigger)
        if completion.recommends_waiting and trigger not in EXPLICIT_COMMIT_TRIGGERS:
            self.buffer.state = TurnState.USER_DRAFTING
            return self.buffer

        prompt = self.buffer.canonical_prompt()
        self.buffer.state = TurnState.TURN_COMMITTED
        self.buffer.committed_prompt = prompt
        self.buffer.commit_trigger = trigger
        self.buffer.orientation = gyro_orient_committed_turn(prompt, self._last_subject)
        self._last_subject = self.buffer.orientation.current_subject

        opened_at = self.buffer.opened_at or time.time()
        self.metrics.fragments_merged += len(self.buffer.fragments)
        self.metrics.generated_tokens_avoided += max(0, len(self.buffer.fragments) - 1) * 80
        self.metrics.committed_turns += 1
        self.metrics.total_open_turn_seconds += max(0.0, time.time() - opened_at)
        if trigger == "silence_timeout":
            self.metrics.automatic_commits += 1
        else:
            self.metrics.explicit_commits += 1
        return self.buffer

    def route(self) -> None:
        self.buffer.state = TurnState.ROUTING

    def think(self) -> None:
        self.buffer.state = TurnState.THINKING

    def speak(self) -> None:
        self.buffer.state = TurnState.CLAIRE_SPEAKING

    def interrupt(self) -> None:
        self.buffer.state = TurnState.INTERRUPTED
        self.metrics.tts_interruptions += 1

    def provider_failed(self, message: str) -> None:
        self.buffer.provider_error = message
        self.buffer.state = TurnState.RETURNING_FLOOR

    def serialize(self) -> str:
        return json.dumps(
            {
                "buffer": {
                    **asdict(self.buffer),
                    "state": self.buffer.state.value,
                },
                "metrics": asdict(self.metrics),
                "silence_timeout_enabled": self.silence_timeout_enabled,
            },
            sort_keys=True,
        )

    @classmethod
    def restore(cls, payload: str) -> "ThreeCRPTurnController":
        raw = json.loads(payload)
        controller = cls(bool(raw.get("silence_timeout_enabled", False)))
        metrics = raw.get("metrics") or {}
        controller.metrics = TurnMetrics(**{k: v for k, v in metrics.items() if k in TurnMetrics.__dataclass_fields__})
        buffer = raw.get("buffer") or {}
        controller.buffer = TurnBuffer(
            state=TurnState(buffer.get("state") or TurnState.IDLE),
            fragments=normalize_fragments(buffer.get("fragments") or []),
            opened_at=buffer.get("opened_at"),
            committed_prompt=buffer.get("committed_prompt") or "",
            commit_trigger=buffer.get("commit_trigger"),
            provider_error=buffer.get("provider_error"),
        )
        return controller

