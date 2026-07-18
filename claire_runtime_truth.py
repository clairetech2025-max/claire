from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from diode_protocol import DiodeProtocol


SCHEMA_VERSION = "truth-spine.v1"
TURN_SCHEMA_VERSION = "truth-spine.turn.v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _redacted(value: Any) -> Any:
    return json.loads(DiodeProtocol.redact(json.dumps(value, ensure_ascii=False, default=str)))


@dataclass
class TrailLinkProof:
    signer_id: str
    signature: str
    verification_status: str
    algorithm: str = "HMAC-SHA256"
    nonce: str = ""
    payload_digest: str = ""


class TrailLinkSigner:
    def __init__(self, key: bytes | str | None = None, signer_id: str = "claire-runtime") -> None:
        raw = key if key is not None else os.environ.get("CLAIRE_TRAILLINK_HMAC_KEY", "claire-local-runtime-key")
        self.key = raw if isinstance(raw, bytes) else str(raw).encode("utf-8")
        self.signer_id = signer_id
        self._seen_nonces: set[str] = set()

    def sign(self, payload_digest: str, *, nonce: str | None = None) -> TrailLinkProof:
        nonce = nonce or uuid.uuid4().hex
        message = f"{payload_digest}:{nonce}".encode("utf-8")
        signature = hmac.new(self.key, message, hashlib.sha256).hexdigest()
        self._seen_nonces.add(nonce)
        return TrailLinkProof(
            signer_id=self.signer_id,
            signature=signature,
            verification_status="verified",
            nonce=nonce,
            payload_digest=payload_digest,
        )

    def verify(self, proof: TrailLinkProof | dict[str, Any], payload_digest: str) -> bool:
        data = asdict(proof) if isinstance(proof, TrailLinkProof) else dict(proof or {})
        nonce = str(data.get("nonce") or "")
        signature = str(data.get("signature") or "")
        expected = hmac.new(self.key, f"{payload_digest}:{nonce}".encode("utf-8"), hashlib.sha256).hexdigest()
        return bool(nonce and hmac.compare_digest(signature, expected))


@dataclass
class RuntimeTruthEvent:
    event_type: str
    session_id: str
    turn_id: str
    actor: dict[str, Any]
    lane: str = ""
    floor_state: str = ""
    input_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    decision: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    parent_event_ids: list[str] = field(default_factory=list)
    status: str = "committed"
    event_id: str = field(default_factory=lambda: "evt_" + uuid.uuid4().hex[:16])
    timestamp_utc: str = field(default_factory=utc_now)


class RuntimeTruthSpine:
    def __init__(
        self,
        path: str | Path = "data/runtime_truth_spine.jsonl",
        degraded_path: str | Path = "data/runtime_truth_spine_degraded.jsonl",
        signer: TrailLinkSigner | None = None,
    ) -> None:
        self.path = Path(path)
        self.degraded_path = Path(degraded_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.degraded_path.parent.mkdir(parents=True, exist_ok=True)
        self.signer = signer or TrailLinkSigner()

    @classmethod
    def from_env(cls) -> "RuntimeTruthSpine":
        return cls(os.environ.get("CLAIRE_RUNTIME_TRUTH_SPINE", "data/runtime_truth_spine.jsonl"))

    def append(self, event: RuntimeTruthEvent, *, fail_closed: bool = False) -> dict[str, Any]:
        event = RuntimeTruthEvent(**asdict(event))
        safe_event = _redacted(asdict(event))
        try:
            return self._append_safe_event(safe_event)
        except Exception as exc:
            if "duplicate Truth Spine event_id" in str(exc):
                raise
            if fail_closed:
                raise
            degraded = dict(safe_event)
            degraded["status"] = "degraded"
            degraded["schema_version"] = SCHEMA_VERSION
            self._append_degraded(degraded)
            return degraded

    def _append_safe_event(self, event: dict[str, Any]) -> dict[str, Any]:
        with self.path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                previous_hash, sequence, event_ids = self._state_from_open_file(fh)
                if event["event_id"] in event_ids:
                    raise ValueError("duplicate Truth Spine event_id")
                payload_hash = sha256_value(event.get("payload") or {})
                unsigned = {
                    "schema_version": SCHEMA_VERSION,
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "timestamp_utc": event["timestamp_utc"],
                    "sequence": sequence,
                    "session_id": event["session_id"],
                    "turn_id": event["turn_id"],
                    "parent_event_ids": event.get("parent_event_ids") or [],
                    "actor": event.get("actor") or {},
                    "lane": event.get("lane") or "",
                    "floor_state": event.get("floor_state") or "",
                    "input_refs": event.get("input_refs") or [],
                    "evidence_refs": event.get("evidence_refs") or [],
                    "decision": event.get("decision") or {},
                    "result_summary": event.get("result_summary") or {},
                    "payload_hash": payload_hash,
                    "previous_hash": previous_hash,
                    "status": event.get("status") or "committed",
                }
                digest = sha256_value(unsigned)
                proof = self.signer.sign(digest)
                with_signature = {**unsigned, "trail_link": asdict(proof)}
                record_hash = sha256_value(with_signature)
                envelope = {
                    **with_signature,
                    "record_hash": record_hash,
                    "payload": event.get("payload") or {},
                }
                fh.seek(0, os.SEEK_END)
                fh.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
                return envelope
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _append_degraded(self, record: dict[str, Any]) -> None:
        with self.degraded_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _state_from_open_file(self, fh) -> tuple[str, int, set[str]]:
        fh.seek(0)
        previous_hash = "0"
        sequence = 1
        event_ids: set[str] = set()
        for line in fh:
            if not line.strip():
                continue
            record = json.loads(line)
            event_ids.add(str(record.get("event_id") or ""))
            previous_hash = str(record.get("record_hash") or "")
            sequence = int(record.get("sequence") or 0) + 1
        return previous_hash or "0", sequence, event_ids

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rows.append(json.loads(line))
        return rows

    def verify(self, *, session_id: str | None = None, turn_id: str | None = None) -> dict[str, Any]:
        previous = "0"
        count = 0
        seen: set[str] = set()
        selected = 0
        for record in self.events():
            if record.get("event_id") in seen:
                return {"valid": False, "reason": "duplicate_event_id", "index": count}
            seen.add(str(record.get("event_id") or ""))
            if record.get("sequence") != count + 1:
                return {"valid": False, "reason": "sequence_mismatch", "index": count}
            if record.get("previous_hash") != previous:
                return {"valid": False, "reason": "previous_hash_mismatch", "index": count}
            unsigned = {
                key: record.get(key)
                for key in [
                    "schema_version",
                    "event_id",
                    "event_type",
                    "timestamp_utc",
                    "sequence",
                    "session_id",
                    "turn_id",
                    "parent_event_ids",
                    "actor",
                    "lane",
                    "floor_state",
                    "input_refs",
                    "evidence_refs",
                    "decision",
                    "result_summary",
                    "payload_hash",
                    "previous_hash",
                    "status",
                ]
            }
            if record.get("payload_hash") != sha256_value(record.get("payload") or {}):
                return {"valid": False, "reason": "payload_hash_mismatch", "index": count}
            digest = sha256_value(unsigned)
            trail_link = record.get("trail_link") or {}
            if not self.signer.verify(trail_link, digest):
                return {"valid": False, "reason": "signature_mismatch", "index": count}
            expected_record_hash = sha256_value({**unsigned, "trail_link": trail_link})
            if record.get("record_hash") != expected_record_hash:
                return {"valid": False, "reason": "record_hash_mismatch", "index": count}
            if (session_id is None or record.get("session_id") == session_id) and (turn_id is None or record.get("turn_id") == turn_id):
                selected += 1
            previous = str(record.get("record_hash") or "")
            count += 1
        return {"valid": True, "records": count, "selected_records": selected, "chain_head": previous}

    def seal_turn(self, *, session_id: str, turn_id: str, input_text: str, final_output: str) -> dict[str, Any]:
        turn_events = [row for row in self.events() if row.get("session_id") == session_id and row.get("turn_id") == turn_id]
        if not turn_events:
            raise ValueError("cannot seal turn without Truth Spine events")
        capsule_unsigned = {
            "schema_version": TURN_SCHEMA_VERSION,
            "session_id": session_id,
            "turn_id": turn_id,
            "first_event_id": turn_events[0].get("event_id"),
            "last_event_id": turn_events[-1].get("event_id"),
            "first_record_hash": turn_events[0].get("record_hash"),
            "last_record_hash": turn_events[-1].get("record_hash"),
            "input_hash": hashlib.sha256(str(input_text or "").encode("utf-8")).hexdigest(),
            "final_output_hash": hashlib.sha256(str(final_output or "").encode("utf-8")).hexdigest(),
            "orientation_event_id": self._last_event_id(turn_events, "gyro.orientation"),
            "authorization_event_ids": [row["event_id"] for row in turn_events if str(row.get("event_type") or "").startswith("3crp.")],
            "are_record_refs": self._collect_refs(turn_events, "are_record_refs"),
            "evidence_refs": self._collect_refs(turn_events, "evidence_refs"),
            "tool_event_ids": [row["event_id"] for row in turn_events if str(row.get("event_type") or "").startswith("tool.")],
            "model_event_ids": [row["event_id"] for row in turn_events if str(row.get("event_type") or "").startswith("model.")],
            "event_count": len(turn_events),
            "chain_head": turn_events[-1].get("record_hash"),
            "sealed_at_utc": utc_now(),
        }
        digest = sha256_value(capsule_unsigned)
        proof = self.signer.sign(digest)
        return {**capsule_unsigned, "trail_link_signature": proof.signature, "trail_link": asdict(proof)}

    def verify_turn_capsule(self, capsule: dict[str, Any]) -> dict[str, Any]:
        turn_events = [row for row in self.events() if row.get("session_id") == capsule.get("session_id") and row.get("turn_id") == capsule.get("turn_id")]
        if len(turn_events) != int(capsule.get("event_count") or -1):
            return {"valid": False, "reason": "event_count_mismatch"}
        checks = {
            "first_event_id": turn_events[0].get("event_id"),
            "last_event_id": turn_events[-1].get("event_id"),
            "first_record_hash": turn_events[0].get("record_hash"),
            "last_record_hash": turn_events[-1].get("record_hash"),
            "chain_head": turn_events[-1].get("record_hash"),
        }
        for key, expected in checks.items():
            if capsule.get(key) != expected:
                return {"valid": False, "reason": f"{key}_mismatch"}
        return {"valid": True, "event_count": len(turn_events)}

    def _last_event_id(self, events: list[dict[str, Any]], event_type: str) -> str:
        for row in reversed(events):
            if row.get("event_type") == event_type:
                return str(row.get("event_id") or "")
        return ""

    def _collect_refs(self, events: list[dict[str, Any]], key: str) -> list[str]:
        refs: set[str] = set()
        for row in events:
            payload = row.get("payload") or {}
            for value in payload.get(key) or row.get(key) or []:
                refs.add(str(value))
        return sorted(refs)


class Runtime3CRPAuthority:
    def admit_input(self, *, origin: dict[str, Any], floor_state: str, fragment: bool) -> dict[str, Any]:
        return {"allowed": True, "action": "hold" if fragment else "accept", "origin": origin, "floor_state": floor_state}

    def authorize_recall(self, *, lane: str, allowed_lanes: list[str]) -> dict[str, Any]:
        return {"allowed": True, "recall_mode": "SUPPORT", "lane": lane, "allowed_lanes": allowed_lanes}

    def enforce_orientation(self, orientation: dict[str, Any]) -> dict[str, Any]:
        return {"allowed": bool(orientation.get("stable", True)), "orientation": orientation}

    def authorize_model(self, *, lane: str, orientation_event_id: str, authorization_event_id: str) -> dict[str, Any]:
        return {"allowed": True, "provider": "configured", "lane": lane, "orientation_event_id": orientation_event_id, "authorization_event_id": authorization_event_id}

    def authorize_memory_write(self, *, lane: str, eligible: bool) -> dict[str, Any]:
        return {"allowed": bool(eligible), "lane": lane}

    def authorize_output(self, *, lane: str, final_answer_hash: str, provenance_ready: bool) -> dict[str, Any]:
        return {"allowed": bool(provenance_ready), "lane": lane, "final_answer_hash": final_answer_hash}

    def authorize_temporal_operation(self, *, operation: str, temporal_resolution: dict[str, Any], high_impact: bool = False) -> dict[str, Any]:
        ambiguous = str((temporal_resolution or {}).get("status") or "") == "ambiguous"
        allowed = not (high_impact and ambiguous)
        return {
            "allowed": allowed,
            "operation": operation,
            "temporal_status": (temporal_resolution or {}).get("status", "none"),
            "reason": "ambiguous_time_blocks_high_impact_action" if not allowed else "temporal_context_available",
        }

    def authorize_behavioral_inference_use(self, *, purpose: str, high_impact: bool = False, external: bool = False) -> dict[str, Any]:
        if high_impact:
            return {"allowed": False, "reason": "behavioral_patterns_cannot_drive_high_impact_decisions"}
        if external:
            return {"allowed": False, "reason": "external_behavioral_disclosure_requires_explicit_user_authorization"}
        return {"allowed": True, "reason": "low_impact_user_visible_adaptation_only", "purpose": purpose}


def recognition_packet_from_are(
    *,
    current_input_ref: str,
    query: str,
    memories: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    temporal_context: dict[str, Any] | None = None,
    temporal_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lowered = str(query or "").lower()
    refs = [str(item.get("memory_id") or item.get("provenance_hash") or item.get("truth_hash") or "") for item in memories]
    refs = [ref for ref in refs if ref]
    continuation_score = 0.0
    if any(marker in lowered for marker in ["also", "that", "this", "continue", "same thing", "where were we"]):
        continuation_score += 0.45
    if refs:
        continuation_score += 0.35
    correction = any(marker in lowered for marker in ["correction", "not that", "that's wrong", "that is wrong", "fix what i said"])
    word_count = len(str(query or "").split())
    unresolved = []
    if word_count <= 12 or re.match(r"^\s*(that|this|it|those|them)\b", lowered):
        unresolved = [word for word in ["that", "this", "it", "those", "them"] if f" {word} " in f" {lowered} "]
    if re.search(r"\bthis\s+is\s+[a-z0-9]", lowered):
        unresolved = [word for word in unresolved if word != "this"]
    temporal_resolved = (temporal_resolution or {}).get("status") == "resolved"
    if temporal_resolved and any(marker in lowered for marker in ["moved it", "changed it", "rescheduled it", "they moved it"]):
        unresolved = [word for word in unresolved if word != "it"]
    stale_refs = [
        ref for ref, item in zip(refs, memories)
        if ((item.get("temporal_metadata") or {}).get("freshness_state") in {"stale", "expired", "superseded"})
    ]
    elapsed_previous = None
    if temporal_context:
        elapsed_previous = temporal_context.get("elapsed_since_previous_turn_seconds")
        if elapsed_previous and elapsed_previous > 86400:
            continuation_score += 0.12
    return {
        "current_input_ref": current_input_ref,
        "are_record_refs": refs,
        "continuation_score": round(min(1.0, continuation_score), 3),
        "topic": " ".join(str(query or "").split()[:8]),
        "correction_detected": correction,
        "contradiction_refs": [],
        "unresolved_references": unresolved,
        "rejected_memory_refs": [item.get("memory_id") for item in rejected if item.get("memory_id")],
        "temporal": {
            "elapsed_since_previous_turn_seconds": elapsed_previous,
            "stale_record_refs": stale_refs,
            "resolution_status": (temporal_resolution or {}).get("status", "none"),
            "state_may_have_changed": bool(stale_refs),
            "temporal_confidence": 0.72 if (temporal_resolution or {}).get("status") != "ambiguous" else 0.42,
        },
        "recommended_turn_action": "hold_floor" if unresolved and not correction else "proceed",
    }


def q_insight_packet(
    *,
    query: str,
    recognition: dict[str, Any],
    lane: str,
    temporal_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lowered = str(query or "").lower()
    fragment = bool(recognition.get("unresolved_references")) or any(marker in lowered for marker in ["hold on", "one more thing", "wait"])
    temporal_resolution = temporal_resolution or {"status": "none", "expressions": [], "ambiguities": []}
    has_date = bool(temporal_resolution.get("expressions"))
    temporal_ambiguous = str(temporal_resolution.get("status")) == "ambiguous"
    deadline_request = any(marker in lowered for marker in ["deadline", "due", "tomorrow", "friday", "monday", "remind", "schedule", "appointment", "meeting", "call"])
    return {
        "finished": not fragment,
        "fragment": fragment,
        "intent": "question" if "?" in str(query or "") or any(x in lowered for x in ["what", "why", "how", "who"]) else "instruction",
        "ambiguity": "temporal" if temporal_ambiguous else "unresolved_reference" if recognition.get("unresolved_references") else "none",
        "requested_action": "answer",
        "sensitivity": "high" if lane in {"LEGAL_CASE", "TRADING_STATION"} else "normal",
        "evidence_needs": "strict" if lane in {"LEGAL_CASE", "TRADING_STATION"} else "support",
        "clarification_required": bool((fragment and not recognition.get("are_record_refs")) or (temporal_ambiguous and deadline_request)),
        "confidence": 0.42 if temporal_ambiguous else 0.72 if not fragment else 0.48,
        "candidate_lane": lane,
        "temporal": {
            "has_explicit_or_relative_time": has_date,
            "deadline_or_schedule_language": deadline_request,
            "resolution_status": temporal_resolution.get("status"),
            "ambiguities": temporal_resolution.get("ambiguities") or [],
        },
    }
