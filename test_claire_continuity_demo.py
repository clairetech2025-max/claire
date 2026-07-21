from __future__ import annotations

import json
from pathlib import Path

from claire_continuity.core import (
    ContinuityWorkspace,
    admit_capsule_metadata_to_are,
    canonical_json,
    demo_collaboration_profile,
    demo_session_capsule,
    find_are_record_by_hash,
    redact_capsule,
    render_handoff_markdown,
    stable_hash,
    validate_capsule,
    verify_artifact_hash,
)
from claire_are import AREStore
from claire_are.config import AREConfig


def test_deterministic_json_serialization_and_stable_hashing():
    left = {"b": 2, "a": {"z": 1, "y": [3, 2, 1]}}
    right = {"a": {"y": [3, 2, 1], "z": 1}, "b": 2}

    assert canonical_json(left) == canonical_json(right)
    assert stable_hash(left) == stable_hash(right)
    assert verify_artifact_hash(left, stable_hash(left))


def test_redaction_and_private_shareable_separation():
    capsule = demo_session_capsule(demo_collaboration_profile())
    shareable = redact_capsule(capsule)
    encoded = canonical_json(shareable)

    assert "private_trust_notes" not in shareable
    assert "synthetic_sensitive_examples" not in shareable
    assert "sk-proj-DEMOSECRET" not in encoded
    assert "hf_DEMOSECRET" not in encoded
    assert "831-555-0123" not in encoded
    assert "private.person@example.com" not in encoded
    assert "123 Private Ranch Road" not in encoded
    assert "BATTLEBORN_TESTSECRET" not in encoded
    assert "Doe v. Roe" not in encoded
    assert "[REDACTED_BY_DIODE]" in encoded or "omitted" in encoded


def test_capsule_validation_and_handoff_content_requirements():
    capsule = redact_capsule(demo_session_capsule(demo_collaboration_profile()))
    validate_capsule(capsule)
    handoff = render_handoff_markdown(capsule)

    required = [
        "Identity / Collaboration Contract",
        "Current Project State",
        "Restore Point",
        "Next Safe Step",
        "Failures",
        "Do Not Repeat",
        "Shared Vocabulary",
        "Active Tasks",
        "Current Priority",
        "Verified Important Facts",
        "Do not invent missing memory",
    ]
    for text in required:
        assert text in handoff


def test_prior_hash_chaining_is_preserved_in_shareable_capsule():
    capsule = demo_session_capsule(demo_collaboration_profile())
    capsule["previous_capsule_hash"] = "abc123previous"
    shareable = redact_capsule(capsule)

    assert shareable["previous_capsule_hash"] == "abc123previous"


def test_are_metadata_only_admission_and_readback(tmp_path):
    capsule = redact_capsule(demo_session_capsule(demo_collaboration_profile()))
    artifact_hash = stable_hash(capsule)
    provenance = admit_capsule_metadata_to_are(
        capsule,
        artifact_hash=artifact_hash,
        source_filename="session_capsule.shareable.json",
        are_root=tmp_path / "are",
    )

    store = AREStore(AREConfig(root=tmp_path / "are", hmac_key=b"local-dev-claire-are-key"))
    envelope = find_are_record_by_hash(store, artifact_hash)
    verify = store.verify()
    store.stop()

    assert envelope is not None
    payload = envelope["payload"]
    metadata = payload["metadata"]
    assert metadata["artifact_hash"] == artifact_hash
    assert metadata["capsule_id"] == capsule["capsule_id"]
    assert "collaboration_profile" not in metadata
    assert "private_trust_notes" not in json.dumps(metadata)
    assert payload["text"] == metadata["redacted_short_summary"]
    assert provenance.are_verification_status["record_exists"] is True
    assert provenance.are_verification_status["hash_matches"] is True
    assert verify["valid"] is True


def test_demo_generates_required_files_and_manifest(tmp_path):
    result = ContinuityWorkspace(tmp_path / "continuity_demo").create_demo(
        admit_to_are=True,
        are_root=tmp_path / "are",
    )
    root = tmp_path / "continuity_demo"
    expected = [
        "collaboration_profile.private.json",
        "session_capsule.private.json",
        "session_capsule.private.md",
        "session_capsule.shareable.json",
        "session_capsule.shareable.md",
        "session_capsule.handoff.md",
        "session_capsule.provenance.json",
    ]
    for name in expected:
        assert (root / name).exists(), name

    shareable = json.loads((root / "session_capsule.shareable.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "session_capsule.provenance.json").read_text(encoding="utf-8"))
    handoff = (root / "session_capsule.handoff.md").read_text(encoding="utf-8")

    assert result["artifact_hash"] == stable_hash(shareable)
    assert manifest["hash_verified"] is True
    assert manifest["artifact_hash"] == result["artifact_hash"]
    assert manifest["are"]["are_verification_status"]["record_exists"] is True
    assert "private_trust_notes" not in canonical_json(shareable)
    assert "Do not invent missing memory" in handoff
    assert "Preserve accumulated collaboration intelligence" in handoff
    assert "model consciousness" in handoff
