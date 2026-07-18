from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from diode_protocol import DiodeProtocol


DEFAULT_PROJECT = "CLAIRE"
DEFAULT_MILESTONE = "No recent milestone recorded in governed memory."
DEFAULT_NEXT_ACTION = "Inspect current repo/runtime state before acting."


@dataclass
class ContinuityFact:
    subject: str
    predicate: str
    value: str
    previous_value: str = ""
    status: str = "current"
    memory_id: str = ""
    lane: str = ""
    source: str = ""
    timestamp_ns: int = 0
    provenance_hash: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContinuityState:
    current: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    superseded: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    user_name: str = "Default Operator"
    assistant_role: str = (
        "Trusted technical thought partner, systems architect, project manager, "
        "and plainspoken strategic adviser."
    )
    relationship_summary: str = (
        "Preserve the high-trust working relationship developed through sustained "
        "problem-solving. Be direct, warm, honest, and loyal to the user's actual goals."
    )
    communication_style: list[str] = field(default_factory=lambda: [
        "Speak plainly and directly.",
        "Do not bury the answer under generic background.",
        "Give one major action at a time during technical work.",
        "Use exact commands, filenames, paths, and next steps.",
        "Do not repeat questions already answered.",
        "Challenge weak assumptions without becoming dismissive.",
        "Admit uncertainty instead of inventing memory.",
        "Recognize when the user is brainstorming versus trying to ship.",
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

    def evaluate(self, conversation: list[dict[str, str]], objective: str = "") -> SentimentState:
        recent = conversation[-18:] if isinstance(conversation, list) else []
        user_text = " ".join(
            str(message.get("content", ""))
            for message in recent
            if isinstance(message, dict) and message.get("role") == "user"
        ).lower()
        corrections = sum(
            len(re.findall(pattern, user_text, flags=re.I))
            for pattern in self.CORRECTION_PATTERNS
        )
        contradiction = min(1.0, corrections / 5.0)
        repetition = self._repetition(recent)
        overload = min(1.0, sum(len(str(message.get("content", ""))) for message in recent if isinstance(message, dict)) / 30000.0)
        topic_drift = self._topic_drift(recent, objective)
        weighted_drift = contradiction * 0.35 + repetition * 0.25 + overload * 0.20 + topic_drift * 0.20
        correction_drift = min(1.0, corrections / 4.0) if corrections >= 2 else 0.0
        drift = min(1.0, max(weighted_drift, correction_drift))
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
        return {token for token in re.findall(r"[a-z0-9]+", str(text or "").lower()) if len(token) > 3}

    def _repetition(self, messages: list[dict[str, str]]) -> float:
        answers = [str(message.get("content", "")) for message in messages if isinstance(message, dict) and message.get("role") == "assistant"]
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
        recent = self._tokens(" ".join(str(message.get("content", "")) for message in messages[-6:] if isinstance(message, dict)))
        return max(0.0, 1.0 - len(target & recent) / max(1, len(target)))


def build_session_recovery(recent_memories: list[dict[str, Any]], current_truth: dict[str, Any]) -> dict[str, Any]:
    current_truth = current_truth if isinstance(current_truth, dict) else {}
    repo_checkpoint = current_truth.get("repo_checkpoint") if isinstance(current_truth.get("repo_checkpoint"), dict) else {}
    company_profile = current_truth.get("company_profile") if isinstance(current_truth.get("company_profile"), dict) else {}
    usable_memories = _usable_memories(recent_memories)
    last = usable_memories[-1] if usable_memories else None
    blockers = _normalize_blockers(repo_checkpoint.get("blockers"))
    active_project = _clean_text(repo_checkpoint.get("active_project") or company_profile.get("name") or DEFAULT_PROJECT)
    last_milestone = _clean_text((last or {}).get("summary") or DEFAULT_MILESTONE)
    next_action = _clean_text(repo_checkpoint.get("next_action") or DEFAULT_NEXT_ACTION)
    return {
        "recovery_status": "ready" if repo_checkpoint or last else "minimal",
        "active_project": active_project,
        "last_milestone": last_milestone,
        "last_milestone_source": _clean_text((last or {}).get("source") or (last or {}).get("lane") or "none"),
        "next_action": next_action,
        "blockers": blockers,
        "continuity_sources": {
            "repo_checkpoint": bool(repo_checkpoint),
            "company_profile": bool(company_profile),
            "recent_memory_count": len(usable_memories),
        },
        "current_file_repo_state": _redact_mapping(repo_checkpoint) if repo_checkpoint else None,
    }


def build_cross_session_continuity_context(memories: list[dict[str, Any]] | Any) -> dict[str, Any]:
    """
    Build compact continuity state from recalled memory records.

    This is a derived view only. It does not write, edit, delete, or supersede
    authoritative ARE records. It exists to help the provider understand which
    recalled facts look current versus historical.
    """
    usable = _usable_memories(memories)
    facts = extract_continuity_facts(usable)
    state = resolve_continuity_state(facts)
    return state.to_dict()


def extract_continuity_facts(memories: list[dict[str, Any]] | Any) -> list[ContinuityFact]:
    if not isinstance(memories, list):
        return []

    facts: list[ContinuityFact] = []
    for memory in _usable_memories(memories):
        summary = _clean_text(memory.get("summary") or memory.get("raw_excerpt") or memory.get("text"))
        if not summary:
            continue
        timestamp_ns = _timestamp_ns(memory)
        base = {
            "memory_id": _clean_text(memory.get("memory_id")),
            "lane": _clean_text(memory.get("lane")),
            "source": _clean_text(memory.get("source")),
            "timestamp_ns": timestamp_ns,
            "provenance_hash": _clean_text(memory.get("provenance_hash")),
            "summary": summary,
        }
        facts.extend(_facts_from_summary(summary, base))
    return facts


def resolve_continuity_state(facts: list[ContinuityFact] | Any) -> ContinuityState:
    if not isinstance(facts, list):
        return ContinuityState()

    ordered = sorted(
        [fact for fact in facts if isinstance(fact, ContinuityFact)],
        key=lambda fact: (fact.timestamp_ns, fact.memory_id),
    )
    state = ContinuityState()
    current_by_key: dict[str, ContinuityFact] = {}

    for fact in ordered:
        key = _fact_key(fact.subject, fact.predicate)
        prior = current_by_key.get(key)
        if fact.previous_value and prior and _norm(fact.previous_value) == _norm(prior.value):
            prior.status = "superseded"
            state.superseded.append(prior.to_dict())
            fact.status = "current"
            current_by_key[key] = fact
        elif prior and _norm(prior.value) != _norm(fact.value):
            if _looks_like_correction(fact.summary):
                prior.status = "superseded"
                state.superseded.append(prior.to_dict())
                fact.status = "current"
                current_by_key[key] = fact
            else:
                fact.status = "unresolved"
                state.unresolved.append(
                    {
                        "subject": fact.subject,
                        "predicate": fact.predicate,
                        "values": [prior.to_dict(), fact.to_dict()],
                        "reason": "conflicting recalled values without explicit correction language",
                    }
                )
        else:
            fact.status = "current"
            current_by_key[key] = fact
        state.history.append(fact.to_dict())

    for key, fact in current_by_key.items():
        state.current[key] = fact.to_dict()
    return state


def current_value(memories: list[dict[str, Any]], subject: str, predicate: str) -> str:
    context = build_cross_session_continuity_context(memories)
    item = (context.get("current") or {}).get(_fact_key(subject, predicate)) or {}
    return str(item.get("value") or "")


def continuity_provider_lines(memories: list[dict[str, Any]] | Any, limit: int = 6) -> list[str]:
    context = build_cross_session_continuity_context(memories)
    current = list((context.get("current") or {}).values())
    superseded = list(context.get("superseded") or [])
    unresolved = list(context.get("unresolved") or [])
    lines: list[str] = []
    if current:
        lines.append("Cross-session continuity, derived from recalled ARE records:")
        for item in current[:limit]:
            lines.append(
                f"- CURRENT {item.get('subject')}.{item.get('predicate')} = {item.get('value')} "
                f"(memory_id={item.get('memory_id') or 'unknown'})"
            )
    if superseded:
        for item in superseded[:limit]:
            lines.append(
                f"- HISTORICAL {item.get('subject')}.{item.get('predicate')} = {item.get('value')} "
                f"(superseded by later correction)"
            )
    if unresolved:
        lines.append(f"- UNRESOLVED continuity conflicts: {len(unresolved)}")
    return lines


def render_session_capsule_bootstrap(capsule: SessionCapsule) -> str:
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


def save_session_capsule(capsule: SessionCapsule, folder: str | Path) -> dict[str, str]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = capsule.created_at.replace(":", "-")
    slug = re.sub(r"[^a-z0-9]+", "-", capsule.scope.lower()).strip("-")[:50]
    base = f"{stamp}_{slug or 'capsule'}"
    json_path = folder / f"{base}.json"
    bootstrap_path = folder / f"{base}_BOOTSTRAP.txt"
    json_path.write_text(json.dumps(asdict(capsule), indent=2), encoding="utf-8")
    bootstrap_path.write_text(render_session_capsule_bootstrap(capsule), encoding="utf-8")
    return {"json": str(json_path), "bootstrap": str(bootstrap_path)}


def auto_checkpoint_session_capsule(
    conversation: list[dict[str, str]],
    capsule: SessionCapsule,
    folder: str | Path,
) -> dict[str, Any]:
    monitor = SentimentMonitor()
    capsule.sentiment = monitor.evaluate(conversation, objective=capsule.next_safe_step or capsule.scope)
    result: dict[str, Any] = {
        "drift": capsule.sentiment.drift,
        "reset_recommended": capsule.sentiment.reset_recommended,
        "reasons": capsule.sentiment.reasons,
        "saved": None,
    }
    if capsule.sentiment.reset_recommended:
        result["saved"] = save_session_capsule(capsule, folder)
    return result


def _usable_memories(recent_memories: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    if not isinstance(recent_memories, list):
        return []
    usable = [memory for memory in recent_memories if isinstance(memory, dict) and _clean_text(memory.get("summary"))]
    return sorted(usable, key=_memory_sort_key)


def _memory_sort_key(memory: dict[str, Any]) -> tuple[int, str]:
    for key in ("timestamp_ns", "created_at_ns", "ts_ns", "received_ts_ns"):
        value = memory.get(key)
        if isinstance(value, int):
            return (value, "")
        if isinstance(value, str) and value.isdigit():
            return (int(value), "")
    for key in ("timestamp", "created_at", "updated_at"):
        value = memory.get(key)
        if value:
            return (0, str(value))
    return (0, "")


def _timestamp_ns(memory: dict[str, Any]) -> int:
    sort_key = _memory_sort_key(memory)
    return int(sort_key[0] or 0)


def _facts_from_summary(summary: str, base: dict[str, Any]) -> list[ContinuityFact]:
    text = " ".join(str(summary or "").split())
    facts: list[ContinuityFact] = []

    codename_patterns = [
        re.compile(
            r"(?:project\s+)?codename\s+(?:is|=)\s+([A-Z][A-Z0-9_-]{2,})(?:[,;]?\s+(?:replacing|replaces|instead\s+of)\s+([A-Z][A-Z0-9_-]{2,}))?",
            re.IGNORECASE,
        ),
        re.compile(
            r"([A-Z][A-Z0-9_-]{2,})\s+(?:replaces|replaced)\s+([A-Z][A-Z0-9_-]{2,}).{0,80}codename",
            re.IGNORECASE,
        ),
    ]
    for pattern in codename_patterns:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).upper()
        previous = (match.group(2) or "").upper()
        facts.append(
            ContinuityFact(
                subject="project",
                predicate="codename",
                value=value,
                previous_value=previous,
                **base,
            )
        )
        return facts

    generic = re.search(
        r"remember this:\s*([a-z][a-z0-9 _-]{2,60})\s+(?:is|=)\s+([A-Za-z0-9_.:-]{2,80})",
        text,
        re.IGNORECASE,
    )
    if generic:
        subject_predicate = "_".join(generic.group(1).lower().split())
        facts.append(
            ContinuityFact(
                subject=subject_predicate,
                predicate="value",
                value=generic.group(2),
                **base,
            )
        )
    return facts


def _fact_key(subject: str, predicate: str) -> str:
    return f"{_norm(subject)}.{_norm(predicate)}"


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _looks_like_correction(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in ["correction", "replacing", "replaces", "replaced", "instead of", "supersedes"])


def _normalize_blockers(blockers: Any) -> list[str]:
    if blockers is None:
        return []
    if isinstance(blockers, str):
        blockers = [blockers]
    if not isinstance(blockers, list):
        return [_clean_text(blockers)]
    return [_clean_text(blocker) for blocker in blockers if _clean_text(blocker)]


def _redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, str):
            clean[key] = _clean_text(item)
        elif isinstance(item, list):
            clean[key] = [_clean_text(entry) if isinstance(entry, str) else entry for entry in item]
        else:
            clean[key] = item
    return clean


def _clean_text(value: Any) -> str:
    return DiodeProtocol.redact(str(value or "").strip())
