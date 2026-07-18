from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class SweeperFinding:
    sweeper: str
    severity: str
    code: str
    summary: str
    source_ids: list[str] = field(default_factory=list)
    recommended_repair: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VerifiableTruthSpine(Protocol):
    def verify(self, **kwargs: Any) -> dict[str, Any]:
        ...


class IntegritySweeper:
    name = "IntegritySweeper"

    def inspect_truth_spine(self, spine: VerifiableTruthSpine) -> list[SweeperFinding]:
        result = spine.verify()
        if result.get("valid"):
            return []
        return [SweeperFinding(self.name, "critical", str(result.get("reason") or "chain_invalid"), "Truth Spine verification failed.", [], "Stop writes and restore from last verified backup.")]


class ProvenanceSweeper:
    name = "ProvenanceSweeper"

    def inspect_links(self, links: list[dict[str, Any]]) -> list[SweeperFinding]:
        findings = []
        for link in links:
            if not link.get("source_record_id"):
                findings.append(SweeperFinding(self.name, "high", "missing_source_record", "TrailLink is missing a source record.", [str(link.get("link_id") or "")], "Rebuild link from source or mark unsupported."))
        return findings


class TemporalSweeper:
    name = "TemporalSweeper"

    def inspect_events(self, events: list[dict[str, Any]]) -> list[SweeperFinding]:
        findings = []
        for event in events:
            if event.get("status") == "current" and event.get("superseded_by"):
                findings.append(SweeperFinding(self.name, "medium", "current_but_superseded", "Temporal event is current but has supersession pointer.", [str(event.get("event_id") or "")], "Mark old event superseded or remove invalid pointer through migration."))
        return findings


class MatterBoundarySweeper:
    name = "MatterBoundarySweeper"

    def inspect_records(self, records: list[dict[str, Any]], matter_id: str) -> list[SweeperFinding]:
        return [
            SweeperFinding(self.name, "high", "cross_matter_record", "Record belongs to another matter.", [str(record.get("memory_id") or record.get("record_id") or "")], "Quarantine from this matter view.")
            for record in records
            if matter_id and record.get("matter_id") and record.get("matter_id") != matter_id
        ]


class LaneBoundarySweeper:
    name = "LaneBoundarySweeper"

    def inspect_records(self, records: list[dict[str, Any]], lane: str) -> list[SweeperFinding]:
        return [
            SweeperFinding(self.name, "medium", "cross_lane_record", "Record lane does not match permitted lane.", [str(record.get("memory_id") or record.get("record_id") or "")], "Exclude from context unless explicitly authorized.")
            for record in records
            if lane and record.get("lane") and record.get("lane") != lane
        ]


class EvidenceSweeper:
    name = "EvidenceSweeper"

    def inspect_records(self, records: list[dict[str, Any]]) -> list[SweeperFinding]:
        findings = []
        seen: set[str] = set()
        for record in records:
            digest = str(record.get("content_hash") or record.get("sha") or "")
            rid = str(record.get("record_id") or record.get("memory_id") or digest)
            if not digest:
                findings.append(SweeperFinding(self.name, "medium", "missing_hash", "Evidence record lacks content hash.", [rid], "Recompute hash from source artifact."))
            elif digest in seen:
                findings.append(SweeperFinding(self.name, "low", "duplicate_evidence", "Duplicate evidence hash detected.", [rid], "Deduplicate derived indexes only."))
            seen.add(digest)
            if record.get("record_class") == "model_output":
                findings.append(SweeperFinding(self.name, "high", "model_output_as_evidence", "Generated output is classified as evidence.", [rid], "Reclassify as model_output or inference."))
        return findings


class RuntimeSweeper:
    name = "RuntimeSweeper"

    def inspect_status(self, status: dict[str, Any]) -> list[SweeperFinding]:
        return [
            SweeperFinding(self.name, "medium", f"{key.lower()}_offline", f"{key} is not online.", [key], "Check service process and logs.")
            for key, value in status.items()
            if isinstance(value, str) and value.upper() in {"OFFLINE", "ERROR"}
        ]


class SecuritySweeper:
    name = "SecuritySweeper"

    def inspect_echoshield(self, classifications: list[dict[str, Any]]) -> list[SweeperFinding]:
        return [
            SweeperFinding(self.name, "critical" if item.get("quarantine") else "medium", "context_defense_risk", "EchoShield detected risky context.", item.get("source_ids") or [], "Keep quarantined until reviewed.")
            for item in classifications
            if item.get("detected_risks")
        ]


class EmberSweeper:
    name = "EmberSweeper"

    def inspect_handoffs(self, handoffs: list[dict[str, Any]]) -> list[SweeperFinding]:
        findings = []
        now = datetime.now(timezone.utc)
        for handoff in handoffs:
            hid = str(handoff.get("handoff_id") or handoff.get("capsule_id") or "")
            if not handoff.get("source_record_ids") and not handoff.get("important_files"):
                findings.append(SweeperFinding(self.name, "medium", "weak_handoff_sources", "Handoff lacks source references.", [hid], "Regenerate with source IDs and Truth Spine IDs."))
            expires = handoff.get("expires_at")
            if expires:
                try:
                    if datetime.fromisoformat(str(expires).replace("Z", "+00:00")) < now:
                        findings.append(SweeperFinding(self.name, "medium", "expired_handoff", "Handoff is expired.", [hid], "Refresh from current ARE and Truth Spine state."))
                except ValueError:
                    findings.append(SweeperFinding(self.name, "low", "invalid_handoff_expiration", "Handoff expiration is malformed.", [hid], "Normalize expiration timestamp."))
        return findings
