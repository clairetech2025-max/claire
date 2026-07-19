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


def test_readiness_workflow_is_manual_and_non_uploading() -> None:
    workflow = read_workflow("hf-deployment-readiness.yml")

    assert "workflow_dispatch:" in workflow
    assert "upload_hf_space.sh" not in workflow
    assert "hf upload" not in workflow
    assert "Upload performed: false" in workflow


def test_readiness_workflow_checks_required_deployment_inputs() -> None:
    workflow = read_workflow("hf-deployment-readiness.yml")

    assert "veritas_space_id" in workflow
    assert "approve_claire_sdk_transition" in workflow
    assert "HF_TOKEN_PRESENT" in workflow
    assert "--require-github-secret HF_TOKEN" in workflow
    assert "--report-only" in workflow


def test_readiness_workflow_builds_both_space_packages() -> None:
    workflow = read_workflow("hf-deployment-readiness.yml")

    assert "deploy/huggingface/claire.manifest.json /tmp/claire-hf-readiness" in workflow
    assert "deploy/huggingface/veritas.manifest.json /tmp/veritas-hf-readiness" in workflow
    assert "validate_hf_tree.py /tmp/claire-hf-readiness" in workflow
    assert "validate_hf_tree.py /tmp/veritas-hf-readiness" in workflow
    assert "hf_deploy_status.py" in workflow


def test_security_source_scan_workflow_runs_tracked_source_scanner() -> None:
    workflow = read_workflow("security-source-scan.yml")

    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "python scripts/security_scan.py" in workflow
    assert "upload_hf_space.sh" not in workflow
