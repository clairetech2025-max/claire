from __future__ import annotations


def nvidia_constraints() -> list[str]:
    return [
        "Speak like an engineer-facing founder system.",
        "Avoid hype and avoid weak self-defeating language.",
        "Emphasize reproducibility: repo, commit, commands, benchmark, demo, validation.",
        "Separate business gate from technical gate.",
        "Frame CLAIRE as governed runtime, not chatbot.",
        "Frame Veritas as pressure chamber / financial intelligence station, not gambling bot.",
        "Frame horses as mission origin and central assets, not distraction.",
    ]


def apply_nvidia_mode(answer: str) -> str:
    required = "Technical gate: repo, commit, commands, benchmark, demo, and validation remain visible."
    text = str(answer or "")
    if required.lower() in text.lower():
        return text
    return f"{text}\n\n{required}"
