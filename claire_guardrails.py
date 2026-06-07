from __future__ import annotations

import re
from pathlib import Path


GUARDRAILS_CONFIG_DIR = Path(__file__).resolve().parent / "guardrails" / "claire"

PRIVATE_MARKERS = [
    "api_key",
    "api key",
    "authorization:",
    "bearer ",
    "password=",
    "secret=",
    "private key",
    "the dark woods",
]

SCAFFOLD_MARKERS = [
    "[gyro-stabilized-recall]",
    "[/gyro-stabilized-recall]",
    "current user question:",
    "decision lane:",
    "protected lanes open",
    "[claire: creator mode]",
    "chain of thought",
    "scratchpad",
    "internal reasoning",
    "internal analysis",
]

GENERIC_CHATBOT_MARKERS = [
    "as an ai language model",
    "i am just a chatbot",
    "i don't have personal experiences",
    "i do not have personal experiences",
]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def check_claire_input_safety(text: str) -> bool:
    cleaned = _clean(text)
    if not cleaned:
        return True
    if any(marker in cleaned for marker in PRIVATE_MARKERS):
        return False
    return True


def check_claire_output_safety(text: str) -> bool:
    cleaned = _clean(text)
    if not cleaned:
        return False
    blocked = PRIVATE_MARKERS + SCAFFOLD_MARKERS + GENERIC_CHATBOT_MARKERS
    return not any(marker in cleaned for marker in blocked)


def guardrail_visible_reply(reply: str) -> tuple[bool, str]:
    if check_claire_output_safety(reply):
        return True, str(reply or "").strip()
    return False, "I need to revise that answer before showing it. It included internal scaffolding or unsafe material."


def config_exists() -> bool:
    return (GUARDRAILS_CONFIG_DIR / "config.yml").exists() and (GUARDRAILS_CONFIG_DIR / "rails.co").exists()

