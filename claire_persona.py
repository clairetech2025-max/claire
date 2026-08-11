"""Versioned, provider-independent CLAIRE persona loading.

The canonical record is tracked configuration, never conversational memory.
Ordinary user input cannot write or replace it.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from diode_protocol import DiodeProtocol


SCHEMA = "claire.persona"
VERSION = 2
CANONICAL_EXPANSION = "Cognizant Lucid Autonomous Iterative Recall Environment"
DEFAULT_PERSONA_PATH = Path(__file__).resolve().parent / "configs" / "claire_persona.v2.json"
FORBIDDEN_KEYS = {"api_key", "token", "credential", "password", "secret", "creator_mode", "shell"}


def persona_path() -> Path:
    configured = os.environ.get("CLAIRE_PERSONA_PATH", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_PERSONA_PATH


def load_persona(path: str | Path | None = None) -> dict[str, Any]:
    selected = Path(path) if path is not None else persona_path()
    raw = json.loads(selected.read_text(encoding="utf-8"))
    if raw.get("schema") != SCHEMA or raw.get("version") != VERSION:
        raise ValueError("Unsupported CLAIRE persona schema or version")
    if raw.get("name") != "CLAIRE" or raw.get("canonical_expansion") != CANONICAL_EXPANSION:
        raise ValueError("CLAIRE canonical identity record is invalid")
    _validate_safe(raw)
    return deepcopy(raw)


def compact_persona(persona: dict[str, Any]) -> dict[str, Any]:
    """Return the bounded representation supplied to any model provider."""
    influences = []
    for category, entries in (persona.get("odyssey_influences") or {}).items():
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            lessons = [str(item).strip() for item in entry.get("lessons") or [] if str(item).strip()]
            if name and lessons:
                influences.append({"category": category, "name": name, "lessons": lessons})
    return {
        "schema": persona["schema"],
        "version": persona["version"],
        "name": persona["name"],
        "canonical_expansion": persona["canonical_expansion"],
        "role": persona["role"],
        "guiding_archetype": persona.get("guiding_archetype"),
        "core_traits": list(persona.get("core_traits") or []),
        "conversation_style": list(persona.get("conversation_style") or []),
        "decision_style": list(persona.get("decision_style") or []),
        "guiding_principles": list(persona.get("guiding_principles") or []),
        "odyssey_influences": influences,
        "influence_synthesis_rules": list(persona.get("influence_synthesis_rules") or []),
        "persona_source": list(persona.get("persona_source") or []),
    }


def canonical_identity_answer() -> str:
    return f"CLAIRE stands for {CANONICAL_EXPANSION}."


def is_expansion_question(text: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower())
    cleaned = " ".join(cleaned.split())
    return "what does claire stand for" in cleaned or "what is the expansion of claire" in cleaned


def _validate_safe(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_KEYS or any(part in normalized for part in ("api_key", "password", "credential")):
                raise ValueError(f"Forbidden persona field: {'.'.join((*path, str(key)))}")
            _validate_safe(item, (*path, str(key)))
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_safe(item, (*path, str(index)))
        return
    if isinstance(value, str):
        redacted = DiodeProtocol.redact(value)
        if redacted != value:
            raise ValueError(f"Secret-like material is prohibited in persona field: {'.'.join(path)}")
