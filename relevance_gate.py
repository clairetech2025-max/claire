from __future__ import annotations

import re
from typing import Any

from lane_router import normalize_lane


QUESTION_TYPE_TERMS = {
    "legal": {"holding", "case", "court", "copyright", "precedent", "docket", "legal"},
    "philosophical": {"identity", "paradox", "theseus", "continuity", "sovereign", "personhood"},
    "architectural": {"vsc", "veritas", "sentinel", "gyro", "runtime", "architecture", "truth", "core"},
    "technical": {"deterministic", "are", "module", "engine", "component", "patent"},
    "psychological": {"human", "memory", "consciousness", "mind", "replacement"},
    "operational": {"status", "deploy", "service", "server", "button", "diagnose"},
}

ENTITY_TERMS = {
    "ship of theseus",
    "theseus",
    "software sovereignty",
    "software",
    "replacement",
    "continuity",
    "veritas",
    "vsc",
    "veritas sovereign core",
    "63/942,560",
    "63 942 560",
    "analog recall engine",
    "are",
    "sentinel",
    "gyro",
    "sovereign",
    "paisley park",
    "boxill",
}

DISTINCTIVE_TERMS = {
    "software",
    "sovereignty",
    "sovereign",
    "replacement",
    "continuity",
    "veritas",
    "vsc",
    "analog recall",
    "ship of theseus",
    "theseus",
    "identity paradox",
}

STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "your",
    "you",
    "for",
    "what",
    "how",
    "why",
    "can",
    "could",
    "would",
    "should",
    "must",
    "about",
    "into",
    "then",
    "also",
    "both",
}


def clean_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s'./-]", " ", str(text).lower()).split())


def tokens(text: str) -> set[str]:
    return {t for t in clean_text(text).split() if len(t) > 2 and t not in STOPWORDS}


def lexical_overlap(query: str, text: str) -> float:
    q = tokens(query)
    t = tokens(text)
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q))


def entity_match(query: str, text: str) -> float:
    q = clean_text(query)
    t = clean_text(text)
    entities = [entity for entity in ENTITY_TERMS if entity in q]
    if not entities:
        return 0.5
    hits = sum(1 for entity in entities if entity in t)
    return hits / max(1, len(entities))


def question_type_match(intent: dict, text: str) -> float:
    cleaned = clean_text(text)
    active = [intent.get("primary_intent")] + list(intent.get("secondary_intents") or [])
    active = [x for x in active if x and x != "mixed"]
    if not active:
        return 0.5
    possible = 0
    hits = 0
    for item in active:
        terms = QUESTION_TYPE_TERMS.get(item, set())
        if not terms:
            continue
        possible += 1
        if any(term in cleaned for term in terms):
            hits += 1
    if possible == 0:
        return 0.5
    return hits / possible


def lane_match(candidate_lanes: list[str], allowed_lanes: list[str], suppressed_lanes: list[str]) -> tuple[float, str]:
    lanes = {normalize_lane(lane) for lane in candidate_lanes}
    allowed = {normalize_lane(lane) for lane in allowed_lanes}
    suppressed = {normalize_lane(lane) for lane in suppressed_lanes}
    if lanes & suppressed:
        return 0.0, "suppressed_lane"
    if not lanes or "general" in lanes:
        return 0.35, "weak_lane_metadata"
    if allowed and lanes & allowed:
        return 1.0, "lane_match"
    if allowed:
        return 0.0, "lane_not_allowed"
    return 0.6, "no_lane_policy"


def support_role_suitability(intent: dict, candidate: dict) -> float:
    lanes = {normalize_lane(lane) for lane in candidate.get("lanes", [])}
    reasoning_mode = intent.get("reasoning_mode")
    if reasoning_mode == "reasoning_first" and "legal_case" in lanes and "legal_case" not in intent.get("allowed_lanes", []):
        return 0.0
    if reasoning_mode == "reasoning_first":
        return 0.8
    return 0.7


def score_candidate(query: str, intent: dict, candidate: dict) -> dict:
    text = str(candidate.get("text") or "")
    lm, lane_reason = lane_match(candidate.get("lanes", []), intent.get("allowed_lanes", []), intent.get("suppressed_lanes", []))
    sem = lexical_overlap(query, text)
    ent = entity_match(query, text)
    qtm = question_type_match(intent, text)
    support = support_role_suitability(intent, candidate)
    final = (lm * 0.35) + (sem * 0.25) + (ent * 0.20) + (qtm * 0.15) + (support * 0.05)
    return {
        "lane_match": round(lm, 3),
        "semantic_match": round(sem, 3),
        "entity_match": round(ent, 3),
        "question_type_match": round(qtm, 3),
        "support_role_suitability": round(support, 3),
        "final_relevance": round(final, 3),
        "lane_reason": lane_reason,
    }


def missing_distinctive_subject(query: str, text: str) -> bool:
    q = clean_text(query)
    t = clean_text(text)
    wanted = [term for term in DISTINCTIVE_TERMS if term in q]
    if not wanted:
        return False
    return not any(term in t for term in wanted)


def gate_retrieval_candidates(query: str, intent: dict, candidates: list[dict], threshold: float = 0.42) -> tuple[list[dict], list[dict]]:
    accepted = []
    rejected = []
    reasoning_first = intent.get("reasoning_mode") == "reasoning_first"
    for candidate in candidates:
        scored = dict(candidate)
        gate = score_candidate(query, intent, candidate)
        scored["gate"] = gate
        hard_lane_fail = gate["lane_match"] <= 0.0
        hard_type_fail = reasoning_first and gate["question_type_match"] <= 0.0
        hard_distinctive_fail = (
            intent.get("detected_intent") == "LEGAL_RESEARCH"
            and "legal_case" in {normalize_lane(lane) for lane in candidate.get("lanes", [])}
            and missing_distinctive_subject(query, scored.get("text", ""))
        )
        if hard_lane_fail or hard_type_fail or hard_distinctive_fail or gate["final_relevance"] < threshold:
            if hard_lane_fail:
                reason = gate.get("lane_reason") or "lane_rejected"
            elif hard_type_fail:
                reason = "question_type_mismatch"
            elif hard_distinctive_fail:
                reason = "missing_distinctive_subject"
            else:
                reason = "low_relevance"
            scored["rejection_reason"] = reason
            rejected.append(scored)
        else:
            accepted.append(scored)
    accepted.sort(key=lambda item: item.get("gate", {}).get("final_relevance", 0), reverse=True)
    return accepted, rejected


def compact_candidate(candidate: dict, max_chars: int = 220) -> dict[str, Any]:
    text = " ".join(str(candidate.get("text") or "").split())
    return {
        "text": text[:max_chars],
        "lanes": candidate.get("lanes", []),
        "score": candidate.get("score", 0.0),
        "gate": candidate.get("gate", {}),
        "rejection_reason": candidate.get("rejection_reason", ""),
    }
