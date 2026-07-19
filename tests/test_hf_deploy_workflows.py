from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_deploy_workflows_default_to_authoritative_main() -> None:
    claire = read_workflow("deploy-claire-hf.yml")
    veritas = read_workflow("deploy-veritas-hf.yml")

    assert 'default: "main"' in claire
    assert 'default: "main"' in veritas
    assert "codex/claire-core-completion-20260718" not in claire
    assert "codex/claire-core-completion-20260718" not in veritas


def test_deploy_workflows_keep_required_hf_gates() -> None:
    claire = read_workflow("deploy-claire-hf.yml")
    veritas = read_workflow("deploy-veritas-hf.yml")

    assert "HF_TOKEN secret is required" in claire
    assert "HF_TOKEN secret is required" in veritas
    assert "HF_APPROVE_SDK_TRANSITION" in claire
    assert "approve_sdk_transition" in claire
    assert "space_id" in veritas


def test_deploy_workflows_wait_for_space_health_after_upload() -> None:
    claire = read_workflow("deploy-claire-hf.yml")
    veritas = read_workflow("deploy-veritas-hf.yml")

    assert "hf_wait_for_space.py" in claire
    assert "hf_wait_for_space.py" in veritas
    assert "Wait for Space health" in claire
    assert "Wait for Space health" in veritas


def test_validate_workflow_runs_on_relevant_main_pushes() -> None:
    workflow = read_workflow("validate-hf-packages.yml")

    assert "push:" in workflow
    assert "branches:" in workflow
    assert "- main" in workflow
    assert "deploy/huggingface/**" in workflow
    assert "scripts/deploy/**" in workflow
