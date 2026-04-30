from __future__ import annotations

import re
from typing import Any


LANE_PATTERNS: dict[str, tuple[str, ...]] = {
    "legal_case": (
        "courtlistener legal record",
        "case name:",
        " v. ",
        " v ",
        "docket number",
        "court:",
        "opinion",
        "holding",
        "copyright enforcement",
        "paisley park",
        "boxill",
    ),
    "legal_theory": (
        "legal theory",
        "jurisdiction",
        "standing",
        "sovereignty doctrine",
        "legal analogy",
        "legal analogies",
        "patent",
        "provisional patent",
    ),
    "philosophy": (
        "ship of theseus",
        "theseus",
        "identity paradox",
        "paradox",
        "continuity",
        "personhood",
        "selfhood",
    ),
    "identity": (
        "identity continuity",
        "human memory",
        "memory replacement",
        "namesake",
        "reflective core",
        "little pieces",
    ),
    "sovereignty": (
        "sovereign",
        "sovereignty",
        "autonomous",
        "continuity of authority",
    ),
    "architecture": (
        "architecture",
        "runtime",
        "truth spine",
        "sentinel",
        "gyro",
        "diode",
        "component replacement",
    ),
    "VSC": (
        "vsc",
        "veritas sovereign core",
        "veritas",
        "deterministic core",
    ),
    "ARE": (
        "are",
        "analog recall engine",
        "active recall",
        "gyro are",
        "memory module",
        "memory-first",
    ),
    "Claire_doctrine": (
        "claire doctrine",
        "claire's rule",
        "lane discipline",
        "preserve human meaning",
    ),
    "personal_context": (
        "lucius",
        "creator",
        "private",
        "case room",
    ),
    "operations": (
        "status",
        "service",
        "azure",
        "cloudflare",
        "restart",
        "deploy",
        "diagnose",
    ),
    "product": (
        "marketplace",
        "buyer",
        "demo",
        "investor",
        "product",
        "pitch",
    ),
    "runtime": (
        "server",
        "endpoint",
        "fastapi",
        "uvicorn",
        "trace",
        "log",
    ),
    "compliance": (
        "compliance",
        "policy",
        "sentinel validation",
        "audit",
        "redaction",
    ),
}


def clean_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s'.:-]", " ", str(text).lower()).split())


def extract_record_text(record: Any) -> str:
    if isinstance(record, dict):
        parts = []
        for key in ("text", "content", "chunk", "memory", "value", "payload", "summary", "title", "source"):
            value = record.get(key)
            if value:
                parts.append(str(value))
        metadata = record.get("metadata")
        if isinstance(metadata, dict):
            for value in metadata.values():
                if isinstance(value, (str, int, float)):
                    parts.append(str(value))
        return "\n".join(parts).strip()
    return str(record or "").strip()


def normalize_lane(lane: str) -> str:
    aliases = {
        "court_docket": "legal_case",
        "generic_case_law": "legal_case",
        "case_law": "legal_case",
        "sovereignty doctrine": "sovereignty",
        "VSC doctrine": "VSC",
        "ARE doctrine": "ARE",
        "prior Claire architecture/philosophy": "Claire_doctrine",
    }
    return aliases.get(str(lane).strip(), str(lane).strip())


def infer_memory_lanes(record: Any) -> list[str]:
    lanes: list[str] = []
    if isinstance(record, dict):
        for key in ("lane", "lanes", "tags", "intent_tags", "source_type", "domain"):
            value = record.get(key)
            if isinstance(value, list):
                lanes.extend(normalize_lane(str(item)) for item in value)
            elif isinstance(value, str) and value:
                lanes.extend(normalize_lane(part.strip()) for part in re.split(r"[,|]", value) if part.strip())
        metadata = record.get("metadata")
        if isinstance(metadata, dict):
            value = metadata.get("lane") or metadata.get("lanes") or metadata.get("tags")
            if isinstance(value, list):
                lanes.extend(normalize_lane(str(item)) for item in value)
            elif isinstance(value, str) and value:
                lanes.extend(normalize_lane(part.strip()) for part in re.split(r"[,|]", value) if part.strip())

    cleaned = clean_text(extract_record_text(record))
    for lane, terms in LANE_PATTERNS.items():
        if any(term in cleaned for term in terms):
            lanes.append(lane)

    if not lanes and cleaned:
        lanes.append("general")

    out = []
    seen = set()
    for lane in lanes:
        lane = normalize_lane(lane)
        if lane and lane not in seen:
            out.append(lane)
            seen.add(lane)
    return out


def extract_candidates(data: Any, limit: int = 12) -> list[dict]:
    if not data:
        return []
    raw_items = []
    if isinstance(data, dict):
        for key in ("results", "matches", "hits", "items"):
            value = data.get(key)
            if isinstance(value, list):
                raw_items.extend(value)
        if not raw_items:
            raw_items.append(data)
    elif isinstance(data, list):
        raw_items = data
    else:
        raw_items = [{"text": str(data)}]

    candidates = []
    for idx, item in enumerate(raw_items[:limit]):
        text = extract_record_text(item)
        if not text:
            continue
        score = 0.0
        if isinstance(item, dict):
            for key in ("score", "final_score", "semantic_score", "similarity"):
                try:
                    score = float(item.get(key) or 0.0)
                    if score:
                        break
                except Exception:
                    pass
        candidates.append(
            {
                "index": idx,
                "text": text,
                "score": score,
                "lanes": infer_memory_lanes(item),
                "raw": item if isinstance(item, dict) else {"text": text},
            }
        )
    return candidates


def route_candidates(candidates: list[dict], allowed_lanes: list[str], suppressed_lanes: list[str]) -> tuple[list[dict], list[dict]]:
    allowed = {normalize_lane(lane) for lane in allowed_lanes}
    suppressed = {normalize_lane(lane) for lane in suppressed_lanes}
    accepted = []
    rejected = []
    for candidate in candidates:
        lanes = {normalize_lane(lane) for lane in candidate.get("lanes", [])}
        if lanes & suppressed:
            candidate["rejection_reason"] = "suppressed_lane"
            rejected.append(candidate)
        elif allowed and lanes and not (lanes & allowed):
            candidate["rejection_reason"] = "lane_not_allowed"
            rejected.append(candidate)
        else:
            accepted.append(candidate)
    return accepted, rejected
