from __future__ import annotations

import json
import logging
import os
import time
import hashlib
from pathlib import Path
from typing import Any

ORIGINAL_ARE_CODE_PATH = Path("/home/LuciusPrime/original_are.pyiginal_are.py/are.py")
ORIGINAL_ARE_DIR = ORIGINAL_ARE_CODE_PATH.parent
ORIGINAL_ARE_MEM_PATH = ORIGINAL_ARE_DIR / "are_data" / "are_mem.jsonl"
LOGGER = logging.getLogger(__name__)

DEFAULT_MEMORY_PATHS = [
    Path(os.environ.get("CLAIRE_ORIGINAL_ARE_MEM_PATH", "")).expanduser()
    if os.environ.get("CLAIRE_ORIGINAL_ARE_MEM_PATH")
    else None,
    ORIGINAL_ARE_MEM_PATH,
    Path("/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl"),
    Path("/home/LuciusPrime/original_are.py/are_data/are_mem.jsonl"),
]


def candidate_memory_paths() -> list[Path]:
    paths: list[Path] = []
    for path in DEFAULT_MEMORY_PATHS:
        if path is not None and path not in paths:
            paths.append(path)
    return paths


def configured_memory_path() -> Path:
    if os.environ.get("CLAIRE_ORIGINAL_ARE_MEM_PATH"):
        path = Path(os.environ["CLAIRE_ORIGINAL_ARE_MEM_PATH"]).expanduser()
        LOGGER.info("Using CLAIRE_ORIGINAL_ARE_MEM_PATH=%s", path)
        return path
    LOGGER.info("Using verified original ARE memory path=%s", ORIGINAL_ARE_MEM_PATH)
    return ORIGINAL_ARE_MEM_PATH


def ensure_memory_file(path: str | Path | None = None) -> Path:
    memory_path = Path(path) if path is not None else configured_memory_path()
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.touch(exist_ok=True)
    LOGGER.info("Original ARE memory file ready: %s", memory_path)
    return memory_path


def resolve_memory_path(create: bool = False) -> Path | None:
    if os.environ.get("CLAIRE_ORIGINAL_ARE_MEM_PATH"):
        path = Path(os.environ["CLAIRE_ORIGINAL_ARE_MEM_PATH"]).expanduser()
        if create or not path.exists():
            return ensure_memory_file(path)
        LOGGER.info("Using CLAIRE_ORIGINAL_ARE_MEM_PATH=%s", path)
        return path if path.exists() and path.is_file() else None

    if create or not ORIGINAL_ARE_MEM_PATH.exists():
        return ensure_memory_file(ORIGINAL_ARE_MEM_PATH)
    return ORIGINAL_ARE_MEM_PATH if ORIGINAL_ARE_MEM_PATH.exists() and ORIGINAL_ARE_MEM_PATH.is_file() else None


def resolve_append_path(memory_path: str | Path | None = None) -> Path:
    if memory_path is not None:
        return ensure_memory_file(memory_path)
    return resolve_memory_path(create=True) or ensure_memory_file(ORIGINAL_ARE_MEM_PATH)


def original_are_status() -> dict[str, Any]:
    selected_path = configured_memory_path()
    return {
        "code_path": str(ORIGINAL_ARE_CODE_PATH),
        "code_exists": ORIGINAL_ARE_CODE_PATH.exists(),
        "memory_path": str(selected_path),
        "memory_dir_exists": selected_path.parent.exists(),
        "memory_exists": selected_path.exists() and selected_path.is_file(),
        "env_override_active": bool(os.environ.get("CLAIRE_ORIGINAL_ARE_MEM_PATH")),
        "candidate_paths": [str(path) for path in candidate_memory_paths()],
    }


def append_original_are_memory(text: str, memory_path: str | Path | None = None) -> dict[str, Any]:
    """
    Append using the original ARE record format from are.py:
    {"ts": int(time.time()), "sha": sha256(text)[:10], "text": text[:8000]}
    """
    value = str(text or "")[:8000]
    path = resolve_append_path(memory_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": int(time.time()),
        "sha": hashlib.sha256(value.encode()).hexdigest()[:10],
        "text": value,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"memory_file": str(path), "record": record}


def read_original_are_history(limit: int = 8, memory_path: str | Path | None = None, create: bool = True) -> dict[str, Any]:
    memory_path = ensure_memory_file(memory_path) if memory_path is not None and create else (Path(memory_path) if memory_path is not None else resolve_memory_path(create=create))
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
