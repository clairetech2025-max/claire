from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_MEMORY_PATHS = [
    Path(os.environ.get("CLAIRE_ORIGINAL_ARE_MEM_PATH", "")).expanduser()
    if os.environ.get("CLAIRE_ORIGINAL_ARE_MEM_PATH")
    else None,
    Path("/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl"),
    Path("/home/LuciusPrime/original_are.py/are_data/are_mem.jsonl"),
]


def candidate_memory_paths() -> list[Path]:
    paths: list[Path] = []
    for path in DEFAULT_MEMORY_PATHS:
        if path is not None and path not in paths:
            paths.append(path)
    return paths


def resolve_memory_path() -> Path | None:
    for path in candidate_memory_paths():
        if path.exists() and path.is_file():
            return path
    return None


def read_original_are_history(limit: int = 8, memory_path: str | Path | None = None) -> dict[str, Any]:
    memory_path = Path(memory_path) if memory_path is not None else resolve_memory_path()
    if memory_path is None:
        return {
            "status": "empty",
            "reason": "Original ARE memory file unavailable or empty; no prior chronological experience supplied.",
            "memory_file": "",
            "records": [],
            "quarantined_records": [],
        }

    try:
        lines = memory_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return {
            "status": "error",
            "reason": f"Original ARE memory file could not be read: {exc}",
            "memory_file": str(memory_path),
            "records": [],
            "quarantined_records": [],
        }

    if not lines:
        return {
            "status": "empty",
            "reason": "Original ARE memory file is empty; no prior chronological experience supplied.",
            "memory_file": str(memory_path),
            "records": [],
            "quarantined_records": [],
        }

    selected = lines[-max(limit, 0):]
    records: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    first_line_number = len(lines) - len(selected) + 1

    for offset, line in enumerate(selected):
        line_number = first_line_number + offset
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            quarantined.append(
                {
                    "line_number": line_number,
                    "reason": f"Malformed original ARE JSONL record: {exc}",
                    "raw": line,
                }
            )
            continue

        if not isinstance(parsed, dict):
            quarantined.append(
                {
                    "line_number": line_number,
                    "reason": "Original ARE JSONL record is not an object.",
                    "raw": line,
                }
            )
            continue

        text = parsed.get("text", "")
        if not isinstance(text, str):
            quarantined.append(
                {
                    "line_number": line_number,
                    "reason": "Original ARE record text is not a string.",
                    "raw": line,
                }
            )
            continue

        records.append(
            {
                "order": len(records) + 1,
                "line_number": line_number,
                "ts": parsed.get("ts"),
                "sha": str(parsed.get("sha", "")),
                "text": text,
            }
        )

    status = "ok"
    reason = "Original ARE chronological history supplied oldest to newest."
    if not records and quarantined:
        status = "quarantined"
        reason = "Only malformed original ARE records were found; no chronological experience supplied."
    elif quarantined:
        status = "partial"
        reason = "Original ARE chronological history supplied with malformed records quarantined."

    return {
        "status": status,
        "reason": reason,
        "memory_file": str(memory_path),
        "records": records,
        "quarantined_records": quarantined,
    }
