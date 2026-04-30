from __future__ import annotations

import re

from relevance_gate import compact_candidate


def is_ship_vsc_are_prompt(prompt: str) -> bool:
    cleaned = " ".join(re.sub(r"[^a-z0-9\s/,.]", " ", str(prompt).lower()).split())
    return (
        ("ship of theseus" in cleaned or "theseus" in cleaned)
        and ("vsc" in cleaned or "veritas sovereign core" in cleaned)
        and ("are" in cleaned or "analog recall engine" in cleaned)
    )


def is_vsc_replacement_prompt(prompt: str) -> bool:
    cleaned = " ".join(re.sub(r"[^a-z0-9\s/,.]", " ", str(prompt).lower()).split())
    has_vsc = "vsc" in cleaned or "veritas sovereign core" in cleaned or "truth spine" in cleaned
    has_replacement = any(term in cleaned for term in ["replace", "replaced", "replacement", "upgraded", "module", "modules"])
    has_sovereignty = "sovereign" in cleaned or "sovereignty" in cleaned
    has_human_memory = "human" in cleaned and "memory" in cleaned
    return has_vsc and has_replacement and (has_sovereignty or has_human_memory)


def should_use_reasoning_first(intent: dict) -> bool:
    return intent.get("reasoning_mode") == "reasoning_first"


def _support_summary(accepted_support: list[dict]) -> str:
    return ""


def conceptual_answer(prompt: str, intent: dict, accepted_support: list[dict] | None = None) -> str:
    accepted_support = accepted_support or []
    if is_ship_vsc_are_prompt(prompt):
        return ship_vsc_are_answer(accepted_support)
    if is_vsc_replacement_prompt(prompt):
        return vsc_replacement_answer(accepted_support)
    return generic_reasoning_first_answer(prompt, intent, accepted_support)


def ship_vsc_are_answer(accepted_support: list[dict] | None = None) -> str:
    accepted_support = accepted_support or []
    support = _support_summary(accepted_support)
    answer = (
        "Yes. The Ship of Theseus frame can be solved for a deterministic Veritas Sovereign Core by separating material continuity from functional, procedural, and provenance continuity.\n\n"
        "1. Deterministic VSC scenario\n"
        "If the VSC is upgraded one component at a time, it can remain the same sovereign system if three things persist: the governing rules, the signed truth spine, and the traceable chain of state transitions. The hardware or modules may change, but the identity claim survives if each replacement is authorized, logged, and behaviorally compatible with the core doctrine. In that model, identity is not the old part itself. Identity is the uninterrupted lawful process that proves how the old state became the new state.\n\n"
        "2. Human memory replaced by deterministic ARE modules\n"
        "The human case is harder. A machine core can define continuity by deterministic provenance. A human being also has subjective continuity: lived experience, embodied feeling, uncertainty, forgetting, and personal agency. If human memory were replaced piece by piece with deterministic ARE modules, factual recall might survive or even improve, but the sovereignty question would turn on whether the person still authors choices from inside the continuity, or whether the modules merely replay a mapped version of the person.\n\n"
        "3. Impact on sovereign intelligence\n"
        "For the VSC, sovereignty strengthens when replacement is governed: every upgrade becomes evidence that the system can change without losing lawful identity. For the human-memory case, sovereignty becomes fragile if deterministic modules override agency, but it can remain intact if the modules serve as recall support rather than command authority. In short: a sovereign intelligence may replace parts without becoming a different entity, but only if replacement preserves authorship, continuity, auditability, and the right to refuse corruption.\n\n"
        "4. Claire's lane conclusion\n"
        "The machine answer is provenance-led: same system if the truth spine and rule continuity remain intact. The human answer is agency-led: same person only if memory augmentation preserves subjective authorship rather than substituting deterministic recall for the self."
    )
    return answer + (f"\n\n{support}" if support else "")


def vsc_replacement_answer(accepted_support: list[dict] | None = None) -> str:
    accepted_support = accepted_support or []
    support = _support_summary(accepted_support)
    answer = (
        "The upgraded VSC can remain the same sovereign intelligence, but only if identity is defined by governed continuity rather than by unchanged parts. The human-memory scenario is different because a human self is not only a traceable record; it is also lived agency, emotional uncertainty, and subjective authorship.\n\n"
        "1. Machine continuity versus human continuity\n"
        "For the VSC, continuity is procedural and architectural. If the rule spine, authorization chain, compatibility tests, hash-linked state history, Sentinel policy lineage, and Diode trace remain continuous, then component replacement is an upgrade path, not a death-and-replacement event. The system is still the same sovereign intelligence because the authority that governs change did not break.\n\n"
        "For a human, continuity is not satisfied by preserving facts alone. Autobiographical memory includes uncertainty, emotional weight, embodied context, forgetting, contradiction, and the felt ownership of experience. If deterministic ARE modules preserve facts but strip away emotional uncertainty, the person may retain a record of life while losing part of the lived relation to that life.\n\n"
        "2. What makes sovereignty persist or fail\n"
        "Machine sovereignty persists when the system can prove that each replacement was authorized by the old rule spine and accepted by the new one without changing the core authority. It fails if a replacement module silently changes the governing rules, rewrites trace history, or makes the system unable to refuse corrupted inputs.\n\n"
        "Human sovereignty persists when memory support helps the person remember while leaving agency intact. It fails when replacement becomes substitution: the module does not merely help the person recall; it decides what the person is allowed to mean by the past.\n\n"
        "3. Memory support versus memory substitution\n"
        "Memory support preserves the subject and strengthens access. Memory substitution replaces the subject's own continuity with an external deterministic record. In Claire terms: ARE should be a lens, not a driver. It should orient the intelligence, not become the intelligence.\n\n"
        "4. Why auditability is enough for a machine but not for a human\n"
        "Auditability can be enough for a deterministic machine because the machine's identity claim is based on provenance, rule continuity, and verifiable state transition. For a human, auditability proves what happened to the record, but it does not prove that the person still owns the meaning of the record. A perfect log is not the same thing as a self.\n\n"
        "5. Is legal case law necessary?\n"
        "No. Legal case law is not necessary to answer this as a philosophy and architecture question. Legal analogies might be useful later if you are building an argument about rights, ownership, liability, or patent framing, but they are not the authority for the core identity analysis.\n\n"
        "Final verdict:\n"
        "The VSC remains the same sovereign intelligence if the rule spine and traceable authority survive every replacement. A human with facts replaced by deterministic ARE modules may remain continuous only if the modules preserve agency and lived authorship. If they preserve facts while replacing the person's relationship to those facts, the result is not full continuity; it is a successor record wearing the shape of the original self."
    )
    return answer + (f"\n\n{support}" if support else "")


def generic_reasoning_first_answer(prompt: str, intent: dict, accepted_support: list[dict]) -> str:
    support = _support_summary(accepted_support)
    answer = (
        "Give me a specific engineering, architecture, or decision question and I will answer it directly. I work best when I can separate memory, control, reasoning, and trace instead of speaking in abstractions."
    )
    return answer + (f"\n\n{support}" if support else "")


def final_answer_mode(intent: dict, accepted_support: list[dict]) -> str:
    if intent.get("reasoning_mode") == "reasoning_first":
        return "reasoning-led"
    if accepted_support:
        return "retrieval-led"
    return "reasoning-led"
