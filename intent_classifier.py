from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


INTENTS = {
    "legal",
    "philosophical",
    "architectural",
    "technical",
    "psychological",
    "operational",
    "mixed",
}


QUESTION_LANES = {
    "ABSTRACT_REASONING",
    "FACTUAL_RECALL",
    "INTERNAL_MEMORY_LOOKUP",
    "LEGAL_RESEARCH",
    "SYSTEM_STATUS",
    "HYBRID_REASONING_WITH_MEMORY",
}


@dataclass
class QueryIntent:
    primary_intent: str
    secondary_intents: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning_mode: str = "balanced"
    allowed_lanes: list[str] = field(default_factory=list)
    suppressed_lanes: list[str] = field(default_factory=list)
    retrieval_strategy: str = "support_only"
    detected_intent: str = "FACTUAL_RECALL"
    source_output_allowed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def clean_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s'.-]", " ", str(text).lower()).split())


KEYWORDS: dict[str, tuple[str, ...]] = {
    "legal": (
        "legal",
        "holding",
        "case",
        "cases",
        "court",
        "courtlistener",
        "docket",
        "opinion",
        "precedent",
        "copyright",
        "statute",
        "complaint",
        "motion",
        "filing",
        "judge",
        "permit",
        "legal memo",
        "legal analogy",
        "legal analogies",
    ),
    "philosophical": (
        "ship of theseus",
        "theseus",
        "paradox",
        "identity",
        "continuity",
        "sovereign intelligence",
        "sovereignty",
        "prove",
        "concept",
        "personhood",
        "selfhood",
    ),
    "architectural": (
        "architecture",
        "veritas sovereign core",
        "vsc",
        "truth spine",
        "sentinel",
        "gyro",
        "runtime",
        "component",
        "modules",
        "sovereign runtime",
        "claire doctrine",
    ),
    "technical": (
        "deterministic",
        "analog recall engine",
        "are",
        "engine",
        "module",
        "modules",
        "replace",
        "upgraded",
        "component replacement",
        "patent",
        "63/942,560",
        "63 942 560",
    ),
    "psychological": (
        "human memory",
        "memory replacement",
        "trauma",
        "mind",
        "psychological",
        "consciousness",
        "subjective",
        "identity continuity",
    ),
    "operational": (
        "deploy",
        "status",
        "diagnose",
        "button",
        "service",
        "server",
        "azure",
        "cloudflare",
        "run",
        "restart",
        "workflow",
    ),
}


RESEARCH_MARKERS = (
    "research memo",
    "connect",
    "compare",
    "analogies",
    "sources",
    "citations",
    "brief",
)


INTERNAL_MEMORY_MARKERS = (
    "what do my docs say",
    "what do my documents say",
    "from my docs",
    "from my files",
    "from my documents",
    "what was the root cause",
    "what fix did we reject",
    "next approved step",
    "yesterday we discovered",
    "what did i say before",
    "what do you remember",
    "search memory",
    "find in memory",
    "internal memory",
    "uploaded document",
    "uploaded file",
)


LEGAL_RESEARCH_MARKERS = (
    "find case law",
    "case law",
    "legal memo",
    "holding",
    "statute",
    "jurisdiction",
    "court support",
    "courtlistener",
    "precedent",
    "legal research",
)


SYSTEM_STATUS_MARKERS = (
    "status",
    "diagnose",
    "health",
    "service",
    "ingest bridge",
    "port 8081",
    "is online",
    "are you online",
    "restart",
    "deploy",
)


DIRECT_REASONING_MARKERS = (
    "can you prove",
    "explain how",
    "what happens if",
    "how would",
    "impact",
    "solve",
    "concept",
)


def _score_intents(cleaned: str) -> dict[str, int]:
    scores = {intent: 0 for intent in KEYWORDS}
    for intent, terms in KEYWORDS.items():
        for term in terms:
            if term in cleaned:
                scores[intent] += 2 if " " in term or "/" in term else 1
    return scores


def _unique(items: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def detect_question_lane(cleaned: str, active: list[str], primary: str, secondary: list[str]) -> str:
    explicit_internal = any(marker in cleaned for marker in INTERNAL_MEMORY_MARKERS)
    explicit_legal = any(marker in cleaned for marker in LEGAL_RESEARCH_MARKERS)
    explicit_status = any(marker in cleaned for marker in SYSTEM_STATUS_MARKERS)
    explicit_research = any(marker in cleaned for marker in RESEARCH_MARKERS) or any(marker in cleaned for marker in LEGAL_RESEARCH_MARKERS)
    conceptual = bool({"philosophical", "architectural", "technical", "psychological"} & set(active))
    named_architecture = any(
        marker in cleaned
        for marker in [
            "vsc",
            "veritas sovereign core",
            "truth spine",
            "sentinel",
            "gyro",
            "analog recall engine",
            "are modules",
            " are",
            "63/942,560",
            "63 942 560",
            "sovereign runtime",
        ]
    )

    if explicit_status and not conceptual and not explicit_legal and not explicit_internal:
        return "SYSTEM_STATUS"
    if explicit_internal:
        return "INTERNAL_MEMORY_LOOKUP"
    if explicit_legal and (primary == "legal" or "legal" in secondary or "case law" in cleaned):
        return "LEGAL_RESEARCH"
    if conceptual and named_architecture:
        return "HYBRID_REASONING_WITH_MEMORY"
    if conceptual:
        return "ABSTRACT_REASONING"
    return "FACTUAL_RECALL"


def source_allowed_for_lane(question_lane: str) -> bool:
    return question_lane in {"FACTUAL_RECALL", "INTERNAL_MEMORY_LOOKUP", "LEGAL_RESEARCH", "SYSTEM_STATUS"}


def classify_query(prompt: str) -> QueryIntent:
    cleaned = clean_text(prompt)
    scores = _score_intents(cleaned)
    active = [intent for intent, score in scores.items() if score > 0]

    if not active:
        question_lane = "SYSTEM_STATUS" if any(x in cleaned for x in SYSTEM_STATUS_MARKERS) else (
            "INTERNAL_MEMORY_LOOKUP" if any(x in cleaned for x in INTERNAL_MEMORY_MARKERS) else "FACTUAL_RECALL"
        )
        return QueryIntent(
            primary_intent="operational" if any(x in cleaned for x in ["status", "button", "service"]) else "mixed",
            secondary_intents=["general"],
            confidence=0.45,
            reasoning_mode="balanced",
            allowed_lanes=["identity", "architecture", "ARE", "Claire_doctrine", "operations", "product"],
            suppressed_lanes=[],
            retrieval_strategy="support_only",
            detected_intent=question_lane,
            source_output_allowed=source_allowed_for_lane(question_lane),
        )

    ranked = sorted(active, key=lambda intent: scores[intent], reverse=True)
    top_score = scores[ranked[0]]
    close = [intent for intent in ranked if scores[intent] >= max(1, top_score - 1)]

    explicit_research = any(marker in cleaned for marker in RESEARCH_MARKERS) or any(marker in cleaned for marker in LEGAL_RESEARCH_MARKERS)
    explicit_case_law_search = "find case law" in cleaned or cleaned.startswith("find cases") or cleaned.startswith("search case law")
    direct_reasoning = any(marker in cleaned for marker in DIRECT_REASONING_MARKERS)
    conceptual = bool({"philosophical", "architectural", "technical", "psychological"} & set(active))

    if explicit_case_law_search:
        primary = "legal"
        secondary = [intent for intent in ranked if intent != "legal"]
    elif explicit_research and "legal" in active and conceptual:
        primary = "mixed"
        secondary = ranked
    elif len(active) >= 3 or (len(close) >= 2 and not (ranked[0] == "legal" and not direct_reasoning)):
        primary = "mixed"
        secondary = ranked
    else:
        primary = ranked[0]
        secondary = ranked[1:]

    legal_primary = primary == "legal" or (ranked[0] == "legal" and scores["legal"] >= scores.get("philosophical", 0) + 2)

    if explicit_case_law_search:
        reasoning_mode = "retrieval_first"
        retrieval_strategy = "legal_retrieval"
    elif legal_primary and not conceptual:
        reasoning_mode = "retrieval_first"
        retrieval_strategy = "legal_retrieval"
    elif explicit_research and "legal" in active and conceptual:
        reasoning_mode = "reasoning_first"
        retrieval_strategy = "primary_concept_support_with_secondary_legal"
    elif conceptual or direct_reasoning:
        reasoning_mode = "reasoning_first"
        retrieval_strategy = "support_only"
    else:
        reasoning_mode = "balanced"
        retrieval_strategy = "support_only"

    allowed_lanes = lanes_for_intents(primary, secondary, explicit_research)
    suppressed_lanes = suppressed_for_intents(primary, secondary, reasoning_mode, explicit_research)
    confidence = min(0.95, 0.45 + (sum(scores.values()) * 0.06))
    question_lane = detect_question_lane(cleaned, active, primary, secondary)
    source_output_allowed = source_allowed_for_lane(question_lane)

    return QueryIntent(
        primary_intent=primary if primary in INTENTS else "mixed",
        secondary_intents=_unique(secondary),
        confidence=round(confidence, 2),
        reasoning_mode=reasoning_mode,
        allowed_lanes=allowed_lanes,
        suppressed_lanes=suppressed_lanes,
        retrieval_strategy=retrieval_strategy,
        detected_intent=question_lane,
        source_output_allowed=source_output_allowed,
    )


def lanes_for_intents(primary: str, secondary: list[str], explicit_research: bool = False) -> list[str]:
    intents = set(secondary)
    intents.add(primary)
    lanes: list[str] = []
    if "philosophical" in intents or primary == "mixed":
        lanes.extend(["philosophy", "identity", "sovereignty", "identity_continuity", "Claire_doctrine"])
    if "architectural" in intents or primary == "mixed":
        lanes.extend(["architecture", "VSC", "ARE", "runtime", "Claire_doctrine"])
    if "technical" in intents:
        lanes.extend(["technical", "ARE", "VSC", "architecture", "patent"])
    if "psychological" in intents:
        lanes.extend(["psychological", "identity", "personal_context"])
    if "operational" in intents:
        lanes.extend(["operations", "runtime", "product"])
    if "legal" in intents:
        lanes.extend(["legal_theory"] if primary != "legal" else ["legal_case", "legal_theory", "compliance"])
        if explicit_research:
            lanes.extend(["legal_case", "legal_theory"])
    if not lanes:
        lanes = ["identity", "architecture", "ARE", "Claire_doctrine", "operations", "product"]
    return _unique(lanes)


def suppressed_for_intents(primary: str, secondary: list[str], reasoning_mode: str, explicit_research: bool = False) -> list[str]:
    intents = set(secondary)
    intents.add(primary)
    suppressed: list[str] = []
    if reasoning_mode == "reasoning_first" and not (explicit_research and "legal" in intents):
        suppressed.extend(["legal_case", "court_docket", "generic_case_law", "random_document_hits"])
    if primary == "legal":
        suppressed.extend(["personal_context"])
    if "operational" not in intents:
        suppressed.extend(["runtime_noise"])
    return _unique(suppressed)
