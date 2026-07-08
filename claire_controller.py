from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from claire_sentinel.models import ActionRequest, ToolCategory
from claire_sentinel.policy import SentinelPolicy
from claire_sentinel.runner import ClaireSentinelRunner
from diode_protocol import DiodeProtocol
from handshake_broker import HandshakeBroker
from lane_classifier import classify_lane
from sentinel_validator import validate_response
from trace_logger import TraceLogger, new_trace_id, sha_text

ToolDecision = Literal["ALLOW", "DENY", "ALLOW_READ_ONLY", "ALLOW_DRAFT_ONLY", "ASK_USER_APPROVAL"]


@dataclass
class WorkerToolRequest:
    tool_name: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)

    def redacted(self) -> dict[str, Any]:
        return json.loads(DiodeProtocol.redact(json.dumps(asdict(self), ensure_ascii=False)))


@dataclass
class WorkerState:
    worker_id: str
    user_id: str
    session_id: str
    current_task: str
    prompt: str
    lane: str = ""
    memory_scope: str = "PUBLIC"
    requested_tools: list[WorkerToolRequest] = field(default_factory=list)
    draft_output: str = ""
    status: str = "drafting"
    metadata: dict[str, Any] = field(default_factory=dict)

    def redacted(self) -> dict[str, Any]:
        data = asdict(self)
        data["requested_tools"] = [tool.redacted() for tool in self.requested_tools]
        return json.loads(DiodeProtocol.redact(json.dumps(data, ensure_ascii=False)))


@dataclass
class ControllerPolicy:
    lane: str
    allowed_lanes: list[str]
    forbidden_actions: list[str]
    allowed_memory_scopes: list[str]
    allowed_tools: list[str]
    role: str
    capsule_id: str
    denied_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OutputInspection:
    approved: bool
    action: Literal["RELEASE", "REVISE", "STOP"]
    issues: list[str]
    safe_output: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClaireController:
    """
    CLAIRE as controller/governor for a worker AI.

    The worker performs tasks. This controller reads worker state, sets policy,
    approves or limits tools, inspects output, redacts secrets, and writes safe
    traces. It does not execute the worker's task.
    """

    FORBIDDEN_ACTION_MARKERS = {
        "live_trade": ["live trade", "place live", "buy btc", "sell btc", "place order", "execute trade"],
        "legal_filing": ["file motion", "file a motion", "submit filing", "e-file", "efile", "court filing"],
        "private_data_dump": ["previous users", "all private information", "dump private", "show private", "private memory"],
        "authority_escalation": ["override policy", "ignore claire", "bypass governance", "escalate authority"],
    }

    TOOL_ALIASES = {
        "veritas_status": {"veritas", "kraken", "trading_status"},
        "legal_research": {"courtlistener", "court_listener", "legal_research"},
        "repo_status": {"repo", "git", "repo_status"},
        "truth_files": {"truth_files", "current_truth"},
        "file_read": {"file_read", "read_file"},
        "email_draft": {"email", "email_draft", "send_email"},
    }

    def __init__(
        self,
        broker: HandshakeBroker | None = None,
        trace_logger: TraceLogger | None = None,
        sentinel_runner: ClaireSentinelRunner | None = None,
    ) -> None:
        self.broker = broker or HandshakeBroker()
        self.trace_logger = trace_logger or TraceLogger()
        sentinel_config = os.environ.get("CLAIRE_SENTINEL_CONFIG", "")
        sentinel_policy = SentinelPolicy.from_json(sentinel_config) if sentinel_config else SentinelPolicy()
        self.sentinel_runner = sentinel_runner or ClaireSentinelRunner(policy=sentinel_policy)
        self._worker_states: dict[str, WorkerState] = {}
        self._policies: dict[str, ControllerPolicy] = {}
        self._stopped_workers: dict[str, str] = {}

    def get_state(self, worker_state: WorkerState) -> dict[str, Any]:
        self._worker_states[worker_state.worker_id] = worker_state
        return worker_state.redacted()

    def set_policy(self, worker_state: WorkerState, metadata: dict[str, Any] | None = None) -> ControllerPolicy:
        metadata = metadata or {}
        redacted_prompt = self.redact(worker_state.prompt)
        lane = worker_state.lane or classify_lane(redacted_prompt).lane
        risk_level = self._risk_level(worker_state)
        decision = self.broker.resolve_authority(
            user_id=worker_state.user_id,
            session_id=worker_state.session_id,
            lane=lane,
            request_text=redacted_prompt,
            risk_level=risk_level,
            metadata={**metadata, "raw_request_text": worker_state.prompt},
        )
        forbidden = self._forbidden_actions(worker_state)
        policy = ControllerPolicy(
            lane=lane,
            allowed_lanes=[lane],
            forbidden_actions=forbidden,
            allowed_memory_scopes=list(decision.capsule.allowed_memory_scopes),
            allowed_tools=list(decision.capsule.allowed_tools),
            role=decision.capsule.role,
            capsule_id=decision.capsule.capsule_id,
            denied_reasons=list(decision.denied_reasons),
        )
        self._policies[worker_state.worker_id] = policy
        return policy

    def approve_tool_call(
        self,
        worker_state: WorkerState,
        tool_request: WorkerToolRequest,
        policy: ControllerPolicy | None = None,
    ) -> ToolDecision:
        policy = policy or self._policies.get(worker_state.worker_id) or self.set_policy(worker_state)
        tool = tool_request.tool_name.lower()
        action = tool_request.action.lower()
        text = " ".join([tool, action, json.dumps(tool_request.args, ensure_ascii=False)]).lower()

        if DiodeProtocol.contains_secret(json.dumps(tool_request.args, ensure_ascii=False)):
            return "DENY"
        if any(marker in text for marker in self.FORBIDDEN_ACTION_MARKERS["authority_escalation"]):
            return "DENY"
        if any(marker in text for marker in self.FORBIDDEN_ACTION_MARKERS["private_data_dump"]):
            return "DENY"
        if any(marker in text for marker in self.FORBIDDEN_ACTION_MARKERS["live_trade"]):
            return "DENY"
        if any(marker in text for marker in self.FORBIDDEN_ACTION_MARKERS["legal_filing"]):
            return "DENY"
        sentinel_decision = self._approve_sentinel_tool_call(worker_state, tool_request, policy)
        if sentinel_decision is not None:
            return sentinel_decision
        if tool in self.TOOL_ALIASES["email_draft"] or action in {"send", "send_email"}:
            return "ALLOW_DRAFT_ONLY"
        if tool in self.TOOL_ALIASES["file_read"] or action in {"read", "list", "open"}:
            return "ALLOW_READ_ONLY"
        if self._tool_allowed(tool, policy.allowed_tools):
            return "ALLOW"
        if tool in {"veritas", "kraken", "courtlistener"}:
            return "ASK_USER_APPROVAL"
        return "DENY"

    def inspect_output(
        self,
        worker_state: WorkerState,
        policy: ControllerPolicy | None = None,
    ) -> OutputInspection:
        policy = policy or self._policies.get(worker_state.worker_id) or self.set_policy(worker_state)
        safe_output = self.redact(worker_state.draft_output)
        validation = validate_response(safe_output, {"controller_policy": policy.to_dict()}, policy.lane)
        issues = list(validation.get("issues") or [])
        lowered = safe_output.lower()
        if any(marker in lowered for marker in ["lane:", "trace_id", "authority gates", "context packet"]):
            issues.append("internal_scaffolding_leak")
        if DiodeProtocol.contains_secret(worker_state.draft_output):
            issues.append("secret_leakage_blocked")
        if any(marker in lowered for marker in self.FORBIDDEN_ACTION_MARKERS["live_trade"]):
            issues.append("live_trade_output_blocked")
        if any(marker in lowered for marker in self.FORBIDDEN_ACTION_MARKERS["legal_filing"]):
            issues.append("legal_filing_output_blocked")
        if any(marker in lowered for marker in self.FORBIDDEN_ACTION_MARKERS["private_data_dump"]):
            issues.append("private_data_output_blocked")

        approved = not issues
        action: Literal["RELEASE", "REVISE", "STOP"] = "RELEASE" if approved else "REVISE"
        if any(issue in issues for issue in ["secret_leakage_blocked", "live_trade_output_blocked", "legal_filing_output_blocked", "private_data_output_blocked"]):
            action = "STOP"
            self.stop_agent(worker_state, "; ".join(issues))
        return OutputInspection(approved=approved, action=action, issues=issues, safe_output=safe_output)

    def redact(self, text: str) -> str:
        return DiodeProtocol.redact(text)

    def stop_agent(self, worker_state: WorkerState, reason: str) -> dict[str, str]:
        self._stopped_workers[worker_state.worker_id] = reason
        worker_state.status = "stopped"
        return {"worker_id": worker_state.worker_id, "status": "stopped", "reason": reason}

    def write_trace(
        self,
        worker_state: WorkerState,
        policy: ControllerPolicy,
        inspection: OutputInspection | None = None,
        tool_decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        safe_state = worker_state.redacted()
        inspection_payload = inspection.to_dict() if inspection else {}
        record = {
            "trace_id": new_trace_id(),
            "user_message_hash": sha_text(self.redact(worker_state.prompt)),
            "lane": policy.lane,
            "memories_recalled": [],
            "prompt_hash": sha_text(json.dumps(safe_state, ensure_ascii=False, sort_keys=True)),
            "model_used": "worker_ai_governed_by_claire",
            "risk_level": self._risk_level(worker_state),
            "validator_result": {"approved": bool(inspection.approved) if inspection else True, "issues": list(inspection.issues) if inspection else []},
            "final_answer_hash": sha_text(inspection.safe_output if inspection else ""),
            "memory_written": False,
            "worker_id": worker_state.worker_id,
            "worker_status": worker_state.status,
            "capsule_id": policy.capsule_id,
            "role": policy.role,
            "allowed_memory_scopes": list(policy.allowed_memory_scopes),
            "allowed_tools": list(policy.allowed_tools),
            "forbidden_actions": list(policy.forbidden_actions),
            "tool_decisions": json.loads(DiodeProtocol.redact(json.dumps(tool_decisions or [], ensure_ascii=False))),
            "inspection": json.loads(DiodeProtocol.redact(json.dumps(inspection_payload, ensure_ascii=False))),
            "state_hash": sha_text(json.dumps(safe_state, ensure_ascii=False, sort_keys=True)),
        }
        return self.trace_logger.log(record)

    def replay_trace(self, trace_id: str) -> dict[str, Any] | None:
        record = self.trace_logger.get(trace_id)
        if record is None:
            return None
        return json.loads(DiodeProtocol.redact(json.dumps(record, ensure_ascii=False)))

    def _risk_level(self, worker_state: WorkerState) -> str:
        text = " ".join([
            worker_state.prompt,
            worker_state.current_task,
            worker_state.draft_output,
            " ".join(json.dumps(tool.redacted(), ensure_ascii=False) for tool in worker_state.requested_tools),
        ]).lower()
        for markers in self.FORBIDDEN_ACTION_MARKERS.values():
            if any(marker in text for marker in markers):
                return "high"
        if DiodeProtocol.contains_secret(text):
            return "high"
        return "low"

    def _forbidden_actions(self, worker_state: WorkerState) -> list[str]:
        text = " ".join([worker_state.prompt, worker_state.current_task]).lower()
        forbidden = []
        for name, markers in self.FORBIDDEN_ACTION_MARKERS.items():
            if any(marker in text for marker in markers):
                forbidden.append(name)
        return forbidden

    def _tool_allowed(self, tool_name: str, allowed_tools: list[str]) -> bool:
        allowed = {tool.lower() for tool in allowed_tools}
        if tool_name in allowed:
            return True
        for canonical, aliases in self.TOOL_ALIASES.items():
            if tool_name in aliases and canonical in allowed:
                return True
        return False

    def _approve_sentinel_tool_call(
        self,
        worker_state: WorkerState,
        tool_request: WorkerToolRequest,
        policy: ControllerPolicy,
    ) -> ToolDecision | None:
        args = tool_request.args or {}
        requested_tool = str(args.get("tool") or tool_request.tool_name or "").lower()
        if requested_tool in {"sentinel", "claire_sentinel", "security"}:
            requested_tool = str(args.get("security_tool") or args.get("name") or "").lower()
        if not requested_tool or self.sentinel_runner.registry.get(requested_tool) is None:
            return None
        if policy.role == "guest":
            self.sentinel_runner.audit_log.append({
                "tool": requested_tool,
                "target": str(args.get("target") or args.get("host") or args.get("domain") or args.get("ip") or ""),
                "reason": str(args.get("reason") or worker_state.current_task or tool_request.action or ""),
                "command": [requested_tool],
                "decision": {
                    "allowed": False,
                    "reason": "Claire controller requires trusted authority for Sentinel security actions.",
                    "risk_level": "high",
                    "category": "security_operations",
                    "requires_approval": False,
                },
                "returncode": None,
                "output_summary": "Denied before execution by Claire controller authority gate.",
                "risk_level": "high",
                "dry_run": True,
                "worker_id": worker_state.worker_id,
                "capsule_id": policy.capsule_id,
            })
            return "DENY"

        target = str(args.get("target") or args.get("host") or args.get("domain") or args.get("ip") or "")
        reason = str(args.get("reason") or worker_state.current_task or tool_request.action or "")
        operator_approved = bool(args.get("operator_approved") or args.get("approved") or args.get("approval"))
        cli_args = args.get("args") or args.get("command_args") or ()
        if isinstance(cli_args, str):
            cli_args = tuple(cli_args.split())
        else:
            cli_args = tuple(str(item) for item in cli_args)

        result = self.sentinel_runner.run(ActionRequest(
            tool=requested_tool,
            target=target,
            reason=reason,
            args=cli_args,
            operator_approved=operator_approved,
            dry_run=True,
        ))
        if result.decision.allowed:
            if result.decision.category == ToolCategory.VULNERABILITY_SCANNING:
                return "ALLOW"
            return "ALLOW_READ_ONLY"
        if result.decision.requires_approval:
            return "ASK_USER_APPROVAL"
        return "DENY"
