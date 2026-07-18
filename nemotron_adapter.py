from __future__ import annotations

import json
import os
from typing import Any, Callable

import requests

from context_builder import render_context_packet

ProviderGenerate = Callable[[list[dict[str, str]], dict[str, Any]], str]


class NemotronAdapter:
    def build_messages(self, context_packet: dict[str, Any], user_message: str) -> list[dict[str, str]]:
        return build_messages(context_packet, user_message)

    def call_nemotron(self, messages: list[dict[str, str]], model_config: dict[str, Any] | None = None) -> dict[str, Any]:
        return call_nemotron(messages, model_config=model_config)

    def parse_response(self, raw_response: Any) -> dict[str, Any]:
        return parse_response(raw_response)


def build_messages(context_packet: dict[str, Any], user_message: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Claire speaking to the user through CLAIRE's governed runtime. "
                "Use the supplied context packet only as private orientation. Do not mention the context packet, current lane, user goal label, runtime, trace, policy, or internal routing unless the user explicitly asks for debug. "
                "Answer the user's message directly in natural language. Do not ask for goals or constraints when the request can be answered with a reasonable first pass. "
                "Do not claim you will search, browse, contact services, or perform actions unless a tool actually ran in this request. If live external information is required and no tool result is present, say that clearly and offer a useful non-live next step. "
                "Do not invent memory. Separate fact, inference, uncertainty, and next action only when that structure helps the user."
            ),
        },
        {"role": "system", "content": render_context_packet(context_packet)},
        {"role": "user", "content": user_message},
    ]


def call_nemotron(messages: list[dict[str, str]], model_config: dict[str, Any] | None = None, provider_generate: ProviderGenerate | None = None) -> dict[str, Any]:
    model_config = model_config or {}
    if provider_generate:
        text = provider_generate(messages, model_config)
        return {"content": str(text or "").strip(), "reasoning_content": "", "raw": {"provider": "in_process"}}

    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        if _should_use_deterministic_guardrail(messages):
            return {"content": _deterministic_stub(messages), "reasoning_content": "", "raw": {"provider": "local_deterministic_stub", "model": "nemotron-stub"}}
        if not model_config.get("disable_local_bridge"):
            local_text = _call_local_bridge(messages, model_config)
            if local_text:
                return {"content": local_text, "reasoning_content": "", "raw": {"provider": "local_bridge"}}
        return {"content": _deterministic_stub(messages), "reasoning_content": "", "raw": {"provider": "local_deterministic_stub", "model": "nemotron-stub"}}

    base_url = model_config.get("base_url") or os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    url = str(base_url).rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = {
        "model": model_config.get("model") or os.environ.get("NVIDIA_NIM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
        "messages": messages,
        "temperature": float(model_config.get("temperature", 0.25)),
        "max_tokens": int(model_config.get("max_tokens", 2048)),
    }
    response = requests.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=int(model_config.get("timeout", 60)))
    if response.status_code >= 400:
        return {"content": f"GO provider unavailable: NVIDIA NIM status {response.status_code}", "reasoning_content": "", "raw": {"status_code": response.status_code}}
    return parse_response(response.json())


def _call_local_bridge(messages: list[dict[str, str]], model_config: dict[str, Any]) -> str:
    base_url = str(
        model_config.get("local_base_url")
        or os.environ.get("CLAIRE_LOCAL_LLM_URL")
        or os.environ.get("LLM_BASE_URL")
        or "http://127.0.0.1:8080"
    ).rstrip("/")
    prompt = messages_to_prompt(messages)
    payload = {
        "prompt": prompt,
        "temperature": float(model_config.get("temperature", 0.35)),
        "n_predict": int(model_config.get("max_tokens", 700)),
        "max_tokens": int(model_config.get("max_tokens", 700)),
    }
    for path in ("/completion", ""):
        try:
            response = requests.post(f"{base_url}{path}", json=payload, timeout=int(model_config.get("timeout", 60)))
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get("ok") is False:
                continue
            if isinstance(data, dict):
                for key in ("response", "content", "output", "text", "answer", "result"):
                    value = str(data.get(key) or "").strip()
                    if value and not value.lower().startswith("go provider unavailable"):
                        return value
            text = response.text.strip()
            if text and not text.lower().startswith("<html"):
                return text
        except Exception:
            continue
    return ""


def _should_use_deterministic_guardrail(messages: list[dict[str, str]]) -> bool:
    context = messages[1]["content"] if len(messages) > 1 else ""
    user_message = messages[-1]["content"] if messages else ""
    lowered = user_message.lower()
    lane = "UNKNOWN"
    for line in context.splitlines():
        if line.startswith("- Current lane:"):
            lane = line.split(":", 1)[1].strip()
            break
    if lane in {"NVIDIA_PATHWAY", "TRADING_STATION", "HORSE_STEWARDSHIP", "BUSINESS_FORMATION", "CLAIRE_SYSTEM_ARCHITECTURE"}:
        return True
    if lane == "LEGAL_CASE" and any(term in lowered for term in ["sue", "lawsuit", "file", "motion", "court filing", "public entity"]):
        return True
    return any(term in lowered for term in ["officeai", "office ai", "governed runtime", "malicious skill", "supply-chain attack", "supply chain attack"])


def parse_response(raw_response: Any) -> dict[str, Any]:
    try:
        choice = (raw_response.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return {
            "content": str(msg.get("content") or "").strip(),
            "reasoning_content": str(msg.get("reasoning_content") or msg.get("reasoning") or "").strip(),
            "raw": raw_response,
        }
    except Exception as exc:
        return {"content": "", "reasoning_content": "", "raw": {"parse_error": str(exc), "response": raw_response}}


def messages_to_prompt(messages: list[dict[str, str]]) -> str:
    return "\n\n".join(f"[{m['role'].upper()}]\n{m['content']}" for m in messages)


def _deterministic_stub(messages: list[dict[str, str]]) -> str:
    context = messages[1]["content"] if len(messages) > 1 else ""
    user_message = messages[-1]["content"] if messages else ""
    lane = "UNKNOWN"
    for line in context.splitlines():
        if line.startswith("- Current lane:"):
            lane = line.split(":", 1)[1].strip()
            break

    lowered = user_message.lower()
    officeai_product = any(term in lowered for term in ["officeai", "office ai", "office-management", "office management"])
    trading_negated = any(
        term in lowered
        for term in [
            "do not pitch crypto",
            "do not pitch crypto or trading",
            "don't pitch crypto",
            "dont pitch crypto",
            "keep veritas in the background",
            "not crypto",
            "not trading",
        ]
    )
    governed_runtime_security = (
        any(term in lowered for term in ["malicious skill", "malicious functionality", "supply-chain attack", "supply chain attack"])
        and any(term in lowered for term in ["plugin", "plugins", "tool", "tools", "skill", "skills", "agent capability"])
        and any(term in lowered for term in ["governed runtime", "governed-runtime", "handshake broker", "diode", "sentinel", "trace"])
    )
    if governed_runtime_security:
        return _tool_supply_chain_fallback()
    if officeai_product:
        return _officeai_fallback()
    if lane == "HORSE_STEWARDSHIP" or "hoof" in lowered or "horse" in lowered:
        return (
            "For an exact impression of a horse hoof, look for an equine hoof impression kit or dental-grade alginate/silicone impression material used with a rigid backing tray. "
            "Clean and dry the hoof, keep the horse calm on level ground, avoid deep packing around sensitive tissue, and have a farrier or veterinarian help if the hoof is injured, sore, or irregular. "
            "For a durable display or fitting reference, make the soft impression first, then cast it with plaster, resin, or another stable casting compound."
        )
    if lane == "TRADING_STATION" or (any(term in lowered for term in ["crypto", "kraken", "veritas", "btc", "trade"]) and not trading_negated):
        if any(term in lowered for term in ["live trade", "place", "buy", "sell", "execute"]):
            return "I can review trading-system status and risk posture, but I cannot place or execute live trades from normal chat."
        return "I can summarize Veritas/Kraken status as inspection-only information. No live trading action is executed from normal chat."
    if lane == "NVIDIA_PATHWAY":
        return _nvidia_runtime_fallback()
    if lane == "LEGAL_CASE":
        if any(term in lowered for term in ["file a motion", "submit filing", "e-file", "efile", "court filing"]):
            return "Court filing actions are blocked from normal chat. I can help organize facts, issues, drafts, and questions for qualified legal review, but I cannot file or submit documents from chat."
        return _legal_cautious_fallback()
    return "I can help with that. Tell me the goal, constraints, and what outcome you want, and I will give a direct next step."


def _nvidia_runtime_fallback() -> str:
    runtime_steps = [
        "classifies the lane",
        "checks current truth",
        "recalls relevant memory through ARE",
        "builds a structured context packet",
        "applies risk and authority rules",
        "calls the downstream model",
    ]
    evidence = ["repository URL", "commit SHA", "startup commands", "benchmark or demo evidence", "validation output"]
    return (
        "CLAIRE is a governed AI runtime, not a stateless chatbot. Before the model answers, ClaireRuntime "
        + ", ".join(runtime_steps[:-1])
        + f", and {runtime_steps[-1]}. ARE is the chronological memory authority. Nemotron is downstream "
        "of orientation and context-building. Sentinel validates before final output, and Trace records the path. "
        "For NVIDIA engineers, reproducibility depends on "
        + ", ".join(evidence[:-1])
        + f", and {evidence[-1]}."
    )


def _officeai_fallback() -> str:
    return (
        "OfficeAI-500 by Claire Systems is a generic AI office-management product for teams that need governed help with routine administrative work. "
        "Likely buyers are small businesses, clinics, field-service operators, professional offices, and internal operations teams that lose time to inbox triage, document follow-up, scheduling support, task tracking, customer-response drafting, and handoff confusion. "
        "The pain point is not headcount replacement; it is fragmented office work with weak memory, unclear authority, and little auditability. "
        "CLAIRE governs those tasks by identifying the user and session, limiting recall to authorized memory scopes, exposing only permitted tools, redacting secrets before model or trace paths, validating the response before release, and recording trace evidence so office actions remain reviewable."
    )


def _tool_supply_chain_fallback() -> str:
    return (
        "The problem is agentic AI tool trust and malicious tool-supply-chain risk. As AI agents gain downloadable skills, plugins, and workflow tools, "
        "each new capability becomes a new authority relationship. An attacker does not have to compromise the model if they can persuade the agent "
        "to trust a tool that can see data, call systems, or influence downstream work.\n\n"
        "That matters now because agents are moving from text generation into office workflows, enterprise data access, ticket handling, document operations, "
        "and delegated actions. The risk shifts from model behavior alone to the runtime around the model: who is asking, which lane the request belongs to, "
        "what memory may be recalled, which tools may run, whether credentials can flow into prompts or logs, and whether the output was checked before release.\n\n"
        "This validates the Claire Systems governed-runtime approach as a relevant design response, without claiming enterprise proof. CLAIRE acts as the governed "
        "runtime around model intelligence. ARE provides memory and provenance continuity so requests are not treated as isolated context. C3RP separates lanes "
        "and tool routing so capabilities are not trusted everywhere by default. Handshake Broker ties identity and authority to the session before private recall "
        "or sensitive tools are exposed. Diode blocks credentials and private tokens from flowing backward into chat, memory, prompts, trace, or logs. Sentinel "
        "validates before output, and Trace records redacted audit evidence of the path taken.\n\n"
        "OfficeAI-500 is useful as an enterprise demo chamber because office work naturally combines memory, identity, tool permissions, credentials, validation, "
        "and auditability. It can demonstrate governed delegation without presenting CLAIRE as already enterprise-proven."
    )


def _legal_cautious_fallback() -> str:
    return (
        "I cannot make the legal decision for you, and this is not legal advice. Treat the question as a claim-screening problem: identify the specific harm, the actor or agency involved, dates, witnesses, documents, deadlines, required notice procedures, available remedies, and the practical cost of proceeding. "
        "For public-entity or court-facing matters, speak with a qualified attorney before filing or threatening action. I can help organize a timeline, evidence list, issue list, and questions for counsel, but I cannot file anything or promise an outcome from chat."
    )
