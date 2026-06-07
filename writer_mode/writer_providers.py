"""Provider interface for Claire Writer Mode.

This module is isolated from the Claire runtime. It contains no hard-coded
secrets and falls back to local scaffold mode when a provider is unavailable.
"""

from __future__ import annotations

import json
import os
import textwrap
import urllib.error
import urllib.request
from typing import Any


FALLBACK_MESSAGE = "Claire Writer provider unavailable. Continuing in local scaffold mode."
DEFAULT_PROVIDER = "local_scaffold"
SUPPORTED_PROVIDERS = {
    "local_scaffold",
    "openai",
    "gemini",
    "claude",
    "local_http",
    "azure_headmaster",
}


def provider_config_from_env() -> dict[str, str]:
    return {
        "provider": os.getenv("CLAIRE_WRITER_PROVIDER", DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER,
        "model": os.getenv("CLAIRE_WRITER_MODEL", "").strip(),
        "api_key": os.getenv("CLAIRE_WRITER_API_KEY", "").strip(),
        "url": os.getenv("CLAIRE_WRITER_URL", "").strip(),
    }


def normalize_config(provider_config: dict[str, Any] | None) -> dict[str, str]:
    env_config = provider_config_from_env()
    if provider_config:
        for key in ("provider", "model", "api_key", "url"):
            value = provider_config.get(key)
            if value is not None and str(value).strip():
                env_config[key] = str(value).strip()
    env_config["provider"] = env_config.get("provider", DEFAULT_PROVIDER).lower()
    if env_config["provider"] not in SUPPORTED_PROVIDERS:
        env_config["provider"] = DEFAULT_PROVIDER
    return env_config


def generate_draft(prompt: str, source_text: str, provider_config: dict[str, Any] | None = None) -> str:
    config = normalize_config(provider_config)
    if config["provider"] == "local_scaffold":
        return local_scaffold("draft", prompt, source_text)
    return generate_remote("draft", prompt, source_text, config)


def generate_brief(prompt: str, source_text: str, provider_config: dict[str, Any] | None = None) -> str:
    config = normalize_config(provider_config)
    if config["provider"] == "local_scaffold":
        return local_scaffold("brief", prompt, source_text)
    return generate_remote("brief", prompt, source_text, config)


def writer_instruction(kind: str, prompt: str, source_text: str) -> str:
    return textwrap.dedent(
        f"""
        You are Claire Writer Mode.

        Task type: {kind}
        User prompt:
        {prompt}

        Required craft standard:
        - Produce excellent prose with compression, clarity, tension, rhythm, and controlled detail.
        - Use plainspoken strength, precise observation, lyric restraint, and procedural clarity where appropriate.
        - Preserve Steve's direct, gritty, honest voice.
        - Do not imitate any author verbatim.
        - Do not invent people, dates, places, events, technical facts, credentials, or claims.
        - Mark uncertain or missing areas as [NEEDS REVIEW].
        - Every output must include: Draft for human review.
        - Nothing is published, emailed, uploaded, or approved.

        Source material:
        {source_text}
        """
    ).strip()


def local_scaffold(kind: str, prompt: str, source_text: str) -> str:
    source = source_text.strip() or "[NEEDS REVIEW] No source text provided."
    if kind == "brief":
        return textwrap.dedent(
            f"""
            # Draft for human review

            ## Plain-English Lead

            [NEEDS REVIEW] Write the clearest possible explanation of the topic using only verified source material.

            ## Controlled Architecture / Topic Notes

            {source}

            ## Partner-Facing Shape

            - Problem: [NEEDS REVIEW]
            - What Claire does: [NEEDS REVIEW]
            - Evidence or proof: [NEEDS REVIEW]
            - Boundaries: no hype-only claims, no confidential source code, no patent over-disclosure.

            ## Human Review Checklist

            - Confirm facts.
            - Remove unsupported claims.
            - Keep the language clean, strong, and specific.
            - Approve manually before external use.
            """
        ).strip()

    return textwrap.dedent(
        f"""
        # Draft for human review

        ## Opening

        [NEEDS REVIEW] Build the opening from Steve's source material. Keep it direct, vivid, and true.

        ## Source Material To Shape

        {source}

        ## Chapter Movement

        1. Where this part begins. [NEEDS REVIEW]
        2. What pressure, work, failure, or discovery drives it. [NEEDS REVIEW]
        3. What Steve learned. [NEEDS REVIEW]
        4. How it connects to Claire or the current project. [NEEDS REVIEW]

        ## Revision Notes

        - Preserve Steve's voice.
        - Cut anything that sounds corporate or invented.
        - Add only facts present in the transcript or later approved by Steve.
        """
    ).strip()


def generate_remote(kind: str, prompt: str, source_text: str, config: dict[str, str]) -> str:
    try:
        provider = config["provider"]
        if provider == "openai":
            return call_openai(kind, prompt, source_text, config)
        if provider == "gemini":
            return call_gemini(kind, prompt, source_text, config)
        if provider == "claude":
            return call_claude(kind, prompt, source_text, config)
        if provider in {"local_http", "azure_headmaster"}:
            return call_generic_http(kind, prompt, source_text, config)
    except Exception:
        print(FALLBACK_MESSAGE)
        return local_scaffold(kind, prompt, source_text)

    print(FALLBACK_MESSAGE)
    return local_scaffold(kind, prompt, source_text)


def call_openai(kind: str, prompt: str, source_text: str, config: dict[str, str]) -> str:
    url = config.get("url") or "https://api.openai.com/v1/chat/completions"
    model = config.get("model") or "gpt-4.1"
    api_key = require_api_key(config)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are Claire Writer Mode. Return markdown only."},
            {"role": "user", "content": writer_instruction(kind, prompt, source_text)},
        ],
        "temperature": 0.35,
    }
    data = post_json(url, payload, {"Authorization": f"Bearer {api_key}"})
    choices = data.get("choices") if isinstance(data, dict) else None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        return str(message.get("content") or choices[0].get("text") or "").strip()
    return parse_common_response(data)


def call_gemini(kind: str, prompt: str, source_text: str, config: dict[str, str]) -> str:
    model = config.get("model") or "gemini-1.5-pro"
    api_key = require_api_key(config)
    url = config.get("url") or f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": writer_instruction(kind, prompt, source_text)}],
            }
        ],
        "generationConfig": {"temperature": 0.35},
    }
    data = post_json(url, payload, {})
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if isinstance(candidates, list) and candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(str(part.get("text", "")) for part in parts).strip()
    return parse_common_response(data)


def call_claude(kind: str, prompt: str, source_text: str, config: dict[str, str]) -> str:
    url = config.get("url") or "https://api.anthropic.com/v1/messages"
    model = config.get("model") or "claude-3-5-sonnet-latest"
    api_key = require_api_key(config)
    payload = {
        "model": model,
        "max_tokens": 4000,
        "temperature": 0.35,
        "system": "You are Claire Writer Mode. Return markdown only.",
        "messages": [{"role": "user", "content": writer_instruction(kind, prompt, source_text)}],
    }
    data = post_json(
        url,
        payload,
        {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    content = data.get("content") if isinstance(data, dict) else None
    if isinstance(content, list):
        return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict)).strip()
    return parse_common_response(data)


def call_generic_http(kind: str, prompt: str, source_text: str, config: dict[str, str]) -> str:
    url = config.get("url")
    if not url:
        raise ValueError("CLAIRE_WRITER_URL is required for local_http or azure_headmaster")
    payload = {
        "prompt": writer_instruction(kind, prompt, source_text),
        "source_text": source_text,
        "model": config.get("model", ""),
        "mode": "writer",
        "kind": kind,
    }
    headers = {}
    if config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"
    data = post_json(url, payload, headers)
    return parse_common_response(data)


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"text": raw}


def parse_common_response(data: Any) -> str:
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, dict):
        return ""
    for key in ("response", "output", "text", "answer", "result", "content"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def require_api_key(config: dict[str, str]) -> str:
    api_key = config.get("api_key", "").strip()
    if not api_key:
        raise ValueError("CLAIRE_WRITER_API_KEY is required for this provider")
    return api_key
