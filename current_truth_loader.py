from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATE_DIR = Path("claire_state")
SUBSYSTEM_REGISTRY_FILE = "subsystem_registry.json"

TRUTH_FILES = [
    "company_profile.json",
    "founding_team.json",
    "mission_statement.md",
    "nvidia_pathway.json",
    "technical_stack.json",
    "canonical_terms.json",
    "horse_stewardship.json",
    "legal_case_summary.json",
    "trading_station_status.json",
    "repo_checkpoint.json",
]


def load_current_truth(state_dir: str | Path = STATE_DIR) -> dict[str, Any]:
    base = Path(state_dir)
    truth: dict[str, Any] = {"_authority_order": ["current_truth_files", "recent_explicit_user_updates", "verified_memory_events", "uploaded_documents", "model_knowledge"]}
    for name in TRUTH_FILES:
        path = base / name
        key = path.stem
        if not path.exists():
            truth[key] = None
            continue
        try:
            if path.suffix.lower() == ".json":
                truth[key] = json.loads(path.read_text(encoding="utf-8"))
            else:
                truth[key] = path.read_text(encoding="utf-8")
        except Exception as exc:
            truth[key] = {"error": str(exc), "path": str(path)}
    return truth


def load_subsystem_registry(state_dir: str | Path = STATE_DIR) -> dict[str, Any]:
    path = Path(state_dir) / SUBSYSTEM_REGISTRY_FILE
    if not path.exists():
        return {"subsystems": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"subsystems": [], "error": str(exc), "path": str(path)}
    if isinstance(data, dict) and isinstance(data.get("subsystems"), list):
        return data
    if isinstance(data, list):
        return {"subsystems": data}
    return {"subsystems": [], "error": "subsystem registry must contain a subsystems list", "path": str(path)}


def get_subsystem_entry(name: str, state_dir: str | Path = STATE_DIR) -> dict[str, Any] | None:
    wanted = str(name or "").casefold()
    for entry in load_subsystem_registry(state_dir).get("subsystems", []):
        if str(entry.get("subsystem_name") or "").casefold() == wanted:
            return entry
    return None


def truth_for_lane(lane: str, truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or load_current_truth()
    lane = str(lane or "").upper()
    keys = {
        "BUSINESS_FORMATION": ["company_profile", "founding_team", "mission_statement"],
        "HORSE_STEWARDSHIP": ["horse_stewardship", "mission_statement", "founding_team"],
        "NVIDIA_PATHWAY": ["nvidia_pathway", "technical_stack", "repo_checkpoint", "company_profile"],
        "TRADING_STATION": ["trading_station_status", "technical_stack", "repo_checkpoint"],
        "LEGAL_CASE": ["legal_case_summary"],
        "CLAIRE_SYSTEM_ARCHITECTURE": ["technical_stack", "canonical_terms", "mission_statement", "repo_checkpoint"],
    }.get(lane, ["company_profile", "mission_statement", "repo_checkpoint"])
    return {key: truth.get(key) for key in keys if truth.get(key) is not None}
