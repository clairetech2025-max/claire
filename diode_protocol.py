from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class DiodeProtocol:
    """
    Diode rule: authority may flow forward as signed capsules; secrets must not
    flow backward into chat responses, model prompts, memory, trace, logs, or
    debug output.
    """

    REDACTION = "[REDACTED_BY_DIODE]"
    SECRET_PATTERNS = [
        re.compile(r"\bexecution\s+passphrase\s+(?:is|=|:)\s*\S+", re.I),
        re.compile(r"\b(passphrase|password|api\s*key|apikey|secret|token)\s*(?:is|=|:)?\s*['\"]?[A-Za-z0-9_\-./+=]{4,}", re.I),
        re.compile(r"\bbearer\s+[A-Za-z0-9_\-./+=]{8,}", re.I),
        re.compile(r"\bkraken[_\s-]*(?:api[_\s-]*)?(?:key|secret)\s*(?:is|=|:)?\s*['\"]?[A-Za-z0-9_\-./+=]{4,}", re.I),
        re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----.*?-----END\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.I | re.S),
        re.compile(r"\b[A-Z0-9_]*BATTLEBORN[A-Z0-9_\-]*\b", re.I),
    ]

    @classmethod
    def redact(cls, text: str) -> str:
        clean = str(text or "")
        for pattern in cls.SECRET_PATTERNS:
            clean = pattern.sub(cls.REDACTION, clean)
        return clean

    @classmethod
    def contains_secret(cls, text: str) -> bool:
        candidate = str(text or "")
        return any(pattern.search(candidate) for pattern in cls.SECRET_PATTERNS)

    @staticmethod
    def request_hash(text: str) -> str:
        return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()

    @classmethod
    def assert_trace_safe(cls, payload: dict[str, Any]) -> bool:
        encoded = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        if cls.contains_secret(encoded):
            return False
        return cls.REDACTION not in encoded or not cls.contains_secret(encoded.replace(cls.REDACTION, ""))
