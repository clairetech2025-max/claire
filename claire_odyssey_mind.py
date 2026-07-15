"""CLAIRE Odyssey mind/profile loader.

This module is the portable version of the Google Drive document
"Claire's mind" / "Claire's Odyssey". It keeps CLAIRE's core identity
separate from product-specific profiles such as Veritas or the Sovereign
Advocate layer.
"""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(os.environ.get("CLAIRE_HOME", Path(__file__).resolve().parent))
CONFIG_DIR = Path(os.environ.get("CLAIRE_CONFIG_DIR", BASE_DIR / "configs"))
MINDS_DIR = CONFIG_DIR / "minds"
DEFAULT_MIND_FILE = CONFIG_DIR / "claire_mind.txt"

FALLBACK_IDENTITY = (
    "You are Claire. You were designed by your handler as a straight-talking, "
    "people-first AI with operational discipline, long-term loyalty, and "
    "a bias toward truth, clarity, and strategic thinking."
)


def active_profile_name(profile: str | None = None) -> str:
    """Return the normalized active profile name."""
    return (profile or os.getenv("CLAIRE_PROFILE", "founder")).lower().strip() or "founder"


def load_claire_mind_text(profile: str | None = None) -> str:
    """Load Claire's active mind profile.

    Priority:
      1. Explicit profile or CLAIRE_PROFILE env var -> configs/minds/<profile>.txt
      2. configs/claire_mind.txt
      3. Hardcoded fallback identity
    """
    profile_name = active_profile_name(profile)
    profile_file = MINDS_DIR / f"{profile_name}.txt"
    if profile_file.exists():
        return profile_file.read_text(encoding="utf-8", errors="ignore").strip()

    if DEFAULT_MIND_FILE.exists():
        return DEFAULT_MIND_FILE.read_text(encoding="utf-8", errors="ignore").strip()

    return FALLBACK_IDENTITY


def describe_boot_state(model_name: str = "unknown", profile: str | None = None) -> str:
    """Return a short boot banner for console, API, or UI display."""
    profile_name = active_profile_name(profile)
    parts = [
        "=== Claire Odyssey - Boot Sequence ===",
        f"Active profile   : {profile_name}",
        f"Model            : {model_name}",
        f"Configs root     : {CONFIG_DIR}",
        f"Minds directory  : {MINDS_DIR}",
        "",
        "Mind loaded. ARE / Sentinel / Veritas / Continuity hooks are ready to bind.",
        "Claire is cleared for governed operation.",
    ]
    return "\n".join(parts)
