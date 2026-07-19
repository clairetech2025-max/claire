from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_doc(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_deployment_docs_require_source_identity_health_gate() -> None:
    combined = "\n".join(
        [
            read_doc("DEPLOYMENT.md"),
            read_doc("RECOVERY.md"),
            read_doc("scripts/deploy/README.md"),
            read_doc("docs/HUGGING_FACE_DEPLOYMENT_STATUS.md"),
        ]
    )

    assert "--expected-source-sha" in combined
    assert "--expected-source-ref" in combined
    assert "--expected-included-source-sha" in combined
    assert "--github-repo clairetech2025-max/claire" in combined
    assert "--require-github-secret HF_TOKEN" in combined
    assert "deployment.source_git_sha" in combined
    assert "deployment.included_sources" in combined
    assert "stale Space" in combined or "stale deployment" in combined


def test_deployment_docs_preserve_azure_and_secret_boundaries() -> None:
    combined = "\n".join(
        [
            read_doc("DEPLOYMENT.md"),
            read_doc("RECOVERY.md"),
            read_doc("scripts/deploy/README.md"),
        ]
    )

    assert "Azure remains" in combined
    assert "HF_TOKEN" in combined
    assert "Do not expose or print secret values" in combined
    assert "Do not deploy private databases" in combined
