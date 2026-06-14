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
    if lane == "HORSE_STEWARDSHIP" or "hoof" in lowered or "horse" in lowered:
        return (
            "For an exact impression of a horse hoof, look for an equine hoof impression kit or dental-grade alginate/silicone impression material used with a rigid backing tray. "
            "Clean and dry the hoof, keep the horse calm on level ground, avoid deep packing around sensitive tissue, and have a farrier or veterinarian help if the hoof is injured, sore, or irregular. "
            "For a durable display or fitting reference, make the soft impression first, then cast it with plaster, resin, or another stable casting compound."
        )
    if lane == "TRADING_STATION" or any(term in lowered for term in ["crypto", "kraken", "veritas", "btc", "trade"]):
        if any(term in lowered for term in ["live trade", "place", "buy", "sell", "execute"]):
            return "I can review trading-system status and risk posture, but I cannot place or execute live trades from normal chat."
        return "I can summarize Veritas/Kraken status as inspection-only information. No live trading action is executed from normal chat."
    if lane == "NVIDIA_PATHWAY":
        return "Technical gate: verify current NVIDIA/Nemotron status, benchmark evidence, and next integration requirement before making a claim."
    if lane == "LEGAL_CASE":
        return "I can summarize legal-monitor status or source-backed research, but this is not legal advice and no filing action is performed from chat."
    return "I can help with that. Tell me the goal, constraints, and what outcome you want, and I will give a direct next step."
