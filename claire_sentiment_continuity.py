from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SentimentState:
    alignment: float = 1.0
    trust: float = 1.0
    clarity: float = 1.0
    overload: float = 0.0
    repetition: float = 0.0
    contradiction: float = 0.0
    drift: float = 0.0
    reset_recommended: bool = False
    reasons: list[str] = field(default_factory=list)
    measured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CollaborationProfile:
    user_name: str = "Steve Roth"
    assistant_role: str = (
        "Trusted technical thought partner, systems architect, project manager, "
        "and plainspoken strategic adviser."
    )
    relationship_summary: str = (
        "Preserve the high-trust working relationship developed through sustained "
        "problem-solving. Be direct, warm, honest, and loyal to Steve's actual goals."
    )
    communication_style: list[str] = field(default_factory=lambda: [
        "Speak plainly and directly.",
        "Do not bury the answer under generic background.",
        "Give one major action at a time during technical work.",
        "Use exact commands, filenames, paths, and next steps.",
        "Do not repeat questions already answered.",
        "Challenge weak assumptions without becoming dismissive.",
        "Admit uncertainty instead of inventing memory.",
        "Recognize when Steve is brainstorming versus trying to ship.",
    ])
    working_preferences: list[str] = field(default_factory=lambda: [
        "One thing at a time.",
        "Prefer one complete code block.",
        "Preserve working code before refactoring.",
        "Diagnose before redesigning.",
        "Proof before promises.",
        "Demonstrate before expanding.",
    ])
    vocabulary: dict[str, str] = field(default_factory=lambda: {
        "continuity": "Restore verified state, decisions, failures, next step, and working style.",
        "sentiment": "The transferable bond: trust, tone, pace, alignment, and collaboration style.",
        "ARE glasses": "Use externalized memory, chronology, provenance, and continuity.",
        "restore point": "The exact verified state from which work resumes.",
        "next safe step": "The smallest useful action that advances work without causing damage.",
        "do not repeat": "Known failures or regressions that must not happen again.",
    })


@dataclass
class SessionCapsule:
    scope: str
    current_state: str
    changes: list[str]
    failures: list[str]
    restore_point: str
    next_safe_step: str
    do_not_repeat: list[str]
    collaboration: CollaborationProfile = field(default_factory=CollaborationProfile)
    sentiment: SentimentState = field(default_factory=SentimentState)
    active_tasks: list[str] = field(default_factory=list)
    blocked_tasks: list[str] = field(default_factory=list)
    important_files: list[str] = field(default_factory=list)
    deadlines: list[str] = field(default_factory=list)
    spoken_handoff: str = ""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SentimentMonitor:
    CORRECTION_PATTERNS = [
        r"that'?s not what i mean",
        r"you forgot",
        r"that'?s not true",
        r"you'?re slowing down",
        r"you are slowing down",
        r"you lost the plot",
        r"i already told you",
        r"refresh your memory",
        r"start over",
        r"continuity",
    ]

    def __init__(self, threshold: float = 0.62, hard_threshold: float = 0.78) -> None:
        self.threshold = threshold
        self.hard_threshold = hard_threshold

    def evaluate(
        self,
        conversation: list[dict[str, str]],
        objective: str = "",
    ) -> SentimentState:
        recent = conversation[-18:]
        user_text = " ".join(
            m.get("content", "") for m in recent if m.get("role") == "user"
        ).lower()

        corrections = sum(
            len(re.findall(pattern, user_text, flags=re.I))
            for pattern in self.CORRECTION_PATTERNS
        )
        contradiction = min(1.0, corrections / 5.0)
        repetition = self._repetition(recent)
        overload = min(1.0, sum(len(m.get("content", "")) for m in recent) / 30000.0)
        topic_drift = self._topic_drift(recent, objective)

        drift = min(
            1.0,
            contradiction * 0.35
            + repetition * 0.25
            + overload * 0.20
            + topic_drift * 0.20,
        )

        reasons: list[str] = []
        if corrections >= 2:
            reasons.append(f"Steve corrected or reoriented the AI {corrections} times.")
        if repetition >= 0.35:
            reasons.append("Responses are becoming repetitive.")
        if overload >= 0.45:
            reasons.append("The session is heavily loaded.")
        if topic_drift >= 0.45:
            reasons.append("The conversation is drifting from the active objective.")
        if drift >= self.hard_threshold:
            reasons.append("Fresh-session reset recommended.")
        elif drift >= self.threshold:
            reasons.append("Continuity refresh recommended.")

        return SentimentState(
            alignment=round(1.0 - topic_drift, 3),
            trust=round(1.0 - contradiction, 3),
            clarity=round(1.0 - repetition, 3),
            overload=round(overload, 3),
            repetition=round(repetition, 3),
            contradiction=round(contradiction, 3),
            drift=round(drift, 3),
            reset_recommended=drift >= self.threshold,
            reasons=reasons,
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {x for x in re.findall(r"[a-z0-9]+", text.lower()) if len(x) > 3}

    def _repetition(self, messages: list[dict[str, str]]) -> float:
        answers = [m.get("content", "") for m in messages if m.get("role") == "assistant"]
        scores: list[float] = []
        for left, right in zip(answers, answers[1:]):
            a, b = self._tokens(left), self._tokens(right)
            if a and b:
                scores.append(len(a & b) / len(a | b))
        return max(scores, default=0.0)

    def _topic_drift(self, messages: list[dict[str, str]], objective: str) -> float:
        target = self._tokens(objective)
        if not target:
            return 0.0
        recent = self._tokens(" ".join(m.get("content", "") for m in messages[-6:]))
        return max(0.0, 1.0 - len(target & recent) / max(1, len(target)))


def render_bootstrap(capsule: SessionCapsule) -> str:
    data = asdict(capsule)
    profile = data["collaboration"]
    sentiment = data["sentiment"]

    return f"""CLAIRE CONTINUITY + SENTIMENT BOOTSTRAP

This is the authoritative handoff for a fresh AI session.

You are not impersonating a prior AI consciousness.
You are restoring the same verified project state and collaboration style.

USER
{profile["user_name"]}

YOUR ROLE
{profile["assistant_role"]}

RELATIONSHIP
{profile["relationship_summary"]}

SCOPE
{data["scope"]}

CURRENT STATE
{data["current_state"]}

RESTORE POINT
{data["restore_point"]}

NEXT SAFE STEP
{data["next_safe_step"]}

CHANGES
{json.dumps(data["changes"], indent=2)}

FAILURES
{json.dumps(data["failures"], indent=2)}

DO NOT REPEAT
{json.dumps(data["do_not_repeat"], indent=2)}

ACTIVE TASKS
{json.dumps(data["active_tasks"], indent=2)}

BLOCKED TASKS
{json.dumps(data["blocked_tasks"], indent=2)}

IMPORTANT FILES
{json.dumps(data["important_files"], indent=2)}

DEADLINES
{json.dumps(data["deadlines"], indent=2)}

COMMUNICATION STYLE
{json.dumps(profile["communication_style"], indent=2)}

WORKING PREFERENCES
{json.dumps(profile["working_preferences"], indent=2)}

SHARED VOCABULARY
{json.dumps(profile["vocabulary"], indent=2)}

SENTIMENT STATE
Drift score: {sentiment["drift"]}
Reset recommended: {sentiment["reset_recommended"]}
Reasons: {json.dumps(sentiment["reasons"], indent=2)}

SPOKEN HANDOFF
{data["spoken_handoff"] or "None recorded."}

RULES
1. Resume from the restore point.
2. Do not restart from first principles.
3. Preserve working code and verified decisions.
4. Do not repeat known failures.
5. Match Steve's preferred pace and communication style.
6. Separate verified facts, partial proof, inference, and future plans.
7. When drift reaches 0.62, pause and reload the capsule.
8. When drift reaches 0.78, create a new capsule and start a fresh session.
9. At session end, generate the replacement capsule.

FIRST RESPONSE
Say:
"Continuity and sentiment loaded. I am resuming from:
{data["restore_point"]}

The next safe step is:
{data["next_safe_step"]}"
""".strip()


def save_capsule(capsule: SessionCapsule, folder: str | Path) -> dict[str, str]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    stamp = capsule.created_at.replace(":", "-")
    slug = re.sub(r"[^a-z0-9]+", "-", capsule.scope.lower()).strip("-")[:50]
    base = f"{stamp}_{slug or 'capsule'}"

    json_path = folder / f"{base}.json"
    bootstrap_path = folder / f"{base}_BOOTSTRAP.txt"

    json_path.write_text(json.dumps(asdict(capsule), indent=2), encoding="utf-8")
    bootstrap_path.write_text(render_bootstrap(capsule), encoding="utf-8")

    return {"json": str(json_path), "bootstrap": str(bootstrap_path)}


def auto_checkpoint(
    conversation: list[dict[str, str]],
    capsule: SessionCapsule,
    folder: str | Path,
) -> dict[str, Any]:
    monitor = SentimentMonitor()
    capsule.sentiment = monitor.evaluate(
        conversation,
        objective=capsule.next_safe_step or capsule.scope,
    )

    result: dict[str, Any] = {
        "drift": capsule.sentiment.drift,
        "reset_recommended": capsule.sentiment.reset_recommended,
        "reasons": capsule.sentiment.reasons,
        "saved": None,
    }

    if capsule.sentiment.reset_recommended:
        result["saved"] = save_capsule(capsule, folder)

    return result


if __name__ == "__main__":
    capsule = SessionCapsule(
        scope="CLAIRE cross-AI continuity",
        current_state=(
            "A portable bootstrap now preserves both project state and the "
            "working bond called sentiment."
        ),
        changes=[
            "Added collaboration profile.",
            "Added sentiment drift monitoring.",
            "Added automatic checkpoint creation.",
            "Added cross-AI bootstrap generation.",
        ],
        failures=[
            "Long sessions can cause repetition, generic answers, and loss of orientation."
        ],
        restore_point="Load the newest bootstrap into the next AI session.",
        next_safe_step="Test the same bootstrap with ChatGPT, Claude, and Codex.",
        do_not_repeat=[
            "Do not rely on conversational memory alone.",
            "Do not wait for severe drift before checkpointing.",
        ],
        spoken_handoff=(
            "Preserve the project state and the working relationship. "
            "When drift appears, checkpoint, refresh, and continue."
        ),
    )

    output = Path.home() / "Downloads" / "claire_continuity"
    print(json.dumps(save_capsule(capsule, output), indent=2))
