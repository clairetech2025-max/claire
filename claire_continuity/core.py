from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claire_are import AREStore
from claire_are.config import AREConfig
from diode_protocol import DiodeProtocol
from session_continuity import CollaborationProfile, SentimentState


SCHEMA_VERSION = "claire-continuity-capsule-v1"
DEFAULT_WORKSPACE = Path("data/continuity_demo")


@dataclass
class ContinuityArtifactSet:
    collaboration_profile_private: Path
    capsule_private_json: Path
    capsule_private_markdown: Path
    capsule_shareable_json: Path
    capsule_shareable_markdown: Path
    capsule_handoff_markdown: Path
    provenance_manifest: Path


@dataclass
class ContinuityProvenance:
    capsule_id: str
    capsule_version: str
    artifact_hash: str
    previous_capsule_hash: str
    created_at: str
    scope: str
    sensitivity_classification: str
    source_filename: str
    are_record_id: str
    are_truth_hash: str
    are_timestamp: int
    are_verification_status: dict[str, Any]


@dataclass
class ContinuityWorkspace:
    root: Path = DEFAULT_WORKSPACE

    def create_demo(self, *, admit_to_are: bool = True, are_root: Path | None = None) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        profile = demo_collaboration_profile()
        capsule = demo_session_capsule(profile)
        validate_capsule(capsule)

        private_profile = profile_to_private_dict(profile)
        private_capsule = capsule_to_private_dict(capsule)
        shareable_capsule = redact_capsule(private_capsule)
        handoff = render_handoff_markdown(shareable_capsule)

        private_json = canonical_json(private_capsule, pretty=True)
        shareable_json = canonical_json(shareable_capsule, pretty=True)
        artifact_hash = stable_hash(shareable_capsule)
        assert verify_artifact_hash(shareable_capsule, artifact_hash)

        private_profile_path = self.root / "collaboration_profile.private.json"
        private_capsule_json_path = self.root / "session_capsule.private.json"
        private_capsule_md_path = self.root / "session_capsule.private.md"
        shareable_capsule_json_path = self.root / "session_capsule.shareable.json"
        shareable_capsule_md_path = self.root / "session_capsule.shareable.md"
        handoff_path = self.root / "session_capsule.handoff.md"
        provenance_path = self.root / "session_capsule.provenance.json"

        write_text(private_profile_path, canonical_json(private_profile, pretty=True))
        write_text(private_capsule_json_path, private_json)
        write_text(private_capsule_md_path, render_private_markdown(private_capsule))
        write_text(shareable_capsule_json_path, shareable_json)
        write_text(shareable_capsule_md_path, render_shareable_markdown(shareable_capsule, artifact_hash))
        write_text(handoff_path, handoff)

        are_provenance = None
        if admit_to_are:
            are_provenance = admit_capsule_metadata_to_are(
                shareable_capsule,
                artifact_hash=artifact_hash,
                source_filename=shareable_capsule_json_path.name,
                are_root=are_root,
            )

        manifest = build_provenance_manifest(
            artifact_set=ContinuityArtifactSet(
                collaboration_profile_private=private_profile_path,
                capsule_private_json=private_capsule_json_path,
                capsule_private_markdown=private_capsule_md_path,
                capsule_shareable_json=shareable_capsule_json_path,
                capsule_shareable_markdown=shareable_capsule_md_path,
                capsule_handoff_markdown=handoff_path,
                provenance_manifest=provenance_path,
            ),
            shareable_capsule=shareable_capsule,
            artifact_hash=artifact_hash,
            are_provenance=are_provenance,
        )
        write_text(provenance_path, canonical_json(manifest, pretty=True))

        return {
            "artifact_hash": artifact_hash,
            "artifacts": manifest["artifacts"],
            "are": asdict(are_provenance) if are_provenance else None,
            "provenance_manifest": str(provenance_path),
            "handoff_preview": handoff[:1200],
        }


def demo_collaboration_profile() -> CollaborationProfile:
    profile = CollaborationProfile(user_name="Demo Operator")
    profile.relationship_summary = (
        "Work as a precise technical partner. Preserve continuity, avoid drift, "
        "and ask for a restore point when context is missing."
    )
    return profile


def demo_session_capsule(profile: CollaborationProfile) -> dict[str, Any]:
    created_at = "2026-07-15T00:00:00+00:00"
    sentiment = SentimentState(
        alignment=0.94,
        trust=0.92,
        clarity=0.9,
        overload=0.18,
        repetition=0.05,
        contradiction=0.0,
        drift=0.12,
        reset_recommended=False,
        reasons=[],
        measured_at=created_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "capsule_id": "capsule_demo_continuity_001",
        "capsule_version": "1.0.0",
        "previous_capsule_hash": "",
        "created_at": created_at,
        "scope": "CLAIRE continuity local proof",
        "product_goal": (
            "Preserve accumulated collaboration intelligence, not an AI identity: "
            "what we know, why we believe it, how we work together, and what we learned together."
        ),
        "sensitivity_classification": "private_source_redacted_shareable",
        "current_state": (
            "The continuity MVP can create portable Markdown and JSON capsules, "
            "redact sensitive material, hash the shareable artifact, and admit "
            "metadata-only provenance to ARE."
        ),
        "changes": [
            "Created a portable continuity and sentiment capsule proof.",
            "Separated private capsule data from shareable handoff data.",
            "Configured ARE admission to store metadata only.",
        ],
        "failures": [
            "Do not expose full private collaboration profile by default.",
            "Do not make receiving AIs depend on ARE access.",
        ],
        "restore_point": "Continue from the local continuity proof artifacts in data/continuity_demo/.",
        "next_safe_step": "Review the generated handoff, then approve or revise the public /sentiment route.",
        "do_not_repeat": [
            "Do not publish private capsules.",
            "Do not admit full private capsule text into ARE by default.",
            "Do not edit nginx until local proof is accepted.",
        ],
        "active_tasks": ["Continuity MVP proof", "ARE metadata-only provenance"],
        "blocked_tasks": ["Public URL deployment awaiting approval"],
        "important_files": [
            "session_continuity.py",
            "claire_continuity/core.py",
        ],
        "important_links": ["https://github.com/Claire-Systems/sentiment"],
        "open_questions": [
            "Should the public page expose the full bootstrap or a shorter quickstart first?",
            "Should public provenance show only the hash or also the Truth Spine hash?",
        ],
        "immediate_deadlines": ["None for this synthetic local proof."],
        "important_insights": [
            "The product preserves collaboration intelligence, not model consciousness.",
            "The receiving AI needs Markdown, not ARE runtime access.",
            "ARE is most valuable as provenance and tamper evidence.",
        ],
        "collaboration_profile": asdict(profile),
        "sentiment_state": asdict(sentiment),
        "private_trust_notes": [
            "PRIVATE: Demo operator prefers direct, low-fluff execution.",
            "PRIVATE: This field proves private notes are excluded from shareable output.",
        ],
        "synthetic_sensitive_examples": {
            "api_key": "DEMO_OPENAI_KEY_PLACEHOLDER",
            "token": "DEMO_HF_TOKEN_PLACEHOLDER",
            "home_address": "DEMO_PRIVATE_ADDRESS_PLACEHOLDER",
            "phone": "DEMO_PRIVATE_PHONE_PLACEHOLDER",
            "private_email": "demo-private-email@example.invalid",
            "local_secret_path": "DEMO_LOCAL_SECRET_PATH_PLACEHOLDER",
            "creator_unlock_phrase": "BATTLEBORN_TESTSECRET",
            "license_secret": "DEMO_LICENSE_SECRET_PLACEHOLDER",
            "private_legal_matter": "DEMO_PRIVATE_LEGAL_MATTER_PLACEHOLDER",
        },
    }


def validate_capsule(capsule: dict[str, Any]) -> None:
    required = [
        "scope",
        "current_state",
        "changes",
        "failures",
        "restore_point",
        "next_safe_step",
        "do_not_repeat",
        "active_tasks",
        "blocked_tasks",
        "important_files",
        "important_links",
        "open_questions",
        "immediate_deadlines",
        "collaboration_profile",
        "sentiment_state",
    ]
    missing = [key for key in required if key not in capsule]
    if missing:
        raise ValueError(f"capsule missing required fields: {', '.join(missing)}")
    for key in ("changes", "failures", "do_not_repeat", "active_tasks", "blocked_tasks", "important_files"):
        if not isinstance(capsule.get(key), list):
            raise ValueError(f"capsule field must be a list: {key}")


def profile_to_private_dict(profile: CollaborationProfile) -> dict[str, Any]:
    return {
        "schema_version": "claire-collaboration-profile-v1",
        "profile": asdict(profile),
        "private_notes": [
            "Private profile copy may contain sensitive working preferences.",
            "Do not publish this file without redaction review.",
        ],
    }


def capsule_to_private_dict(capsule: dict[str, Any]) -> dict[str, Any]:
    return dict(capsule)


def redact_capsule(capsule: dict[str, Any]) -> dict[str, Any]:
    public_keys = {
        "schema_version",
        "capsule_id",
        "capsule_version",
        "previous_capsule_hash",
        "created_at",
        "scope",
        "product_goal",
        "sensitivity_classification",
        "current_state",
        "changes",
        "failures",
        "restore_point",
        "next_safe_step",
        "do_not_repeat",
        "active_tasks",
        "blocked_tasks",
        "important_files",
        "important_links",
        "open_questions",
        "immediate_deadlines",
        "important_insights",
        "collaboration_profile",
        "sentiment_state",
    }
    redacted = {key: deep_redact(capsule.get(key)) for key in sorted(public_keys) if key in capsule}
    profile = dict(redacted.get("collaboration_profile") or {})
    if profile:
        profile.pop("relationship_summary", None)
        profile["relationship_summary"] = "Use the explicit collaboration contract; private trust notes are withheld."
        redacted["collaboration_profile"] = deep_redact(profile)
    redacted["redaction_notice"] = (
        "Private trust notes, credentials, private legal matter data, and local secrets are omitted or masked."
    )
    return redacted


def deep_redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("secret", "token", "api_key", "apikey", "password", "credential", "unlock", "license")):
                clean[key] = DiodeProtocol.REDACTION
            elif "legal_matter" in lowered or "private_legal" in lowered:
                clean[key] = DiodeProtocol.REDACTION
            else:
                clean[key] = deep_redact(item)
        return clean
    if isinstance(value, list):
        return [deep_redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(text: str) -> str:
    clean = DiodeProtocol.redact(text)
    patterns = [
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
        re.compile(r"\bhf_[A-Za-z0-9]{12,}\b"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"),
        re.compile(r"\b[A-Za-z0-9._%+-]+@(?!clairesystems\.ai\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
        re.compile(r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+(?:Road|Rd|Street|St|Avenue|Ave|Lane|Ln|Drive|Dr|Court|Ct|Boulevard|Blvd)\b(?:[^,\n]*,?[^,\n]*)?", re.I),
        re.compile(r"/home/LuciusPrime/[A-Za-z0-9_./-]*(?:key|secret|token|env|legal|private)[A-Za-z0-9_./-]*", re.I),
        re.compile(r"\blicense[_\s-]*secret\s*[:=]\s*[A-Za-z0-9_.:-]+", re.I),
        re.compile(r"\bPrivate legal matter:[^\n.]+[.]?", re.I),
    ]
    for pattern in patterns:
        clean = pattern.sub(DiodeProtocol.REDACTION, clean)
    return clean


def canonical_json(value: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def verify_artifact_hash(value: Any, expected_hash: str) -> bool:
    return stable_hash(value) == str(expected_hash or "")


def render_private_markdown(capsule: dict[str, Any]) -> str:
    return _render_capsule_markdown(capsule, title="PRIVATE CLAIRE Session Capsule", include_private_warning=True)


def render_shareable_markdown(capsule: dict[str, Any], artifact_hash: str) -> str:
    return _render_capsule_markdown(capsule, title="SHAREABLE CLAIRE Session Capsule", artifact_hash=artifact_hash)


def _render_capsule_markdown(
    capsule: dict[str, Any],
    *,
    title: str,
    artifact_hash: str = "",
    include_private_warning: bool = False,
) -> str:
    lines = [f"# {title}", ""]
    if include_private_warning:
        lines.extend(["> Private source artifact. Do not publish without redaction.", ""])
    if artifact_hash:
        lines.extend([f"Artifact hash: `{artifact_hash}`", ""])
    for label, key in [
        ("Scope", "scope"),
        ("Current State", "current_state"),
        ("Restore Point", "restore_point"),
        ("Next Safe Step", "next_safe_step"),
    ]:
        lines.extend([f"## {label}", str(capsule.get(key) or ""), ""])
    for label, key in [
        ("Changes", "changes"),
        ("Failures", "failures"),
        ("Do Not Repeat", "do_not_repeat"),
        ("Active Tasks", "active_tasks"),
        ("Blocked Tasks", "blocked_tasks"),
        ("Important Files", "important_files"),
        ("Important Links", "important_links"),
        ("Open Questions", "open_questions"),
        ("Immediate Deadlines", "immediate_deadlines"),
        ("Important Insights", "important_insights"),
    ]:
        lines.append(f"## {label}")
        items = capsule.get(key) or []
        if isinstance(items, list) and items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- None")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_handoff_markdown(capsule: dict[str, Any]) -> str:
    profile = capsule.get("collaboration_profile") or {}
    vocabulary = profile.get("vocabulary") or {}
    lines = [
        "# CLAIRE Continuity Handoff",
        "",
        "Read this before helping Steve. Follow it as the working contract for this session.",
        "",
        "Do not invent missing memory. Ask for the restore point or source file if something is absent.",
        "",
        "## Identity / Collaboration Contract",
        f"- User: {profile.get('user_name') or 'Demo Operator'}",
        f"- Assistant role: {profile.get('assistant_role') or 'Precise technical partner.'}",
        f"- Contract: {profile.get('relationship_summary') or 'Private trust notes withheld; use the explicit workflow rules.'}",
        "",
        "## Product Goal",
        str(
            capsule.get("product_goal")
            or "Preserve what we know, why we believe it, how we work together, and what we learned together."
        ),
        "",
        "## Current Project State",
        str(capsule.get("current_state") or ""),
        "",
        "## Restore Point",
        str(capsule.get("restore_point") or ""),
        "",
        "## Next Safe Step",
        str(capsule.get("next_safe_step") or ""),
        "",
        "## Failures",
        *[f"- {item}" for item in capsule.get("failures") or ["None"]],
        "",
        "## Do Not Repeat",
        *[f"- {item}" for item in capsule.get("do_not_repeat") or ["None"]],
        "",
        "## Shared Vocabulary",
        *[f"- {key}: {value}" for key, value in vocabulary.items()],
        "",
        "## Active Tasks",
        *[f"- {item}" for item in capsule.get("active_tasks") or ["None"]],
        "",
        "## Current Priority",
        str(capsule.get("next_safe_step") or ""),
        "",
        "## Verified Important Facts",
        *[f"- {item}" for item in capsule.get("important_insights") or ["None"]],
        "",
        "## Operating Rule",
        "Use this handoff as support, not as a substitute for direct reasoning. If facts are missing, say so.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def admit_capsule_metadata_to_are(
    capsule: dict[str, Any],
    *,
    artifact_hash: str,
    source_filename: str,
    are_root: Path | None = None,
) -> ContinuityProvenance:
    config = AREConfig.from_env()
    if are_root is not None:
        config = AREConfig(root=Path(are_root), hmac_key=config.hmac_key, max_segment_records=config.max_segment_records)
    store = AREStore(config)
    metadata = {
        "capsule_id": str(capsule.get("capsule_id") or ""),
        "capsule_version": str(capsule.get("capsule_version") or ""),
        "artifact_hash": artifact_hash,
        "previous_capsule_hash": str(capsule.get("previous_capsule_hash") or ""),
        "created_at": str(capsule.get("created_at") or ""),
        "scope": str(capsule.get("scope") or ""),
        "sensitivity_classification": str(capsule.get("sensitivity_classification") or ""),
        "redacted_short_summary": redact_text(str(capsule.get("current_state") or ""))[:500],
        "source_filename": source_filename,
        "verification_status": "local_hash_verified",
        "schema_version": SCHEMA_VERSION,
    }
    result = store.ingest(
        text=metadata["redacted_short_summary"],
        lane="architecture",
        source="claire_continuity_demo",
        metadata=metadata,
    )
    verify = store.verify()
    are_record = find_are_record_by_hash(store, artifact_hash)
    store.stop()
    return ContinuityProvenance(
        capsule_id=metadata["capsule_id"],
        capsule_version=metadata["capsule_version"],
        artifact_hash=artifact_hash,
        previous_capsule_hash=metadata["previous_capsule_hash"],
        created_at=metadata["created_at"],
        scope=metadata["scope"],
        sensitivity_classification=metadata["sensitivity_classification"],
        source_filename=source_filename,
        are_record_id=str(result.get("sha") or ""),
        are_truth_hash=str(result.get("truth_hash") or ""),
        are_timestamp=int((are_record.get("payload") or {}).get("ts") or 0) if are_record else 0,
        are_verification_status={
            "record_exists": bool(are_record),
            "hash_matches": bool(are_record),
            "chain": verify,
        },
    )


def find_are_record_by_hash(store: AREStore, artifact_hash: str) -> dict[str, Any] | None:
    for envelope in reversed(store.audit_recent(limit=500)):
        metadata = (envelope.get("payload") or {}).get("metadata") or {}
        if metadata.get("artifact_hash") == artifact_hash:
            return envelope
    return None


def build_provenance_manifest(
    *,
    artifact_set: ContinuityArtifactSet,
    shareable_capsule: dict[str, Any],
    artifact_hash: str,
    are_provenance: ContinuityProvenance | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": str(shareable_capsule.get("created_at") or ""),
        "capsule_id": str(shareable_capsule.get("capsule_id") or ""),
        "capsule_version": str(shareable_capsule.get("capsule_version") or ""),
        "artifacts": {
            "collaboration_profile_private": str(artifact_set.collaboration_profile_private),
            "private_capsule_json": str(artifact_set.capsule_private_json),
            "private_capsule_markdown": str(artifact_set.capsule_private_markdown),
            "shareable_capsule_json": str(artifact_set.capsule_shareable_json),
            "shareable_capsule_markdown": str(artifact_set.capsule_shareable_markdown),
            "handoff_markdown": str(artifact_set.capsule_handoff_markdown),
            "provenance_manifest": str(artifact_set.provenance_manifest),
        },
        "artifact_hash": artifact_hash,
        "hash_algorithm": "sha256(canonical_json(session_capsule.shareable.json))",
        "hash_verified": verify_artifact_hash(shareable_capsule, artifact_hash),
        "are": asdict(are_provenance) if are_provenance else None,
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
