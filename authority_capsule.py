from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from diode_protocol import DiodeProtocol


@dataclass
class AuthorityCapsule:
    capsule_id: str
    subject_user_id: str
    role: str
    session_id: str
    device_id: str | None
    lane: str
    purpose: str
    request_hash: str
    allowed_memory_scopes: list[str]
    allowed_tools: list[str]
    auth_strength: str
    risk_level: str
    issued_at: float
    expires_at: float
    diode_redacted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuthorityCapsuleSigner:
    def __init__(self, secret: str | None = None) -> None:
        env_secret = secret or os.getenv("HANDSHAKE_BROKER_SECRET", "")
        if env_secret:
            self.secret = env_secret.encode("utf-8")
            self.demo_mode = False
        else:
            self.secret = f"demo-{uuid.uuid4().hex}".encode("utf-8")
            self.demo_mode = True

    def sign(self, capsule: AuthorityCapsule) -> str:
        payload = capsule.to_dict()
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if DiodeProtocol.contains_secret(encoded):
            raise ValueError("authority capsule contains secret-like content")
        if "raw_prompt" in encoded or "prompt_text" in encoded:
            raise ValueError("authority capsule must not contain raw prompt text")
        payload_b64 = _b64(encoded.encode("utf-8"))
        signature = _b64(hmac.new(self.secret, payload_b64.encode("ascii"), hashlib.sha256).digest())
        return f"{payload_b64}.{signature}"

    def verify(
        self,
        token: str,
        expected_request_text: str | None = None,
        expected_lane: str | None = None,
    ) -> AuthorityCapsule | None:
        try:
            payload_b64, signature = str(token or "").split(".", 1)
        except ValueError:
            return None
        expected_sig = _b64(hmac.new(self.secret, payload_b64.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected_sig):
            return None
        try:
            payload = json.loads(_unb64(payload_b64).decode("utf-8"))
            capsule = AuthorityCapsule(**payload)
        except Exception:
            return None
        if capsule.expires_at <= time.time():
            return None
        if expected_request_text is not None and capsule.request_hash != DiodeProtocol.request_hash(expected_request_text):
            return None
        if expected_lane is not None and capsule.lane != expected_lane:
            return None
        encoded = json.dumps(capsule.to_dict(), ensure_ascii=False, sort_keys=True)
        if DiodeProtocol.contains_secret(encoded):
            return None
        return capsule


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
