from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass
class TemporalInstant:
    utc_timestamp: str | None
    local_timestamp: str | None
    timezone_name: str
    utc_offset: str | None
    precision: str = "unknown"
    source: str = "unknown"
    verified: bool = False
    confidence: float = 0.0
    raw_text: str = ""
    source_reference: str = ""

    @classmethod
    def from_datetime(
        cls,
        dt: datetime,
        *,
        timezone_name: str,
        precision: str = "exact",
        source: str = "system_clock",
        verified: bool = True,
        confidence: float = 1.0,
        raw_text: str = "",
        source_reference: str = "",
    ) -> "TemporalInstant":
        if dt.tzinfo is None:
            raise ValueError("TemporalInstant requires timezone-aware datetime")
        local = dt.astimezone(ZoneInfo(timezone_name))
        offset = local.strftime("%z")
        offset_text = f"{offset[:3]}:{offset[3:]}" if offset else None
        return cls(
            utc_timestamp=dt.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            local_timestamp=local.isoformat(),
            timezone_name=timezone_name,
            utc_offset=offset_text,
            precision=precision,
            source=source,
            verified=verified,
            confidence=confidence,
            raw_text=raw_text,
            source_reference=source_reference,
        )

    def to_datetime_utc(self) -> datetime | None:
        if not self.utc_timestamp:
            return None
        return parse_aware_datetime(self.utc_timestamp)


@dataclass
class TemporalInterval:
    start: TemporalInstant | None = None
    end: TemporalInstant | None = None
    duration_seconds: float | None = None
    open_start: bool = False
    open_end: bool = False
    confidence: float = 0.0
    source_reference: str = ""


@dataclass
class TemporalRelation:
    subject_event_id: str
    relation: str
    object_event_id: str
    confidence: float
    evidence_references: list[str] = field(default_factory=list)


@dataclass
class TemporalEvent:
    event_id: str
    event_type: str
    title: str
    description: str = ""
    actor_refs: list[str] = field(default_factory=list)
    occurred_at: TemporalInstant | None = None
    observed_at: TemporalInstant | None = None
    ingested_at: TemporalInstant | None = None
    effective_from: TemporalInstant | None = None
    effective_until: TemporalInstant | None = None
    due_at: TemporalInstant | None = None
    completed_at: TemporalInstant | None = None
    recurrence_rule: str = ""
    status: str = "current"
    importance: float = 0.5
    confidence: float = 0.7
    evidence_refs: list[str] = field(default_factory=list)
    truth_spine_event_ref: str = ""
    superseded_by: str = ""


@dataclass
class TemporalMemoryMetadata:
    created_at: str | None = None
    last_confirmed_at: str | None = None
    last_recalled_at: str | None = None
    last_modified_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    superseded_at: str | None = None
    superseded_by: str | None = None
    age_seconds: float | None = None
    freshness_state: str = "undated"
    decay_score: float = 1.0
    temporal_importance: float = 0.5
    expected_review_at: str | None = None


@dataclass
class BehavioralInference:
    inference_id: str
    category: str
    observation: str
    detected_pattern: str
    tentative_inference: str
    confirmed_preference: str = ""
    user_corrected_conclusion: str = ""
    evidence_references: list[str] = field(default_factory=list)
    observation_count: int = 0
    time_range_start: str | None = None
    time_range_end: str | None = None
    confidence: float = 0.0
    last_confirmed_at: str | None = None
    review_at: str | None = None
    expires_at: str | None = None
    user_status: str = "unconfirmed"
    allowed_purpose: str = "presentation_pacing_task_organization"
    disabled: bool = False
    deleted: bool = False
    external_sharing_authorized: bool = False


@dataclass
class TemporalContext:
    now_utc: str
    now_local: str
    timezone_name: str
    monotonic_time: float
    session_started_at: str | None
    session_elapsed_seconds: float
    turn_started_at: str | None
    turn_elapsed_seconds: float
    previous_turn_at: str | None
    elapsed_since_previous_turn_seconds: float | None
    active_deadlines: list[dict[str, Any]] = field(default_factory=list)
    overdue_items: list[dict[str, Any]] = field(default_factory=list)
    upcoming_items: list[dict[str, Any]] = field(default_factory=list)
    recurring_patterns: list[dict[str, Any]] = field(default_factory=list)
    temporal_uncertainties: list[dict[str, Any]] = field(default_factory=list)


class TrustedClock:
    def __init__(self, fixed_utc: datetime | None = None, monotonic_values: list[float] | None = None) -> None:
        if fixed_utc is not None and fixed_utc.tzinfo is None:
            raise ValueError("fixed_utc must be timezone-aware")
        self.fixed_utc = fixed_utc
        self._monotonic_values = list(monotonic_values or [])
        self._last_monotonic = 0.0

    def now_utc(self) -> datetime:
        if self.fixed_utc is not None:
            return self.fixed_utc.astimezone(UTC)
        return datetime.now(UTC)

    def monotonic(self) -> float:
        if self._monotonic_values:
            self._last_monotonic = float(self._monotonic_values.pop(0))
            return self._last_monotonic
        if self.fixed_utc is not None:
            self._last_monotonic += 1.0
            return self._last_monotonic
        return time.monotonic()

    def advance(self, delta: timedelta) -> None:
        if self.fixed_utc is None:
            raise RuntimeError("advance is only available for fixed clocks")
        self.fixed_utc = (self.fixed_utc + delta).astimezone(UTC)


class TemporalEngine:
    def __init__(
        self,
        path: str | Path = "data/temporal_events.jsonl",
        *,
        clock: TrustedClock | None = None,
        default_timezone: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or TrustedClock()
        self.default_timezone = default_timezone or os.environ.get("CLAIRE_USER_TIMEZONE") or "America/Los_Angeles"
        self.sessions: dict[str, dict[str, Any]] = {}
        self.turns: dict[tuple[str, str], dict[str, Any]] = {}
        self._events: dict[str, TemporalEvent] = {}
        self._relations: list[TemporalRelation] = []
        self._behavioral_inferences: dict[str, BehavioralInference] = {}
        self.behavioral_tracking_enabled = os.environ.get("CLAIRE_BEHAVIORAL_TRACKING", "1").strip() not in {"0", "false", "False"}
        self.disabled_behavior_categories: set[str] = set()
        self._load()

    def start_session(self, session_id: str, timezone_name: str | None = None) -> dict[str, Any]:
        timezone_name = self._timezone_name(timezone_name)
        now = self.clock.now_utc()
        mono = self.clock.monotonic()
        existing = self.sessions.get(session_id)
        if existing:
            existing["timezone_name"] = timezone_name
            return existing
        record = {
            "session_id": session_id,
            "timezone_name": timezone_name,
            "started_at_utc": now.isoformat().replace("+00:00", "Z"),
            "started_monotonic": mono,
            "last_turn_at_utc": None,
        }
        self.sessions[session_id] = record
        self._append_record({"kind": "session", **record})
        return record

    def start_turn(self, session_id: str, turn_id: str) -> dict[str, Any]:
        session = self.sessions.get(session_id) or self.start_session(session_id)
        now = self.clock.now_utc()
        mono = self.clock.monotonic()
        prior = session.get("last_turn_at_utc")
        record = {
            "session_id": session_id,
            "turn_id": turn_id,
            "started_at_utc": now.isoformat().replace("+00:00", "Z"),
            "started_monotonic": mono,
            "previous_turn_at": prior,
        }
        self.turns[(session_id, turn_id)] = record
        session["last_turn_at_utc"] = record["started_at_utc"]
        self._append_record({"kind": "turn_start", **record})
        return record

    def end_turn(self, session_id: str, turn_id: str) -> dict[str, Any]:
        turn = self.turns.get((session_id, turn_id)) or {}
        elapsed = max(0.0, self.clock.monotonic() - float(turn.get("started_monotonic") or 0.0))
        record = {"kind": "turn_end", "session_id": session_id, "turn_id": turn_id, "elapsed_seconds": elapsed}
        self._append_record(record)
        return record

    def get_now(self, session_id: str | None = None, turn_id: str | None = None, timezone_name: str | None = None) -> TemporalContext:
        timezone_name = self._timezone_name(timezone_name or (self.sessions.get(session_id or "") or {}).get("timezone_name"))
        now_utc = self.clock.now_utc()
        now_local = now_utc.astimezone(ZoneInfo(timezone_name))
        mono = self.clock.monotonic()
        session = self.sessions.get(session_id or "") or {}
        turn = self.turns.get((session_id or "", turn_id or "")) or {}
        session_elapsed = self._elapsed_from_monotonic_or_wall(session, "started_monotonic", "started_at_utc", mono, now_utc)
        turn_elapsed = self._elapsed_from_monotonic_or_wall(turn, "started_monotonic", "started_at_utc", mono, now_utc)
        previous_turn_at = turn.get("previous_turn_at")
        elapsed_previous = None
        if previous_turn_at:
            elapsed_previous = max(0.0, (now_utc - parse_aware_datetime(previous_turn_at)).total_seconds())
        deadlines = self.evaluate_deadlines_at(now_utc)
        return TemporalContext(
            now_utc=now_utc.isoformat().replace("+00:00", "Z"),
            now_local=now_local.isoformat(),
            timezone_name=timezone_name,
            monotonic_time=mono,
            session_started_at=session.get("started_at_utc"),
            session_elapsed_seconds=round(session_elapsed, 3),
            turn_started_at=turn.get("started_at_utc"),
            turn_elapsed_seconds=round(turn_elapsed, 3),
            previous_turn_at=previous_turn_at,
            elapsed_since_previous_turn_seconds=None if elapsed_previous is None else round(elapsed_previous, 3),
            active_deadlines=deadlines["active"],
            overdue_items=deadlines["overdue"],
            upcoming_items=deadlines["upcoming"],
            recurring_patterns=[asdict(event) for event in self._events.values() if event.recurrence_rule],
            temporal_uncertainties=[],
        )

    def resolve_expression(
        self,
        text: str,
        reference_time: datetime | str | None = None,
        timezone_name: str | None = None,
    ) -> dict[str, Any]:
        timezone_name = self._timezone_name(timezone_name)
        ref = parse_aware_datetime(reference_time) if isinstance(reference_time, str) else reference_time
        ref = (ref or self.clock.now_utc()).astimezone(ZoneInfo(timezone_name))
        lowered = str(text or "").lower()
        expressions: list[dict[str, Any]] = []
        ambiguities: list[dict[str, Any]] = []

        def add(label: str, dt: datetime, precision: str = "day", confidence: float = 0.86) -> None:
            expressions.append({
                "raw_text": label,
                "instant": asdict(TemporalInstant.from_datetime(
                    dt,
                    timezone_name=timezone_name,
                    precision=precision,
                    source="user_statement",
                    verified=False,
                    confidence=confidence,
                    raw_text=label,
                )),
            })

        base = ref.replace(hour=12, minute=0, second=0, microsecond=0)
        if re.search(r"\btoday\b", lowered):
            add("today", base)
        if re.search(r"\btonight\b", lowered):
            add("tonight", ref.replace(hour=20, minute=0, second=0, microsecond=0), "hour", 0.74)
        if re.search(r"\btomorrow\b", lowered):
            if re.search(r"\btomorrow\s+(morning|afternoon|evening)\b", lowered):
                ambiguities.append({"raw_text": "tomorrow", "reason": "part_of_day_without_exact_time"})
            add("tomorrow", base + timedelta(days=1))
        if re.search(r"\byesterday\b", lowered):
            add("yesterday", base - timedelta(days=1))
        for weekday, target in WEEKDAYS.items():
            if re.search(rf"(?<!this\s)(?<!next\s)\b{weekday}\b", lowered):
                days = (target - ref.weekday()) % 7
                dt = self._with_time_from_text(ref + timedelta(days=days), lowered)
                add(weekday, dt, "minute" if self._contains_clock_time_or_noon(lowered) else "day", 0.82)
        for match in re.finditer(r"\bin\s+(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks)\b", lowered):
            amount = int(match.group(1))
            unit = match.group(2)
            kwargs = {"minutes": amount} if unit.startswith("minute") else {"hours": amount} if unit.startswith("hour") else {"days": amount * (7 if unit.startswith("week") else 1)}
            add(match.group(0), ref + timedelta(**kwargs), "minute" if unit.startswith(("minute", "hour")) else "day", 0.9)
        for match in re.finditer(r"\b(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks)\s+ago\b", lowered):
            amount = int(match.group(1))
            unit = match.group(2)
            kwargs = {"minutes": amount} if unit.startswith("minute") else {"hours": amount} if unit.startswith("hour") else {"days": amount * (7 if unit.startswith("week") else 1)}
            add(match.group(0), ref - timedelta(**kwargs), "minute" if unit.startswith(("minute", "hour")) else "day", 0.9)
        if "last week" in lowered:
            start = (base - timedelta(days=base.weekday() + 7)).replace(hour=0)
            end = start + timedelta(days=7)
            expressions.append({
                "raw_text": "last week",
                "interval": asdict(TemporalInterval(
                    start=TemporalInstant.from_datetime(start, timezone_name=timezone_name, precision="day", source="user_statement", confidence=0.84),
                    end=TemporalInstant.from_datetime(end, timezone_name=timezone_name, precision="day", source="user_statement", confidence=0.84),
                    duration_seconds=604800,
                    confidence=0.84,
                )),
            })
        for kind, weekday in re.findall(r"\b(this|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered):
            target = WEEKDAYS[weekday]
            days = (target - ref.weekday()) % 7
            if kind == "next":
                days += 7
            dt = self._with_time_from_text(ref + timedelta(days=days), lowered)
            add(f"{kind} {weekday}", dt, "minute" if self._contains_clock_time_or_noon(lowered) else "day", 0.88)
        if any(marker in lowered for marker in ["recently", "before the call", "after the deployment", "last time"]):
            ambiguities.append({"raw_text": text, "reason": "context_link_required"})
        explicit_date = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", lowered)
        if explicit_date:
            year, month, day = map(int, explicit_date.groups())
            add(explicit_date.group(0), datetime(year, month, day, 12, tzinfo=ZoneInfo(timezone_name)), "day", 0.94)
        return {
            "status": "ambiguous" if ambiguities else "resolved" if expressions else "none",
            "expressions": expressions,
            "ambiguities": ambiguities,
            "reference_time": ref.isoformat(),
            "timezone_name": timezone_name,
        }

    def register_event(self, event: TemporalEvent | dict[str, Any]) -> TemporalEvent:
        if isinstance(event, dict):
            event = self._event_from_dict(event)
        if not event.event_id:
            event.event_id = "tevt_" + uuid.uuid4().hex[:16]
        if event.ingested_at is None:
            event.ingested_at = TemporalInstant.from_datetime(self.clock.now_utc(), timezone_name=self.default_timezone)
        self._events[event.event_id] = event
        self._append_record({"kind": "event", "event": self._event_to_dict(event)})
        return event

    def update_event(self, event_id: str, changes: dict[str, Any]) -> TemporalEvent:
        old = self._events[event_id]
        new_data = self._event_to_dict(old)
        new_data.update(changes)
        if "event_id" not in changes:
            new_data["event_id"] = "tevt_" + uuid.uuid4().hex[:16]
        new_event = self._event_from_dict(new_data)
        old.status = "superseded"
        old.superseded_by = new_event.event_id
        self._events[old.event_id] = old
        self._events[new_event.event_id] = new_event
        self._append_record({"kind": "event_superseded", "old": self._event_to_dict(old), "new": self._event_to_dict(new_event)})
        return new_event

    def relate_events(self, event_a: str, relation: str, event_b: str, confidence: float = 0.7, evidence_references: list[str] | None = None) -> TemporalRelation:
        rel = TemporalRelation(event_a, relation, event_b, confidence, evidence_references or [])
        self._relations.append(rel)
        self._append_record({"kind": "relation", "relation": asdict(rel)})
        return rel

    def build_timeline(self, query: str = "") -> list[dict[str, Any]]:
        events = list(self._events.values())
        if query:
            terms = set(re.findall(r"[a-z0-9]+", query.lower()))
            events = [event for event in events if terms & set(re.findall(r"[a-z0-9]+", f"{event.title} {event.description}".lower()))]
        events.sort(key=lambda event: self._event_sort_key(event))
        return [self._event_to_dict(event) for event in events]

    def evaluate_deadlines(self, context: TemporalContext) -> dict[str, list[dict[str, Any]]]:
        return self.evaluate_deadlines_at(parse_aware_datetime(context.now_utc))

    def evaluate_deadlines_at(self, now_utc: datetime) -> dict[str, list[dict[str, Any]]]:
        active, overdue, upcoming = [], [], []
        for event in self._events.values():
            due = event.due_at.to_datetime_utc() if event.due_at else None
            if not due or event.status in {"completed", "superseded"}:
                continue
            item = {"event_id": event.event_id, "title": event.title, "due_at": event.due_at.utc_timestamp}
            seconds = (due - now_utc).total_seconds()
            item["seconds_until"] = round(seconds, 3)
            if seconds < 0:
                overdue.append(item)
            elif seconds <= 7 * 86400:
                upcoming.append(item)
            active.append(item)
        return {"active": active, "overdue": overdue, "upcoming": upcoming}

    def evaluate_memory_freshness(self, memory_record: dict[str, Any], now: datetime | str | None = None) -> TemporalMemoryMetadata:
        now_dt = parse_aware_datetime(now) if isinstance(now, str) else (now or self.clock.now_utc())
        created = self._memory_created_at(memory_record)
        if created is None:
            return TemporalMemoryMetadata(freshness_state="undated", decay_score=0.65)
        age = max(0.0, (now_dt.astimezone(UTC) - created.astimezone(UTC)).total_seconds())
        category = self._memory_category(memory_record)
        stale_after = {"software": 30 * 86400, "role": 90 * 86400, "deadline": 0, "biographical": 20 * 365 * 86400}.get(category, 180 * 86400)
        valid_until = memory_record.get("valid_until") or memory_record.get("expires_at")
        superseded = memory_record.get("superseded_at") or memory_record.get("superseded_by")
        if superseded:
            state = "superseded"
            decay = 0.15
        elif valid_until and parse_aware_datetime(valid_until) < now_dt:
            state = "expired"
            decay = 0.0
        elif created > now_dt:
            state = "future"
            decay = 0.55
        elif age > stale_after:
            state = "stale"
            decay = 0.35
        elif age > stale_after * 0.5:
            state = "aging"
            decay = 0.65
        elif age < 7 * 86400:
            state = "recent"
            decay = 0.95
        else:
            state = "current"
            decay = 0.85
        return TemporalMemoryMetadata(
            created_at=created.isoformat().replace("+00:00", "Z"),
            valid_until=valid_until,
            superseded_at=memory_record.get("superseded_at"),
            superseded_by=memory_record.get("superseded_by"),
            age_seconds=round(age, 3),
            freshness_state=state,
            decay_score=round(decay, 3),
            temporal_importance=float(memory_record.get("importance_score") or 0.5),
        )

    def rank_temporal_relevance(self, memory_records: list[dict[str, Any]], query_time: datetime | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or self.clock.now_utc()
        ranked = []
        historical = query_time is not None
        for memory in memory_records:
            enriched = dict(memory)
            freshness = self.evaluate_memory_freshness(memory, now)
            score = float(memory.get("score") or memory.get("importance_score") or 0.5)
            if historical:
                mem_time = self._memory_created_at(memory)
                proximity = 1.0 / (1.0 + (abs((mem_time - query_time).total_seconds()) / 86400.0 if mem_time else 365.0))
                temporal_score = max(0.15, proximity)
            else:
                temporal_score = freshness.decay_score
            validity_weight = 0.35 if freshness.freshness_state in {"expired", "superseded"} else 1.0
            enriched["temporal_metadata"] = asdict(freshness)
            enriched["temporal_score"] = round(score * temporal_score * validity_weight, 4)
            ranked.append(enriched)
        return sorted(ranked, key=lambda row: float(row.get("temporal_score") or 0.0), reverse=True)

    def detect_temporal_conflicts(self, events: list[TemporalEvent | dict[str, Any]]) -> list[dict[str, Any]]:
        parsed = [self._event_from_dict(event) if isinstance(event, dict) else event for event in events]
        conflicts: list[dict[str, Any]] = []
        by_title: dict[str, list[TemporalEvent]] = {}
        for event in parsed:
            by_title.setdefault(event.title.lower(), []).append(event)
        for title, group in by_title.items():
            instants = {event.due_at.utc_timestamp for event in group if event.due_at and event.due_at.utc_timestamp}
            if len(instants) > 1:
                conflicts.append({"title": title, "reason": "conflicting_due_times", "event_ids": [event.event_id for event in group]})
        return conflicts

    def verify_temporal_claim(self, claim: str, evidence: list[TemporalEvent | dict[str, Any]]) -> dict[str, Any]:
        lowered = claim.lower()
        events = [self._event_from_dict(event) if isinstance(event, dict) else event for event in evidence]
        if "caused" in lowered or "because" in lowered:
            return {"status": "unsupported_causation", "summary": "Timing alone does not prove causation.", "confidence": 0.4}
        if "before" in lowered or "after" in lowered:
            ordered = self.build_ordering(events)
            return {"status": "verified_chronology" if ordered else "unsupported_chronology", "ordering": ordered, "confidence": 0.75 if ordered else 0.2}
        return {"status": "not_temporal", "confidence": 0.0}

    def build_ordering(self, events: list[TemporalEvent]) -> list[str]:
        known = [event for event in events if self._event_time(event)]
        known.sort(key=lambda event: self._event_time(event) or datetime.max.replace(tzinfo=UTC))
        return [event.event_id for event in known]

    def serialize_context_for_model(
        self,
        context: TemporalContext,
        resolution: dict[str, Any] | None = None,
        *,
        max_items: int = 3,
    ) -> dict[str, Any]:
        return {
            "trusted_runtime_time": {
                "current_utc": context.now_utc,
                "current_local_time": context.now_local,
                "timezone": context.timezone_name,
                "session_elapsed_seconds": context.session_elapsed_seconds,
                "turn_elapsed_seconds": context.turn_elapsed_seconds,
                "elapsed_since_previous_user_interaction_seconds": context.elapsed_since_previous_turn_seconds,
            },
            "deadlines": {
                "upcoming": context.upcoming_items[:max_items],
                "overdue": context.overdue_items[:max_items],
            },
            "resolution": resolution or {"status": "none"},
            "instruction": "Use these trusted temporal values. Do not invent current time, elapsed time, deadline status, or event order.",
        }

    def status(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "events": len(self._events),
            "relations": len(self._relations),
            "sessions": len(self.sessions),
            "behavioral_inferences": len([item for item in self._behavioral_inferences.values() if not item.deleted]),
            "behavioral_tracking": "enabled" if self.behavioral_tracking_enabled else "disabled",
            "timezone": self.default_timezone,
            "store": str(self.path),
        }

    def record_behavioral_pattern(
        self,
        *,
        category: str,
        observation: str,
        detected_pattern: str,
        tentative_inference: str,
        evidence_references: list[str],
        observation_count: int,
        time_range_start: str,
        time_range_end: str,
        confidence: float,
        allowed_purpose: str,
        review_after_days: int = 30,
    ) -> BehavioralInference | None:
        if not self.behavioral_tracking_enabled or category in self.disabled_behavior_categories:
            return None
        self._reject_punitive_or_high_impact_behavior(category, tentative_inference, allowed_purpose)
        now = self.clock.now_utc()
        inference = BehavioralInference(
            inference_id="binf_" + uuid.uuid4().hex[:16],
            category=category,
            observation=observation,
            detected_pattern=detected_pattern,
            tentative_inference=tentative_inference,
            evidence_references=list(evidence_references),
            observation_count=int(observation_count),
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            confidence=round(float(confidence), 3),
            review_at=(now + timedelta(days=review_after_days)).isoformat().replace("+00:00", "Z"),
            expires_at=(now + timedelta(days=review_after_days * 2)).isoformat().replace("+00:00", "Z"),
            allowed_purpose=allowed_purpose,
        )
        self._behavioral_inferences[inference.inference_id] = inference
        self._append_record({"kind": "behavioral_inference_created", "inference": asdict(inference)})
        return inference

    def inspect_behavioral_inferences(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        values = self._behavioral_inferences.values()
        if not include_deleted:
            values = [item for item in values if not item.deleted]
        return [asdict(item) for item in values]

    def correct_behavioral_inference(self, inference_id: str, correction: str, *, confirmed: bool = False) -> BehavioralInference:
        inference = self._behavioral_inferences[inference_id]
        inference.user_corrected_conclusion = correction
        inference.user_status = "confirmed" if confirmed else "modified"
        inference.last_confirmed_at = self.clock.now_utc().isoformat().replace("+00:00", "Z")
        if confirmed:
            inference.confirmed_preference = correction
        self._append_record({"kind": "behavioral_inference_corrected", "inference": asdict(inference)})
        return inference

    def delete_behavioral_inference(self, inference_id: str) -> None:
        inference = self._behavioral_inferences[inference_id]
        inference.deleted = True
        self._append_record({"kind": "behavioral_inference_deleted", "inference_id": inference_id})

    def disable_behavior_category(self, category: str) -> None:
        self.disabled_behavior_categories.add(category)
        self._append_record({"kind": "behavior_category_disabled", "category": category})

    def export_behavioral_inferences(self) -> dict[str, Any]:
        return {
            "behavioral_tracking": "enabled" if self.behavioral_tracking_enabled else "disabled",
            "inferences": self.inspect_behavioral_inferences(),
            "rules": {
                "authority_reduction_allowed": False,
                "high_impact_decision_allowed": False,
                "external_sharing_default": False,
                "mental_health_or_character_labels_allowed": False,
            },
        }

    def authorize_behavioral_use(self, inference_id: str, purpose: str, *, high_impact: bool = False, external: bool = False) -> dict[str, Any]:
        inference = self._behavioral_inferences.get(inference_id)
        if not inference or inference.deleted or inference.disabled:
            return {"allowed": False, "reason": "inference_unavailable"}
        if high_impact:
            return {"allowed": False, "reason": "behavioral_inference_cannot_drive_high_impact_decisions"}
        if external and not inference.external_sharing_authorized:
            return {"allowed": False, "reason": "external_sharing_not_authorized"}
        allowed = purpose == inference.allowed_purpose or purpose in {"presentation", "pacing", "workflow_suggestion", "task_organization"}
        return {"allowed": allowed, "reason": "allowed_user_visible_low_impact_adaptation" if allowed else "purpose_not_authorized"}

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                kind = row.get("kind")
                if kind == "session":
                    row["started_monotonic"] = None
                    self.sessions[row["session_id"]] = row
                elif kind == "turn_start":
                    row["started_monotonic"] = None
                    self.turns[(row["session_id"], row["turn_id"])] = row
                elif kind in {"event", "event_superseded"}:
                    for key in ("event", "old", "new"):
                        if row.get(key):
                            event = self._event_from_dict(row[key])
                            self._events[event.event_id] = event
                elif kind == "relation":
                    self._relations.append(TemporalRelation(**row["relation"]))
                elif kind in {"behavioral_inference_created", "behavioral_inference_corrected"}:
                    item = BehavioralInference(**row["inference"])
                    self._behavioral_inferences[item.inference_id] = item
                elif kind == "behavioral_inference_deleted":
                    inference_id = str(row.get("inference_id") or "")
                    if inference_id in self._behavioral_inferences:
                        self._behavioral_inferences[inference_id].deleted = True
                elif kind == "behavior_category_disabled":
                    self.disabled_behavior_categories.add(str(row.get("category") or ""))
            except Exception:
                continue

    def _append_record(self, record: dict[str, Any]) -> None:
        record = {"recorded_at_utc": self.clock.now_utc().isoformat().replace("+00:00", "Z"), **record}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=self._json_default) + "\n")

    def _timezone_name(self, timezone_name: str | None) -> str:
        name = str(timezone_name or self.default_timezone or "UTC")
        try:
            ZoneInfo(name)
            return name
        except Exception:
            return "UTC"

    def _elapsed_from_monotonic_or_wall(self, record: dict[str, Any], mono_key: str, wall_key: str, mono: float, now_utc: datetime) -> float:
        if record.get(mono_key) is not None:
            return max(0.0, mono - float(record.get(mono_key) or 0.0))
        if record.get(wall_key):
            return max(0.0, (now_utc - parse_aware_datetime(record[wall_key])).total_seconds())
        return 0.0

    def _with_time_from_text(self, dt: datetime, text: str) -> datetime:
        if "noon" in text:
            return dt.replace(hour=12, minute=0, second=0, microsecond=0)
        if "midnight" in text:
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        match = re.search(r"\b(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
        if not match:
            return dt.replace(hour=12, minute=0, second=0, microsecond=0)
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = match.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _contains_clock_time(self, text: str) -> bool:
        return bool(re.search(r"\b(?:at\s*)?\d{1,2}(?::\d{2})?\s*(am|pm)\b", text))

    def _contains_clock_time_or_noon(self, text: str) -> bool:
        return bool(self._contains_clock_time(text) or re.search(r"\b(noon|midnight|at\s+\d{1,2}(?::\d{2})?)\b", text))

    def _memory_created_at(self, memory: dict[str, Any]) -> datetime | None:
        for key in ("created_at", "timestamp_utc", "ingested_at", "last_confirmed_at"):
            if memory.get(key):
                return parse_aware_datetime(memory[key])
        if memory.get("timestamp_ns"):
            return datetime.fromtimestamp(int(memory["timestamp_ns"]) / 1_000_000_000, UTC)
        return None

    def _memory_category(self, memory: dict[str, Any]) -> str:
        text = " ".join(str(memory.get(key) or "") for key in ("lane", "event_type", "summary", "raw_excerpt", "source")).lower()
        if any(word in text for word in ["version", "config", "configuration", "port", "commit", "model"]):
            return "software"
        if any(word in text for word in ["birthday", "birth date", "born"]):
            return "biographical"
        if any(word in text for word in ["deadline", "due", "appointment", "meeting", "call"]):
            return "deadline"
        if any(word in text for word in ["role", "ceo", "attorney", "employee"]):
            return "role"
        return "general"

    def _event_sort_key(self, event: TemporalEvent) -> datetime:
        return self._event_time(event) or datetime.max.replace(tzinfo=UTC)

    def _event_time(self, event: TemporalEvent) -> datetime | None:
        for instant in (event.occurred_at, event.due_at, event.effective_from, event.observed_at, event.ingested_at):
            if instant:
                dt = instant.to_datetime_utc()
                if dt:
                    return dt
        return None

    def _event_to_dict(self, event: TemporalEvent) -> dict[str, Any]:
        return asdict(event)

    def _event_from_dict(self, data: dict[str, Any]) -> TemporalEvent:
        clean = dict(data)
        for key in ("occurred_at", "observed_at", "ingested_at", "effective_from", "effective_until", "due_at", "completed_at"):
            if isinstance(clean.get(key), dict):
                clean[key] = TemporalInstant(**clean[key])
        return TemporalEvent(**{k: v for k, v in clean.items() if k in TemporalEvent.__dataclass_fields__})

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        raise TypeError(str(type(value)))

    def _reject_punitive_or_high_impact_behavior(self, category: str, inference: str, purpose: str) -> None:
        text = f"{category} {inference} {purpose}".lower()
        blocked_terms = {
            "unreliable",
            "unstable",
            "incapable",
            "dishonest",
            "dangerous",
            "mental",
            "diagnosis",
            "competence",
            "medical",
            "employment",
            "credit",
            "housing",
            "insurance",
            "law-enforcement",
            "essential services",
        }
        if any(term in text for term in blocked_terms):
            raise ValueError("punitive, diagnostic, or high-impact behavioral inference is not allowed")


def parse_aware_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime is not allowed")
        return value.astimezone(UTC)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed")
    return dt.astimezone(UTC)
