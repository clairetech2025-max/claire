from pathlib import Path


def test_public_demo_startup_does_not_hard_require_provider_secret() -> None:
    script = Path(__file__).resolve().parents[1] / "hf_claire_runtime_full" / "start.sh"
    content = script.read_text(encoding="utf-8")

    assert "${NVIDIA_API_KEY:?" not in content
    assert "${CLAIRELLAMA:?" not in content
