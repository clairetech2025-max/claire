from __future__ import annotations

from typing import Any

from sentinel_validator import validate_response


def validate_bounded_response(answer: str, context_packet: dict[str, Any], lane: str) -> dict[str, Any]:
    return validate_response(answer, context_packet, lane)
