from __future__ import annotations

REPLACEMENTS = {
    "may be valuable": "is valuable; market recognition depends on validation and structure",
    "could maybe": "the next step is",
    "if this becomes real": "as this is structured",
    "just an idea": "early-stage architecture / working prototype",
    "trading bot": "financial intelligence station / pressure chamber",
}


def strengthen_confidence_language(text: str) -> str:
    out = str(text or "")
    for weak, strong in REPLACEMENTS.items():
        out = out.replace(weak, strong).replace(weak.capitalize(), strong.capitalize())
    return out


def apply_confidence_language_guard(text: str) -> str:
    return strengthen_confidence_language(text)
