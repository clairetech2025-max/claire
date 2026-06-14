from __future__ import annotations

import re


def nvidia_constraints() -> list[str]:
    return [
        "Speak like an engineer-facing founder system.",
        "Avoid hype and avoid weak self-defeating language.",
        "Emphasize reproducibility: repo, commit SHA, startup commands, benchmark/demo, validation output.",
        "Keep internal gate labels out of the user-facing answer.",
        "Frame CLAIRE as governed runtime, not chatbot.",
        "Frame Veritas as pressure chamber / financial intelligence station, not gambling bot.",
        "Frame horses as mission origin and central assets, not distraction.",
    ]


def apply_nvidia_mode(answer: str) -> str:
    text = str(answer or "")
    text = re.sub(r"(?im)^\s*Technical gate\s*[:=].*$", "", text)
    text = re.sub(r"(?i)\bTechnical gate\s*[:=]\s*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
