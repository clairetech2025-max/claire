from pathlib import Path

import claire_odyssey_mind as mind


def test_profile_specific_mind_wins(monkeypatch, tmp_path):
    config_dir = tmp_path / "configs"
    minds_dir = config_dir / "minds"
    minds_dir.mkdir(parents=True)
    (config_dir / "claire_mind.txt").write_text("default mind", encoding="utf-8")
    (minds_dir / "founder.txt").write_text("founder mind", encoding="utf-8")

    monkeypatch.setattr(mind, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(mind, "MINDS_DIR", minds_dir)
    monkeypatch.setattr(mind, "DEFAULT_MIND_FILE", config_dir / "claire_mind.txt")
    monkeypatch.setenv("CLAIRE_PROFILE", "Founder")

    assert mind.active_profile_name() == "founder"
    assert mind.load_claire_mind_text() == "founder mind"


def test_default_mind_fallback(monkeypatch, tmp_path):
    config_dir = tmp_path / "configs"
    minds_dir = config_dir / "minds"
    minds_dir.mkdir(parents=True)
    (config_dir / "claire_mind.txt").write_text("default mind", encoding="utf-8")

    monkeypatch.setattr(mind, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(mind, "MINDS_DIR", minds_dir)
    monkeypatch.setattr(mind, "DEFAULT_MIND_FILE", config_dir / "claire_mind.txt")
    monkeypatch.setenv("CLAIRE_PROFILE", "missing")

    assert mind.load_claire_mind_text() == "default mind"


def test_hardcoded_fallback(monkeypatch, tmp_path):
    config_dir = tmp_path / "missing-configs"
    minds_dir = config_dir / "minds"

    monkeypatch.setattr(mind, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(mind, "MINDS_DIR", minds_dir)
    monkeypatch.setattr(mind, "DEFAULT_MIND_FILE", config_dir / "claire_mind.txt")
    monkeypatch.delenv("CLAIRE_PROFILE", raising=False)

    assert mind.load_claire_mind_text() == mind.FALLBACK_IDENTITY


def test_describe_boot_state(monkeypatch, tmp_path):
    config_dir = Path(tmp_path) / "configs"
    minds_dir = config_dir / "minds"

    monkeypatch.setattr(mind, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(mind, "MINDS_DIR", minds_dir)

    banner = mind.describe_boot_state("test-model", profile="advocate")

    assert "Claire Odyssey" in banner
    assert "Active profile   : advocate" in banner
    assert "Model            : test-model" in banner
    assert str(config_dir) in banner
    assert str(minds_dir) in banner
