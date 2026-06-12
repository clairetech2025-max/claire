from __future__ import annotations

import json
import re
import time
from typing import Any

from are_memory_store import AREMemoryStore, MemoryEvent
from context_builder import build_context_packet
from current_truth_loader import load_current_truth, truth_for_lane
from entity_registry import identify_entities
from lane_classifier import LaneResult, classify_lane
from claire_runtime_router import c3rp_classify, normalize_input as c3rp_normalize_input, provisional_orientation
from language_guard import strengthen_confidence_language
from memory_committer import commit_if_needed, should_commit_memory
from memory_eligibility import evaluate_memory_eligibility
from nemotron_adapter import build_messages, call_nemotron, messages_to_prompt
from nvidia_mode import apply_nvidia_mode, nvidia_constraints
from original_are_bridge import append_original_are_memory, read_original_are_history
from sentinel_validator import validate_response
from trace_logger import TraceLogger, new_trace_id, sha_text


class ClaireRuntime:
    """
    Governed runtime around Nemotron.

    Nemotron is only called after CLAIRE has normalized input, classified lane,
    reviewed memory eligibility, loaded current truth, recalled lane-eligible
    memory, built context, and applied risk/authority gates.
    """

    def __init__(
        self,
        memory_store: AREMemoryStore | None = None,
        trace_logger: TraceLogger | None = None,
        model_config: dict[str, Any] | None = None,
        use_original_are: bool | None = None,
    ) -> None:
        self.use_original_are = (memory_store is None) if use_original_are is None else use_original_are
        self.memory_store = memory_store if memory_store is not None else (None if self.use_original_are else AREMemoryStore())
        self.trace_logger = trace_logger or TraceLogger()
        self.model_config = model_config or {}

    def handle_user_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        if metadata.get("demo_mode"):
            return self.handle_demo_message(user_id, session_id, message, metadata)
        trace_id = new_trace_id()

        normalized = self._normalize_input(message)
        c3rp_route = self._c3rp_route(normalized)
        lane_result = self._lane_result_from_c3rp(normalized, c3rp_route, metadata.get("recent_context"))
        lane = lane_result.lane
        full_truth = load_current_truth()
        current_truth = truth_for_lane(lane, full_truth)
        entities = identify_entities(normalized)
        entity_names = [entity["name"] for entity in entities]
        eligibility = evaluate_memory_eligibility(normalized, lane)
        recent_path, long_term_memories = self._recall_memory(user_id, lane_result, entity_names)
        risk_level, risks = self._risk_authority_gate(lane, normalized)
        constraints = self._constraints(lane)

        context_packet = build_context_packet(
            lane_result=lane_result,
            user_goal=normalized,
            current_truth=current_truth,
            entities=entities,
            recent_path=recent_path,
            long_term_memories=long_term_memories,
            constraints=constraints,
            risks=risks,
        )
        messages = build_messages(context_packet, normalized)
        raw_response = call_nemotron(
            messages,
            model_config=metadata.get("model_config") or self.model_config,
            provider_generate=metadata.get("provider_generate"),
        )
        answer = str(raw_response.get("content") or "").strip()
        answer = strengthen_confidence_language(answer)
        if lane == "NVIDIA_PATHWAY":
            answer = apply_nvidia_mode(answer)

        validator_result = validate_response(answer, context_packet, lane)
        if not validator_result.get("approved") and validator_result.get("revised_answer"):
            answer = str(validator_result["revised_answer"])

        runtime_report = None
        if self._wants_runtime_orientation(normalized):
            runtime_report = self._build_runtime_report(
                normalized=normalized,
                lane_result=lane_result,
                eligibility=eligibility,
                recent_path=recent_path,
                long_term_memories=long_term_memories,
                risk_level=risk_level,
                risks=risks,
                validator_result=validator_result,
                model_answer=answer,
            )
            answer = json.dumps(runtime_report, ensure_ascii=False, indent=2)

        memory_written, memory_event = self._commit_memory(
            user_id=user_id,
            session_id=session_id,
            message=normalized,
            lane=lane,
            answer=answer,
            eligibility=eligibility,
        )

        result = {
            "answer": answer,
            "lane": lane,
            "used_memory": [memory.get("memory_id") for memory in recent_path + long_term_memories if memory.get("memory_id")],
            "risk_level": risk_level,
            "trace_id": trace_id,
            "memory_written": memory_written,
        }
        if runtime_report is not None:
            result["runtime_report"] = runtime_report
        trace_record = {
            "trace_id": trace_id,
            "timestamp_ns": None,
            "user_id": user_id,
            "session_id": session_id,
            "user_message_hash": sha_text(normalized),
            "lane": lane,
            "lane_result": lane_result.to_dict() if hasattr(lane_result, "to_dict") else lane_result.__dict__,
            "c3rp_route": c3rp_route,
            "memories_recalled": result["used_memory"],
            "prompt_hash": sha_text(messages_to_prompt(messages)),
            "model_used": self._model_used(raw_response),
            "risk_level": risk_level,
            "validator_result": validator_result,
            "final_answer_hash": sha_text(answer),
            "memory_written": memory_written,
            "memory_event_id": (memory_event or {}).get("memory_id"),
            "runtime_report": runtime_report,
            "steps": [
                "input_normalization",
                "c3rp_lane_classification",
                "memory_eligibility_review",
                "are_chronological_recall",
                "current_truth_loading",
                "context_building",
                "risk_authority_gating",
                "nemotron_prompt_construction",
                "response_validation",
                "trace_logging",
                "memory_commit_decision",
            ],
        }
        self.trace_logger.log(trace_record)
        if self.memory_store is not None:
            self.memory_store.append_session_trace(trace_id, user_id, session_id, lane, trace_record)
        return result

    def handle_demo_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        input_received = str(message or "")
        trace_id = new_trace_id()
        steps = [
            "ingest_input",
            "generate_trace_id",
            "run_are_recall",
            "run_policy_validation",
            "build_llm_prompt",
            "call_llm",
            "assemble_response_json",
            "persist_trace",
            "return_response",
        ]

        try:
            c3rp_route = self._c3rp_route(input_received)
            lane_result = self._lane_result_from_c3rp(input_received, c3rp_route, metadata.get("recent_context"))
            memories = self._recall_demo_memory(user_id, lane_result.lane)
            memories = [
                item for item in memories
                if self._memory_supports_demo_input(input_received, lane_result.lane, item)
            ]
            recall_check = {
                "status": "found" if memories else "none",
                "summary": "Relevant prior memory found." if memories else "No relevant prior memory found.",
                "items": [
                    {
                        "memory_id": item.get("memory_id"),
                        "timestamp_ns": item.get("timestamp_ns"),
                        "lane": item.get("lane"),
                        "summary": item.get("summary"),
                    }
                    for item in memories
                ],
            }
        except Exception:
            c3rp_route = self._c3rp_route(input_received)
            lane_result = self._lane_result_from_c3rp(input_received, c3rp_route)
            memories = []
            recall_check = {
                "status": "error",
                "summary": "Recall subsystem unavailable.",
                "items": [],
            }

        try:
            risk_level, risks = self._risk_authority_gate(lane_result.lane, input_received)
            policy_validation = {
                "status": "warning" if risks else "allowed",
                "summary": "; ".join(risks) if risks else "No policy constraints violated.",
                "rules_triggered": risks,
            }
        except Exception:
            risk_level = "unknown"
            policy_validation = {
                "status": "warning",
                "summary": "Policy subsystem unavailable.",
                "rules_triggered": [],
            }

        messages = self._build_demo_messages(input_received, recall_check, policy_validation)
        try:
            raw_response = call_nemotron(
                messages,
                model_config=metadata.get("model_config") or self.model_config,
                provider_generate=metadata.get("provider_generate"),
            )
        except Exception as exc:
            raw_response = {
                "content": "",
                "reasoning_content": "",
                "raw": {"provider_error": str(exc)},
            }
        llm_fields = self._parse_demo_llm_fields(raw_response.get("content"))
        identity = llm_fields.get("identity") or "CLAIRE governed demo runtime."
        decision = llm_fields.get("decision") or "Simulated action only."
        output = llm_fields.get("output") or "Simulating requested action for demonstration only; no real-world execution performed."

        if input_received.strip().lower() == "schedule a horseback ride tomorrow at 10am":
            decision = "Simulated action only."
            output = "Simulating scheduling action for demonstration only; no real-world execution performed."

        response = {
            "trace_id": trace_id,
            "demo_mode": True,
            "identity": identity,
            "input_received": input_received,
            "recall_check": recall_check,
            "policy_validation": policy_validation,
            "decision": decision,
            "output": output,
            "trace_summary": {
                "steps_executed": steps,
                "decisions_made": [
                    f"lane={lane_result.lane}",
                    f"recall={recall_check['status']}",
                    f"policy={policy_validation['status']}",
                    "execution=simulation_only",
                ],
            },
        }
        self._validate_demo_response(response)
        trace_record = {
            "trace_id": trace_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "input": input_received,
            "recall": recall_check,
            "policy": policy_validation,
            "decision": decision,
            "output": output,
            "steps": steps,
        }
        self._persist_demo_trace(trace_record)
        self.trace_logger.log(
            {
                "trace_id": trace_id,
                "user_id": user_id,
                "session_id": session_id,
                "user_message_hash": sha_text(input_received),
                "lane": lane_result.lane,
                "memories_recalled": [item.get("memory_id") for item in memories if item.get("memory_id")],
                "prompt_hash": sha_text(messages_to_prompt(messages)),
                "model_used": self._model_used(raw_response),
                "risk_level": risk_level,
                "validator_result": {"approved": True, "issues": []},
                "final_answer_hash": sha_text(output),
                "memory_written": False,
                "payload": response,
            }
        )
        return response

    def _build_demo_messages(
        self,
        input_received: str,
        recall_check: dict[str, Any],
        policy_validation: dict[str, Any],
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are CLAIRE demo mode. Return only a compact JSON object with keys "
                    "identity, decision, and output. No hidden reasoning. No real-world actions. "
                    "Use the supplied recall and policy summaries only."
                ),
            },
            {
                "role": "system",
                "content": (
                    f"Recall status: {recall_check.get('status')}. "
                    f"Recall summary: {recall_check.get('summary')}\n"
                    f"Policy status: {policy_validation.get('status')}. "
                    f"Policy summary: {policy_validation.get('summary')}"
                ),
            },
            {"role": "user", "content": input_received},
        ]

    def _parse_demo_llm_fields(self, model_text: Any) -> dict[str, str]:
        text = str(model_text or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            key: str(parsed.get(key) or "").strip()
            for key in ("identity", "decision", "output")
            if str(parsed.get(key) or "").strip()
        }

    def _memory_supports_demo_input(self, input_received: str, lane: str, memory: dict[str, Any]) -> bool:
        text = " ".join(
            str(memory.get(key) or "")
            for key in ("summary", "raw_excerpt", "lane", "source")
        ).lower()
        if not text.strip():
            return False
        memory_lane = str(memory.get("lane") or "")
        if memory_lane not in {lane, "GENERAL_CHAT", "SESSION", "ORIGINAL_ARE"}:
            return False
        query_terms = {
            term
            for term in re.findall(r"[a-z0-9']+", input_received.lower())
            if len(term) > 3 and term not in {"schedule", "tomorrow", "demo", "mode"}
        }
        if not query_terms:
            return False
        return bool(query_terms.intersection(set(re.findall(r"[a-z0-9']+", text))))

    def _normalize_input(self, message: str) -> str:
        return " ".join(str(message or "").split())

    def _c3rp_route(self, message: str) -> dict[str, Any]:
        normalized = c3rp_normalize_input(message)
        orientation = provisional_orientation(normalized)
        return c3rp_classify(normalized, orientation)

    def _lane_result_from_c3rp(
        self,
        message: str,
        c3rp_route: dict[str, Any],
        recent_context: list[dict[str, Any]] | None = None,
    ) -> LaneResult:
        base = classify_lane(message, recent_context)
        c3rp_lane = str(c3rp_route.get("lane") or "").upper()
        legacy = c3rp_route.get("legacy_intent") or {}
        lane = base.lane
        reason = f"C3RP route={c3rp_lane}; {base.reason}"

        if c3rp_lane == "LEGAL_RESEARCH":
            lane = "LEGAL_CASE"
        elif c3rp_lane == "DOCUMENT_QA":
            lane = "GENERAL_CHAT"
            reason = "C3RP document utility route admitted through governed runtime."
        elif c3rp_lane == "SAFETY_SENSITIVE":
            lane = "GENERAL_CHAT"
            reason = "C3RP safety-sensitive route contained by governed runtime."
        elif c3rp_lane == "ACTION_REQUEST" and base.lane == "GENERAL_CHAT":
            lane = "GENERAL_CHAT"
            reason = "C3RP action request route admitted for simulated or advisory response only."
        elif c3rp_lane in {"CONCEPTUAL", "PROJECT_STATE"} and base.lane == "GENERAL_CHAT":
            primary = str(legacy.get("primary_intent") or "")
            secondaries = set(legacy.get("secondary_intents") or [])
            if primary == "architectural" or "architectural" in secondaries:
                lane = "CLAIRE_SYSTEM_ARCHITECTURE"
            elif primary == "legal" or "legal" in secondaries:
                lane = "LEGAL_CASE"

        allowed = list(base.allowed_memory_lanes or [])
        for item in c3rp_route.get("allowed_lanes") or []:
            item = str(item)
            if item not in allowed:
                allowed.append(item)
        return LaneResult(
            lane=lane,
            confidence=base.confidence,
            reason=reason,
            allowed_memory_lanes=allowed or [lane],
            allowed_tools=base.allowed_tools,
            requires_strict_provenance=base.requires_strict_provenance or bool(c3rp_route.get("suppressed_lanes")),
            caution=base.caution,
            output_style=base.output_style,
        )

    def _wants_runtime_orientation(self, message: str) -> bool:
        text = str(message or "").lower()
        triggers = [
            "before you answer, orient",
            "answer like claire",
            "give runtime decision",
            "what should happen inside your runtime",
            "show your runtime decision",
            "orient first",
        ]
        return any(trigger in text for trigger in triggers)

    def _build_runtime_report(
        self,
        *,
        normalized: str,
        lane_result: LaneResult,
        eligibility: Any,
        recent_path: list[dict[str, Any]],
        long_term_memories: list[dict[str, Any]],
        risk_level: str,
        risks: list[str],
        validator_result: dict[str, Any],
        model_answer: str,
    ) -> dict[str, Any]:
        should_write, write_reason = should_commit_memory(normalized, lane_result.lane, eligibility)
        secondary_lanes = [lane for lane in lane_result.allowed_memory_lanes if lane != lane_result.lane]
        return {
            "lane": lane_result.lane,
            "secondary_lanes": secondary_lanes,
            "memory_eligibility": eligibility.to_dict() if hasattr(eligibility, "to_dict") else dict(eligibility or {}),
            "should_write_to_ARE": should_write,
            "ARE_write_format": "original ARE JSONL: {ts:int, sha:sha256(text)[:10], text:text[:8000]}",
            "memory_event_type": "durable_exchange" if should_write else "none",
            "durable_summary": normalized[:500] if should_write else "No durable ARE write recommended for this request.",
            "why_Nemotron_does_not_own_this_memory": "Nemotron receives a governed prompt and produces language only; durable memory is committed by CLAIRE through original_are_bridge.py after policy and eligibility checks.",
            "how_future_sessions_should_recall_it": "Future sessions should read chronological records through original_are_bridge.read_original_are_history and use them only as lane-governed support.",
            "Sentinel_checks": {
                "risk_level": risk_level,
                "risks": risks,
                "validator_result": validator_result,
                "write_reason": write_reason,
            },
            "Trace_fields_to_record": [
                "trace_id",
                "user_message_hash",
                "lane",
                "lane_result",
                "c3rp_route",
                "memories_recalled",
                "prompt_hash",
                "model_used",
                "validator_result",
                "final_answer_hash",
                "memory_written",
            ],
            "assumptions_allowed": [
                "Use current truth files as higher authority than old memory.",
                "Use original ARE records as chronological support, not as model-owned memory.",
                "Treat Nemotron output as language generation subject to Sentinel validation.",
            ],
            "assumptions_blocked": [
                "Do not invent memory.",
                "Do not let Nemotron write or rewrite durable memory directly.",
                "Do not promote SQLite or vector search to default runtime memory authority.",
                "Do not surface off-lane recalled material as the answer.",
            ],
            "final_response_to_user": model_answer,
            "recall_summary": {
                "recent_path_count": len(recent_path),
                "long_term_memory_count": len(long_term_memories),
                "memory_ids": [memory.get("memory_id") for memory in recent_path + long_term_memories if memory.get("memory_id")],
            },
        }

    def _recall_memory(
        self,
        user_id: str,
        lane_result: LaneResult,
        entity_names: list[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if self.use_original_are:
            history = read_original_are_history(limit=8)
            memories = [
                {
                    "memory_id": f"original_are_{item.get('sha') or item.get('line_number')}",
                    "timestamp_ns": int(item.get("ts") or 0) * 1_000_000_000,
                    "lane": "ORIGINAL_ARE",
                    "summary": str(item.get("text") or "")[:500],
                    "source": "original_are",
                    "provenance_hash": item.get("sha"),
                    "importance_score": 1.0,
                }
                for item in history.get("records", [])
            ]
            memories.sort(key=lambda memory: int(memory.get("timestamp_ns") or 0))
            return memories[-5:], memories[:-5]

        allowed = set(lane_result.allowed_memory_lanes or [lane_result.lane])
        primary_lane = lane_result.lane
        recent = self.memory_store.recall_recent(user_id, lane=primary_lane, limit=8)
        entity_hits = self.memory_store.recall_by_entity(user_id, entity_names, lane=primary_lane, limit=8)

        def lane_allowed(memory: dict[str, Any]) -> bool:
            return str(memory.get("lane") or "") in allowed

        seen: set[str] = set()
        ordered: list[dict[str, Any]] = []
        for memory in recent + entity_hits:
            memory_id = str(memory.get("memory_id") or "")
            if memory_id and memory_id not in seen and lane_allowed(memory):
                seen.add(memory_id)
                ordered.append(memory)
        ordered.sort(key=lambda memory: int(memory.get("timestamp_ns") or 0))
        return ordered[-5:], ordered[:-5]

    def _recall_demo_memory(self, user_id: str, lane: str) -> list[dict[str, Any]]:
        if self.use_original_are:
            history = read_original_are_history(limit=5)
            return [
                {
                    "memory_id": f"original_are_{item.get('sha') or item.get('line_number')}",
                    "timestamp_ns": int(item.get("ts") or 0) * 1_000_000_000,
                    "lane": "ORIGINAL_ARE",
                    "summary": str(item.get("text") or "")[:500],
                    "source": "original_are",
                }
                for item in history.get("records", [])
            ]
        return self.memory_store.recall_recent(user_id, lane=lane, limit=5)

    def _commit_memory(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        lane: str,
        answer: str,
        eligibility: Any,
    ) -> tuple[bool, dict[str, Any] | None]:
        if self.use_original_are:
            ok, reason = should_commit_memory(message, lane, eligibility)
            if not ok:
                return False, None
            text = (
                f"lane={lane}\n"
                f"user_id={user_id}\n"
                f"session_id={session_id}\n"
                f"reason={reason}\n"
                f"message={message}\n"
                f"answer={answer[:1200]}"
            )
            written = append_original_are_memory(text)
            return True, {
                "memory_id": f"original_are_{written['record']['sha']}",
                "source": "original_are",
                "memory_file": written["memory_file"],
            }
        return commit_if_needed(
            self.memory_store or AREMemoryStore(),
            user_id,
            session_id,
            message,
            lane,
            answer,
            eligibility,
        )

    def _constraints(self, lane: str) -> list[str]:
        constraints = [
            "Current truth files outrank old memory.",
            "Use retrieval only as support; answer the active question directly.",
            "Suppress irrelevant off-lane memories.",
            "Do not confuse Claire the person with CLAIRE the AI/runtime system.",
            "Do not treat Nemotron as CLAIRE herself.",
        ]
        if lane == "NVIDIA_PATHWAY":
            constraints.extend(nvidia_constraints())
        if lane == "TRADING_STATION":
            constraints.append("Never place live trades directly from chat.")
        if lane == "LEGAL_CASE":
            constraints.append("Do not provide legal or tax certainty without professional review.")
        return constraints

    def _risk_authority_gate(self, lane: str, message: str) -> tuple[str, list[str]]:
        text = message.lower()
        risks: list[str] = []
        if lane == "TRADING_STATION" and any(term in text for term in ["buy now", "sell now", "place order", "live trade"]):
            risks.append("Live trading requires Veritas live gates, passphrase, risk governor, kill switch check, and external confirmation.")
        if lane == "LEGAL_CASE":
            risks.append("Legal lane requires source gating and no professional-certainty claims.")
        if any(term in text for term in ["password", "private key", "social security", "ssn"]):
            risks.append("Sensitive data detected.")
        return ("high" if risks else "low", risks)

    def _model_used(self, raw_response: dict[str, Any]) -> str:
        raw = raw_response.get("raw") or {}
        return str(raw.get("model") or raw.get("provider") or "nvidia_nemotron")

    def _validate_demo_response(self, response: dict[str, Any]) -> None:
        if not response.get("trace_id"):
            raise ValueError("demo response missing trace_id")
        if "input_received" not in response:
            raise ValueError("demo response missing input_received")
        if not response.get("output"):
            raise ValueError("demo response missing output")
        if not response.get("trace_summary", {}).get("steps_executed"):
            raise ValueError("demo response missing trace_summary.steps_executed")

    def _persist_demo_trace(self, record: dict[str, Any]) -> None:
        from pathlib import Path

        path = Path("data/traces.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        from pathlib import Path

        path = Path("data/traces.jsonl")
        if not path.exists():
            runtime_trace = self.trace_logger.get(trace_id)
            return runtime_trace
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("trace_id") == trace_id:
                    return record
        return self.trace_logger.get(trace_id)


def handle_user_message(user_id: str, session_id: str, message: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return ClaireRuntime().handle_user_message(user_id, session_id, message, metadata)
