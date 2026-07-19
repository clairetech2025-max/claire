from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "deploy"))

import build_hf_tree  # noqa: E402


def test_deployment_identity_uses_github_environment(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "clairetech2025-max/claire")

    identity = build_hf_tree.deployment_identity(
        {
            "application": "CLAIRE",
            "space_id": "Blackstormhorse/CLAIRE_Control_Interface",
        }
    )

    assert identity["schema_version"] == "claire-hf-deployment-identity.v1"
    assert identity["application"] == "CLAIRE"
    assert identity["source_git_sha"] == "abc123"
    assert identity["source_git_ref"] == "main"
    assert identity["source_repository"] == "clairetech2025-max/claire"
    assert identity["space_id"] == "Blackstormhorse/CLAIRE_Control_Interface"
    assert isinstance(identity["included_sources"], list)
    assert identity["build_timestamp_utc"].endswith("Z")


def test_deployment_identity_prefers_checked_out_source_environment(monkeypatch) -> None:
    monkeypatch.setenv("CLAIRE_SOURCE_SHA", "checkedout123")
    monkeypatch.setenv("CLAIRE_SOURCE_REF", "release-candidate")
    monkeypatch.setenv("GITHUB_SHA", "workflow456")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    identity = build_hf_tree.deployment_identity({"application": "CLAIRE"})

    assert identity["source_git_sha"] == "checkedout123"
    assert identity["source_git_ref"] == "release-candidate"
