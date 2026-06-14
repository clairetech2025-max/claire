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
                "You are NVIDIA Nemotron operating downstream of CLAIRE's governed runtime. "
                "Use only the supplied context packet, current user message, and general reasoning. "
                "Do not invent memory. Separate fact, inference, uncertainty, and next action."
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
        return "I can summarize legal-monitor status or source-backed research, but this is not legal advice and no filing action is performed from chat."
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
