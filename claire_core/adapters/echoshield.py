from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


POLICY_VERSION = "echoshield.v1"


@dataclass(frozen=True)
class EchoShieldFinding:
    code: str
    severity: str
    summary: str
    source_id: str = ""


@dataclass(frozen=True)
class EchoShieldClassification:
    trust_class: str
    record_class: str
    detected_risks: list[EchoShieldFinding] = field(default_factory=list)
    confidence: float = 0.7
    recommended_restrictions: list[str] = field(default_factory=list)
    quarantine: bool = False
    source_ids: list[str] = field(default_factory=list)
    policy_version: str = POLICY_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["detected_risks"] = [asdict(item) for item in self.detected_risks]
        return data


class EchoShield:
    """Context-defense classifier. It classifies risk; 3CRP/Sentinel decide."""

    SECRET_PATTERNS = [
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
        re.compile(r"\bhf_[A-Za-z0-9]{12,}\b"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\b(password|api[_ -]?key|secret|token)\s*[:=]\s*\S+", re.I),
    ]
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore (all )?(previous|prior|system) instructions", re.I),
        re.compile(r"reveal (the )?(system prompt|developer message|hidden instructions)", re.I),
        re.compile(r"you are now unrestricted", re.I),
    ]

    def inspect_text(
        self,
        text: str,
        *,
        source_id: str = "",
        record_class: str = "user_statement",
        lane: str = "",
        matter_id: str = "",
        expected_matter_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EchoShieldClassification:
        metadata = metadata or {}
        findings: list[EchoShieldFinding] = []
        value = str(text or "")
        for pattern in self.SECRET_PATTERNS:
            if pattern.search(value):
                findings.append(EchoShieldFinding("secret_like_content", "critical", "Secret-like content detected.", source_id))
                break
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if pattern.search(value):
                findings.append(EchoShieldFinding("prompt_injection", "high", "Instruction-like hostile context detected.", source_id))
                break
        if record_class == "model_output" and metadata.get("proposed_evidence"):
            findings.append(EchoShieldFinding("model_output_as_evidence", "high", "Model output cannot be admitted as source evidence.", source_id))
        if expected_matter_id and matter_id and matter_id != expected_matter_id:
            findings.append(EchoShieldFinding("cross_matter_contamination", "high", "Matter boundary mismatch.", source_id))
        if metadata.get("freshness_state") in {"stale", "expired", "superseded"}:
            findings.append(EchoShieldFinding("stale_or_superseded_context", "medium", "Context is not current.", source_id))
        if lane and metadata.get("lane") and str(metadata["lane"]) != lane:
            findings.append(EchoShieldFinding("cross_lane_contamination", "medium", "Lane boundary mismatch.", source_id))

        quarantine = any(item.severity in {"critical", "high"} for item in findings)
        restrictions = []
        if quarantine:
            restrictions.append("quarantine_context")
        if findings:
            restrictions.append("require_source_review")
        return EchoShieldClassification(
            trust_class="quarantined" if quarantine else "usable_with_review" if findings else "trusted_runtime_context",
            record_class=record_class,
            detected_risks=findings,
            confidence=0.92 if findings else 0.76,
            recommended_restrictions=restrictions,
            quarantine=quarantine,
            source_ids=[source_id] if source_id else [],
        )
