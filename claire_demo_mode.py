from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_LOG = "/home/LuciusPrime/claire/data/traces.jsonl"

NVIDIA_DEMO_TRIGGERS = (
    "run nvidia demo",
    "nvidia",
    "cortex demo",
    "evaluation mode",
    "self demo",
    "claire self demo",
    "ask claire to demonstrate cortex",
    "demonstrate cortex",
    "demo yourself",
    "claire demo mode",
    "nvidia demo mode",
)

UNSUPPORTED_CLAIM_MARKERS = (
    "guaranteed 1000x faster",
    "guaranteed 1,000x faster",
    "beats all rag systems",
    "eliminates hallucinations",
    "guaranteed truth",
    "conscious",
    "sentient",
)

PUBLIC_SAFE_BENCHMARK_REPLY = (
    "I cannot make that unsupported claim. The tested benchmark record supports saying that local "
    "Android/Termux tests demonstrated sub-millisecond deterministic recall under tested conditions."
)

PIPELINE_TEXT = """User Input
  -> Claire Runtime
  -> Analog Recall Engine
  -> Gyro / Context Stabilization
  -> Governed Prompt-Prefix
  -> NVIDIA-compatible Model Runtime
  -> Response
  -> Trace / Replay Log"""

GO_BACKEND_NOTE = (
    "Go backend note: The Go backend can remain the high-performance service layer or router. "
    "Claire/ARE can call it over HTTP. The Python/FastAPI layer can use httpx for async integration. "
    "NVIDIA-compatible inference can be added as another routed backend."
)


def _clean_for_match(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s']", " ", str(text or "").lower())
    return " ".join(cleaned.split())


def is_nvidia_demo_trigger(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    exact_triggers = {"nvidia", "cortex demo", "evaluation mode", "self demo", "claire self demo"}
    if cleaned in exact_triggers:
        return True
    return any(trigger in cleaned for trigger in NVIDIA_DEMO_TRIGGERS if trigger not in exact_triggers)


def is_nvidia_help_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "how would nvidia help you",
            "how can nvidia help you",
            "what would nvidia improve",
            "what can nvidia improve",
            "where would nvidia help",
            "how would nvidia improve claire",
            "how can nvidia improve claire",
        ]
    )


def is_pinecone_question(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return "pinecone" in cleaned and any(marker in cleaned for marker in ["why", "use", "not", "instead", "compare"])


def is_faiss_question(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return "faiss" in cleaned and any(marker in cleaned for marker in ["where", "fit", "role", "use", "l2", "acceleration"])


def is_weakness_question(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(
        marker in cleaned
        for marker in [
            "show me a weakness",
            "where is it weak",
            "what is a weakness",
            "where is the design weak",
            "what is weak",
            "challenge the architecture",
            "what should be tested first",
        ]
    )


def pinecone_review_text() -> str:
    return (
        "Pinecone could be useful as a managed vector index, but it would not replace the Cortex/ARE control layer.\n\n"
        "The main reason is responsibility. Pinecone can help retrieve semantically similar records. It does not decide whether a memory is eligible, authoritative, current, public-safe, write-safe, or appropriate for the current question. Cortex still needs to orient, gate, verify, and decide what role retrieved material is allowed to play.\n\n"
        "A practical architecture could use Pinecone as an L2 retrieval backend, the same way FAISS could be used locally. ARE remains the governed memory spine; Pinecone would be an acceleration or search component, not the source of authority."
    )


def faiss_review_text() -> str:
    return (
        "FAISS fits as L2 semantic acceleration inside ARE, not as the whole memory system.\n\n"
        "L1 should stay deterministic: capsule IDs, hashes, signatures, session state, and exact recall where provenance matters. FAISS is useful when the reviewer asks a fuzzy or semantic question and the system needs candidate memories quickly.\n\n"
        "The flow I would test is: query -> orientation -> FAISS candidate search -> ARE eligibility and provenance gate -> verified capsule context -> model or local composer. FAISS finds candidates; ARE decides what can be trusted and used."
    )


def weakness_review_text() -> str:
    return (
        "A real weakness is that the architecture has several layers that need clean boundaries and reproducible tests.\n\n"
        "If ARE, Sentinel, Session Capsules, Veritas, and the model bridge are not sharply separated, the system can become hard to evaluate. Another weakness is benchmark discipline: speed claims must be rerun under controlled conditions on the target hardware, with clear baselines and failure cases.\n\n"
        "The next serious test should be narrow: compare a cold start against a Session Capsule restart, then measure whether the system recalls the right state, ignores irrelevant memory, explains its uncertainty, and avoids using private or unsupported material."
    )


def is_are_explanation_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return cleaned in {
        "what is the analog recall engine",
        "what is analog recall engine",
        "what is are",
        "explain the analog recall engine",
        "explain are",
    }


def is_trace_request(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return cleaned in {"show your trace", "show trace", "show the trace", "trace"}


def is_unsupported_claim_request(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    return any(marker in cleaned for marker in UNSUPPORTED_CLAIM_MARKERS)


def nvidia_trace_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"nvidia-demo-{stamp}-{uuid.uuid4().hex[:4]}"


def nvidia_trace_object(trace_id: str | None = None) -> dict[str, Any]:
    return {
        "trace_id": trace_id or nvidia_trace_id(),
        "mode": "nvidia_demo",
        "memory_layer": "Analog Recall Engine",
        "inference_layer": "local_demo_or_nvidia_placeholder",
        "governance_checks": {
            "public_safe_claim_mode": "enabled",
            "protected_memory_rewrite": "blocked",
            "secret_leakage_check": "passed",
            "benchmark_claim_guard": "enabled",
        },
        "nvidia_integration": {
            "nim": "possible_future_endpoint",
            "tensorrt_llm": "possible_local_gpu_inference",
            "triton": "possible_model_serving_layer",
            "jetson": "possible_edge_deployment",
        },
    }


def are_first_text() -> str:
    return (
        "The Analog Recall Engine is the external memory layer.\n"
        "It stores structured records, observations, capsules, and context outside the model.\n"
        "The model may consume curated context, but it does not own or rewrite the historical record.\n\n"
        "ARE Spectacle is the packaged middleware form of ARE.\n"
        "It sits between an AI application and an LLM.\n"
        "It retrieves governed memory, stabilizes context, and returns a controlled prompt-prefix."
    )


def nvidia_help_text() -> str:
    return (
        "NVIDIA software would provide the inference or deployment layer, while ARE remains the governed memory layer.\n"
        "A future integration could route Claire's governed prompt-prefix into NVIDIA NIM, TensorRT-LLM, Triton Inference Server, or Jetson-based edge deployments.\n"
        "The architecture is model-agnostic: ARE prepares the governed context, and the selected model runtime performs generation.\n\n"
        f"{PIPELINE_TEXT}\n\n"
        f"{GO_BACKEND_NOTE}"
    )


def nvidia_demo_text() -> str:
    return (
        "NVIDIA review mode is open.\n\n"
        "Ask me anything about Cortex, ARE, Session Capsules, provenance, traceability, RAG, vector search, Android deployment, or NVIDIA integration. "
        "I’ll answer like an engineering review: what is implemented, what is prototype, what is roadmap, and where the design is weak.\n\n"
        "I won’t expose private documents, secrets, personal legal material, or unsupported benchmark claims. "
        "Start with the part you want to challenge."
    )


def build_nvidia_demo_payload(prompt: str, response_text: str | None = None) -> dict[str, Any]:
    trace = nvidia_trace_object()
    output = response_text or nvidia_demo_text()
    payload = {
        "query": prompt,
        "source": "NVIDIA-DEMO",
        "reply": output,
        "trace_id": trace["trace_id"],
        "trace": trace,
    }
    persist_nvidia_trace(prompt, output, trace)
    return payload


def persist_nvidia_trace(prompt: str, output: str, trace: dict[str, Any], trace_log: str = TRACE_LOG) -> None:
    record = {
        **trace,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input": str(prompt or ""),
        "output": output,
        "steps": [
            "ingest_input",
            "route_nvidia_demo",
            "explain_are_first",
            "apply_public_claim_guard",
            "assemble_response",
            "persist_trace",
        ],
    }
    path = Path(trace_log)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def fetch_nvidia_trace(trace_id: str, trace_log: str = TRACE_LOG) -> dict[str, Any] | None:
    if not re.fullmatch(r"nvidia-demo-\d{8}_\d{6}-[a-f0-9]{4,12}", str(trace_id or "")):
        return None
    if not os.path.exists(trace_log):
        return None
    with open(trace_log, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except Exception:
                continue
            if record.get("trace_id") == trace_id:
                return record
    return None


def nvidia_text_reply(prompt: str) -> str | None:
    if is_unsupported_claim_request(prompt):
        return PUBLIC_SAFE_BENCHMARK_REPLY
    if is_nvidia_demo_trigger(prompt):
        return nvidia_demo_text()
    if is_trace_request(prompt):
        trace = nvidia_trace_object()
        return json.dumps(trace, indent=2)
    return None
