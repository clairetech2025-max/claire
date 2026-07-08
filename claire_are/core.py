from __future__ import annotations

from typing import Any

from claire_are.config import AREConfig
from claire_are.diode_guard import DiodeGuard
from claire_are.truth_spine import TruthDecision, TruthRecord, TruthSpine


class AREStore:
    """Public plugin boundary for governed ARE memory."""

    def __init__(self, config: AREConfig | None = None, guard: DiodeGuard | None = None) -> None:
        self.config = config or AREConfig.from_env()
        self.guard = guard or DiodeGuard()
        self.truth = TruthSpine(
            self.config.root,
            hmac_key=self.config.hmac_key,
            max_segment_records=self.config.max_segment_records,
        )

    def ingest(self, *, text: str, lane: str, source: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        decision = self.guard.check_write(lane=lane, source=source, text=text)
        result = self.truth.append(
            TruthRecord(text=text, lane=lane, source=source, event_type="memory", metadata=metadata or {}),
            TruthDecision(decision.allowed, decision.reason, decision.rules_triggered),
        )
        return self._result_with_decision(result, decision.allowed, decision.reason)

    def log_event(self, *, text: str, lane: str, source: str, event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.truth.append(
            TruthRecord(text=text, lane=lane, source=source, event_type=event_type, metadata=metadata or {}),
            TruthDecision(True, "audit event accepted", []),
        )
        return self._result_with_decision(result, True, "audit event accepted")

    def recall(self, *, query: str, lane: str, limit: int = 8, log: bool = True) -> dict[str, Any]:
        memories = self._search_memories(query=query, lane=lane, limit=limit)
        recall_event = {"record": {"sha": ""}, "truth_hash": ""}
        if log:
            recall_event = self.log_event(
                text=f"ARE recall query lane={lane} hits={len(memories)} query={query[:500]}",
                lane="audit",
                source="are_consult_gate",
                event_type="recall",
                metadata={"requesting_lane": lane, "query": query, "hits": len(memories)},
            )
        return {
            "query": query,
            "lane": lane,
            "recall_event_sha": str(recall_event.get("sha") or ""),
            "recall_truth_hash": str(recall_event.get("truth_hash") or ""),
            "memories": memories,
        }

    def verify(self) -> dict[str, Any]:
        return self.truth.verify()

    def audit_recent(self, limit: int = 25) -> list[dict[str, Any]]:
        return self.truth.envelopes()[-max(0, int(limit)) :]

    def stop(self) -> None:
        self.truth.stop()

    def _search_memories(self, *, query: str, lane: str, limit: int) -> list[dict[str, Any]]:
        query_terms = set(str(query or "").lower().split())
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for idx, envelope in enumerate(self.truth.envelopes()):
            decision = envelope.get("decision") or {}
            payload = envelope.get("payload") or {}
            if not decision.get("allowed"):
                continue
            if payload.get("event_type") != "memory":
                continue
            if not self.guard.can_read(requesting_lane=lane, record_lane=str(payload.get("lane") or "")):
                continue
            text = str(payload.get("text") or "")
            text_terms = set(text.lower().split())
            score = len(query_terms & text_terms)
            if score or not query_terms:
                scored.append((score, idx, self._memory_from_envelope(envelope)))
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [item for _, _, item in scored[: max(0, int(limit))]]

    def _memory_from_envelope(self, envelope: dict[str, Any]) -> dict[str, Any]:
        payload = envelope.get("payload") or {}
        compat = envelope.get("compat") or {}
        return {
            "ts": int(payload.get("ts") or compat.get("ts") or 0),
            "sha": str(compat.get("sha") or "")[:10],
            "text": str(payload.get("text") or compat.get("text") or ""),
            "lane": str(payload.get("lane") or ""),
            "source": str(payload.get("source") or ""),
            "truth_hash": str(envelope.get("truth_hash") or ""),
            "metadata": payload.get("metadata") or {},
        }

    def _result_with_decision(self, result: dict[str, Any], accepted: bool, reason: str) -> dict[str, Any]:
        record = result.get("record") or {}
        envelope = result.get("envelope") or {}
        payload = envelope.get("payload") or {}
        return {
            "status": "accepted" if accepted else "rejected",
            "lane": str(payload.get("lane") or ""),
            "source": str(payload.get("source") or ""),
            "sha": str(record.get("sha") or ""),
            "truth_hash": str(result.get("truth_hash") or ""),
            "accepted": bool(accepted),
            "reason": reason,
        }
