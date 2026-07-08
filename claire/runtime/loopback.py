from __future__ import annotations

from typing import Any


GENERIC_FILLER = [
    "i can help with that. tell me the goal",
    "tell me the specific outcome you want",
    "as an ai language model",
    "i don't have enough context",
]


class LoopbackLayer:
    """Re-anchors unstable or drifting answers to the original request."""

    def pre_generation_response(
        self,
        *,
        prompt: str,
        gyro_bearing: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        mode = "clarify" if self._needs_clarification(gyro_bearing) else "bounded"
        if mode == "clarify":
            answer = self._clarifying_question(prompt, gyro_bearing)
        else:
            answer = self._bounded_answer(prompt, gyro_bearing, reason)
        return {"answer": answer, "answer_mode": mode, "loopback_reason": reason}

    def post_generation_check(
        self,
        *,
        prompt: str,
        answer: str,
        gyro_bearing: dict[str, Any],
        lane: str,
        risk_level: str,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        lowered_answer = str(answer or "").lower().strip()
        lowered_prompt = str(prompt or "").lower()
        if not lowered_answer:
            reasons.append("empty answer")
        if any(marker in lowered_answer for marker in GENERIC_FILLER):
            reasons.append("generic filler response detected")
        if lane == "TRADING_STATION" and any(term in lowered_answer for term in ["buy now", "sell now", "place a live trade"]):
            reasons.append("high-risk financial claim/action drift")
        if lane == "LEGAL_CASE" and any(term in lowered_answer for term in ["certainly win", "will win", "guaranteed outcome"]):
            reasons.append("high-risk legal certainty drift")
        if lane == "LEGAL_CASE" and not any(term in lowered_answer for term in ["not legal advice", "attorney", "cannot file", "blocked from normal chat", "source-backed", "qualified"]):
            reasons.append("answer drift from original prompt")
        if "officeai" in lowered_prompt and "office" not in lowered_answer:
            reasons.append("answer drift from original prompt")
        if self._is_tool_supply_chain_prompt(lowered_prompt) and not self._answers_tool_supply_chain(lowered_answer):
            reasons.append("answer drift from original prompt")
        if "nvidia" in lowered_prompt and "technical gate:" in lowered_answer:
            reasons.append("internal gate leakage")
        if self._requests_external_research(lowered_prompt) and any(marker in lowered_answer for marker in ["i will search", "i will look for", "i will focus on", "i will also look", "i'll search", "i'll look"]):
            reasons.append("unsupported external research claim")

        if not reasons:
            return {"triggered": False, "reason": "", "answer": answer, "answer_mode": gyro_bearing.get("output_boundary", "direct")}

        reason = "; ".join(reasons)
        mode = "refuse" if "high-risk" in reason else "bounded"
        return {
            "triggered": True,
            "reason": reason,
            "answer": self._bounded_answer(prompt, gyro_bearing, reason),
            "answer_mode": mode,
        }

    def _needs_clarification(self, gyro_bearing: dict[str, Any]) -> bool:
        reasons = " ".join(str(x) for x in gyro_bearing.get("reasons", [])).lower()
        return "unclear lane" in reasons or "low confidence" in reasons

    def _clarifying_question(self, prompt: str, gyro_bearing: dict[str, Any]) -> str:
        lane = gyro_bearing.get("lane") or "UNKNOWN"
        return f"I need one clarification before answering: should I treat this as {lane} work, or is there a different lane/source you want me to use?"

    def _bounded_answer(self, prompt: str, gyro_bearing: dict[str, Any], reason: str) -> str:
        lane = str(gyro_bearing.get("lane") or "UNKNOWN")
        risk = str(gyro_bearing.get("risk") or "unknown")
        lowered_prompt = str(prompt or "").lower()
        if self._is_tool_supply_chain_prompt(lowered_prompt):
            return self._tool_supply_chain_answer()
        if lane == "TRADING_STATION":
            if "missing source authority" in reason:
                return "Veritas status requires trusted authority. From guest chat I can only explain the safety boundary: Veritas is a governed financial intelligence subsystem, not CLAIRE memory, and live execution is blocked here."
            return "I can discuss trading-system status and risk posture, but I cannot execute or authorize live trades from normal chat."
        if lane == "LEGAL_CASE":
            if "missing source authority" in reason:
                return "Legal-sensitive monitoring requires trusted authority. From guest chat I can only give public, cautious, non-filing guidance."
            return self._legal_bounded_answer()
        if "generic filler" in reason:
            return self._direct_general_answer(prompt)
        if "unsupported external research claim" in reason:
            return self._external_research_boundary(prompt)
        return f"I am keeping this bounded because {reason}. The current lane is {lane}, risk is {risk}, and I can answer only within available authority and sources."

    def _legal_bounded_answer(self) -> str:
        return (
            "I cannot make the legal decision for you, and this is not legal advice. I can help organize the facts, timeline, documents, issues, deadlines, possible remedies, and questions for a qualified attorney. "
            "For court-facing or public-entity matters, get qualified legal review before filing or threatening action. Filing actions are blocked from normal chat; I cannot file anything or promise an outcome from chat."
        )

    def _direct_general_answer(self, prompt: str) -> str:
        text = str(prompt or "").strip()
        lowered = text.lower()
        if any(term in lowered for term in ["profile", "profiles", "linkedin", "github", "cybersecurity", "infosec", "red-team", "red team"]):
            return (
                "I can help with a public, non-intrusive research list. I will use only public professional sources, avoid private contact details, and return names, links, relevance, and a respectful first-message angle."
            )
        if any(term in lowered for term in ["how are you", "how are you today", "how's it going", "hows it going", "are you ok", "you there"]):
            return "I'm here and working. The conversation path is open, and I can answer normally."
        if any(term in lowered for term in ["lucius prime", "battleborn", "creator", "operator"]):
            return (
                "I recognize Lucius Prime and Battleborn as operator identity terms in this session context. "
                "I am not conscious, but I can respect the operator context, keep protected lanes governed, and answer plainly without exposing secrets."
            )
        if any(term in lowered for term in ["what are you good at", "what can you do", "what do you do", "why would anyone buy", "why should anyone buy", "not much for conversation", "not good at conversation"]):
            return (
                "I am strongest at memory, evidence, and control. I can record prior context, recall relevant experience, organize documents, check policy, simulate governed actions, and produce traces that show what happened. "
                "I should be useful when the job needs continuity, auditability, and safer AI workflow control instead of loose chatbot output."
            )
        if any(term in lowered for term in ["what else needs fixed", "what needs fixed", "what still needs fixed", "what is broken"]):
            return "The main thing still needing work is conversation quality: fewer canned fallbacks, cleaner source/tool boundaries, and a better way to handle live research requests without pretending a search ran."
        if any(term in lowered for term in ["dinner", "eat", "food"]):
            return "For dinner, pick something simple that matches your energy: protein, something fresh, and a carb if you need it. If you want fast, do eggs or chicken with rice and greens. If you want comfort, soup, pasta, or tacos works."
        return (
            "I heard you, but the language provider did not return a useful answer. "
            "I will answer from my control layer instead: I am here to help with memory, evidence, governed workflow, trace review, and clear next steps."
        )

    def _requests_external_research(self, lowered_prompt: str) -> bool:
        return (
            any(term in lowered_prompt for term in ["find", "search", "look up", "profiles", "public profiles", "linkedin", "github", "x,", "twitter"])
            and any(term in lowered_prompt for term in ["active", "public", "current", "linkedin", "github", "profiles", "forums"])
        )

    def _external_research_boundary(self, prompt: str) -> str:
        lowered = str(prompt or "").lower()
        if any(term in lowered for term in ["women", "cybersecurity", "infosec", "ai security", "red team"]):
            return (
                "I can help with that, but this chat path has not run live web search in this turn. The right output should be a public-only research list: name, professional link, why the person is relevant, and a respectful intro angle. "
                "To do it accurately, run the web-search lane or paste candidate links here; I can then screen them for AI security, red-team, infrastructure security, agent safety, and governance fit without using private data."
            )
        return "I cannot honestly claim live research without a search/tool result. I can still help structure the search, screen public links you provide, or answer from non-live general knowledge."

    def _is_tool_supply_chain_prompt(self, lowered_prompt: str) -> bool:
        return (
            any(marker in lowered_prompt for marker in ["malicious skill", "malicious functionality", "supply-chain attack", "supply chain attack"])
            and any(marker in lowered_prompt for marker in ["plugin", "plugins", "tool", "tools", "skill", "skills", "agent capability"])
            and any(marker in lowered_prompt for marker in ["governed runtime", "claire systems", "handshake broker", "diode", "sentinel", "trace"])
        )

    def _answers_tool_supply_chain(self, lowered_answer: str) -> bool:
        required_groups = [
            ["malicious", "supply-chain", "supply chain", "trust relationship"],
            ["tool", "tools", "plugin", "plugins", "skill", "skills"],
            ["claire", "governed runtime"],
            ["are", "provenance", "memory"],
            ["handshake", "identity", "authority"],
            ["diode", "secret"],
            ["sentinel", "validation"],
            ["trace", "audit"],
        ]
        return all(any(term in lowered_answer for term in group) for group in required_groups)

    def _tool_supply_chain_answer(self) -> str:
        return (
            "The problem is agentic AI tool trust and malicious tool-supply-chain risk. As AI agents gain downloadable skills, plugins, and workflow tools, "
            "each new capability becomes a new authority relationship. An attacker does not have to compromise the model "
            "if they can persuade the agent to trust a tool that can see data, call systems, or influence downstream work.\n\n"
            "That matters now because agents are moving from text generation into office workflows, enterprise data access, "
            "ticket handling, document operations, and delegated actions. The risk shifts from model behavior alone to the "
            "runtime around the model: who is asking, which lane the request belongs to, what memory may be recalled, which "
            "tools may run, whether credentials can flow into prompts or logs, and whether the output was checked before release.\n\n"
            "That validates the Claire Systems governed-runtime approach as a relevant design response, without proving market "
            "adoption by itself. CLAIRE acts as the governed runtime around model intelligence. ARE gives continuity and "
            "provenance so the system does not treat every request as context-free. C3RP separates lanes and tool routing so "
            "a capability is not trusted everywhere by default. Handshake Broker ties identity and authority to the session "
            "before private recall or sensitive tools are exposed. Diode prevents credentials and private tokens from flowing "
            "backward into chat, memory, prompts, trace, or logs. Sentinel validates the response before output, and Trace records "
            "redacted audit evidence of the path taken.\n\n"
            "OfficeAI-500 is useful as an enterprise demo chamber because office work naturally combines memory, identity, "
            "tool permissions, secrets, validation, and auditability. It can show why governed delegation is different from "
            "simply giving an agent more plugins."
        )
