from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_files_exist():
    for rel in [
        "Dockerfile", "README.md", "start_hf_space.sh", ".dockerignore", ".env.example",
        "scripts/download_model.py", "scripts/healthcheck_llama.py", "scripts/healthcheck_claire.py",
        "demo_data/are_mem.jsonl",
    ]:
        assert (ROOT / rel).exists(), rel


def test_demo_are_history_is_sanitized_and_ordered():
    rows = [json.loads(line) for line in (ROOT / "demo_data/are_mem.jsonl").read_text().splitlines()]
    assert [r["sha"] for r in rows] == ["demo000001", "demo000002", "demo000003", "demo000004", "demo000005"]
    joined = "\n".join(r["text"] for r in rows).lower()
    for banned in ["steven roth", "seahorse", "federal complaint", "paloma", "spca", "california state parks", "monterey county", "sean james"]:
        assert banned not in joined


def test_no_model_weights_in_space_folder():
    forbidden = {".gguf", ".safetensors", ".bin"}
    for path in ROOT.rglob("*"):
        if path.is_file():
            assert path.suffix.lower() not in forbidden, path


def test_env_defaults_include_phi3_and_replaceable_profiles():
    env = (ROOT / ".env.example").read_text()
    assert "CLAIRE_PROVIDER=llama" in env
    assert "microsoft/Phi-3-mini-4k-instruct-gguf" in env
    assert "Phi-3-mini-4k-instruct-q4.gguf" in env
    assert "NVIDIA_API_KEY" in env
    assert "CLAIRE_GO_UPSTREAM_URL" in env


if __name__ == "__main__":
    test_required_files_exist()
    test_demo_are_history_is_sanitized_and_ordered()
    test_no_model_weights_in_space_folder()
    test_env_defaults_include_phi3_and_replaceable_profiles()
    print("hf_space_deployment_tests=ok")
