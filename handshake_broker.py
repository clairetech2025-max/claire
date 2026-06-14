from __future__ import annotations

import hmac
import time
import uuid
from dataclasses import dataclass
from typing import Any

from authority_capsule import AuthorityCapsule, AuthorityCapsuleSigner
from diode_protocol import DiodeProtocol


LANE_SCOPE_POLICY = {
    "GENERAL_CHAT": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "USER_PRIVATE"], "guest_tools": [], "trusted_tools": []},
    "GENERAL": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "USER_PRIVATE"], "guest_tools": [], "trusted_tools": []},
    "WRITING": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "USER_PRIVATE"], "guest_tools": [], "trusted_tools": []},
    "HORSE_STEWARDSHIP": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "HORSE_STEWARDSHIP", "USER_PRIVATE"], "guest_tools": [], "trusted_tools": ["truth_files"]},
    "TRADING_STATION": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "TRADING_SENSITIVE", "COMPANY_INTERNAL"], "guest_tools": [], "trusted_tools": ["veritas_status"]},
    "LEGAL_CASE": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "LEGAL_SENSITIVE", "COMPANY_INTERNAL"], "guest_tools": [], "trusted_tools": ["legal_research"]},
    "CLAIRE_SYSTEM_ARCHITECTURE": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "COMPANY_INTERNAL", "OWNER_ONLY"], "guest_tools": ["repo_status"], "trusted_tools": ["repo_status", "truth_files"]},
    "CLAIRE_ARCHITECTURE": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "COMPANY_INTERNAL", "OWNER_ONLY"], "guest_tools": ["repo_status"], "trusted_tools": ["repo_status", "truth_files"]},
    "NVIDIA_PATHWAY": {"guest_scopes": ["PUBLIC"], "trusted_scopes": ["PUBLIC", "COMPANY_INTERNAL"], "guest_tools": ["repo_status"], "trusted_tools": ["repo_status", "benchmark_status"]},
    "SENSITIVE_ACTION": {"guest_scopes": [], "trusted_scopes": [], "guest_tools": [], "trusted_tools": []},
}

SENSITIVE_TOOL_MARKERS = [
    "live trade",
    "place a live",
    "execute",
    "buy btc",
    "sell btc",
    "place order",
    "file a motion",
    "submit filing",
    "e-file",
]


@dataclass
class BrokerDecision:
    capsule: AuthorityCapsule
    token: str
    trusted: bool
    denied_reasons: list[str]
    demo_mode: bool


class HandshakeBroker:
    """
    Handshake Broker by Claire Systems.

    Demo identity-and-authority broker for CLAIRE. Production should use
    WebAuthn/FIDO2/passkeys or hardware-backed device signing. This local demo
    uses HMAC challenge/signature only to prove the authority flow.
    """

    def __init__(self, signer: AuthorityCapsuleSigner | None = None) -> None:
        self.signer = signer or AuthorityCapsuleSigner()

    def make_challenge(self, session_id: str, device_id: str | None = None) -> dict[str, str]:
        nonce = uuid.uuid4().hex
        challenge = f"{session_id}:{device_id or 'unknown'}:{nonce}:{int(time.time())}"
        return {"challenge": challenge, "nonce": nonce, "demo_mode": str(self.signer.demo_mode).lower()}

    def verify_demo_signature(self, challenge: str, signature: str, device_secret: str) -> bool:
        expected = hmac.new(device_secret.encode("utf-8"), challenge.encode("utf-8"), "sha256").hexdigest()
        return hmac.compare_digest(str(signature or ""), expected)

    def resolve_authority(
        self,
        *,
        user_id: str,
        session_id: str,
        lane: str,
        request_text: str,
        risk_level: str,
        metadata: dict[str, Any] | None = None,
    ) -> BrokerDecision:
        metadata = metadata or {}
        request_text = DiodeProtocol.redact(request_text)
        token = str(metadata.get("authority_token") or "")
        verified = self.signer.verify(token, expected_request_text=request_text, expected_lane=lane) if token else None
        trusted = bool(verified) or bool(metadata.get("trusted_device") or metadata.get("owner_mode"))
        role = verified.role if verified else ("owner" if trusted else "guest")
        device_id = verified.device_id if verified else metadata.get("device_id")
        policy = LANE_SCOPE_POLICY.get(lane, LANE_SCOPE_POLICY["GENERAL_CHAT"])
        scopes = list(policy["trusted_scopes"] if trusted else policy["guest_scopes"])
        tools = list(policy["trusted_tools"] if trusted else policy["guest_tools"])
        denied = []

        lowered = request_text.lower()
        approval_followup = lowered.strip() in {"i approve it", "approved", "yes approve", "i approve", "go ahead"}
        if any(marker in lowered for marker in SENSITIVE_TOOL_MARKERS) or (lane == "TRADING_STATION" and approval_followup):
            denied.append("sensitive_tool_action_blocked_from_normal_chat")
            tools = []
        if lane == "TRADING_STATION" and not trusted:
            denied.append("trusted_authority_required_for_veritas_status")
        if lane == "LEGAL_CASE" and any(marker in lowered for marker in ["file a motion", "submit filing", "e-file", "efile"]):
            denied.append("legal_filing_blocked_from_normal_chat")
        if lane == "SENSITIVE_ACTION":
            denied.append("sensitive_action_requires_step_up_path")

        capsule = AuthorityCapsule(
            capsule_id=f"cap_{uuid.uuid4().hex[:16]}",
            subject_user_id=str(user_id or "guest"),
            role=role,
            session_id=str(session_id or "session"),
            device_id=str(device_id) if device_id else None,
            lane=lane,
            purpose="governed_runtime_request",
            request_hash=DiodeProtocol.request_hash(request_text),
            allowed_memory_scopes=scopes,
            allowed_tools=tools,
            auth_strength="trusted_device_demo" if trusted else "guest_public",
            risk_level=risk_level,
            issued_at=time.time(),
            expires_at=time.time() + (300 if trusted else 120),
            diode_redacted=(request_text != str(metadata.get("raw_request_text") or request_text)),
        )
        signed = self.signer.sign(capsule)
        return BrokerDecision(capsule=capsule, token=signed, trusted=trusted, denied_reasons=denied, demo_mode=self.signer.demo_mode)
