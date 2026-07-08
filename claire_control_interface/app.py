"""Public-safe CLAIRE Control Interface for Hugging Face Spaces.

This is not production CLAIRE. It is a controlled demo of the public pipeline:
observe -> recall -> validate -> decide -> output -> trace.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import gradio as gr


TRACE_HEADERS = ["timestamp", "trace id", "input", "recall", "policy", "decision"]
SIMPLE_TRACE_HEADERS = ["step", "result"]
MEMORY_HEADERS = ["timestamp", "checksum", "memory preview"]
ARE_SPACE_URL = "https://blackstormhorse-are-memory-module.hf.space/"


@dataclass
class ClairePublicState:
    memories: list[dict[str, str]] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def short_checksum(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:12]


def clean_text(text: str, limit: int = 500) -> str:
    return " ".join(str(text or "").split())[:limit]


def trace_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"trace_{stamp}_{uuid.uuid4().hex[:4]}"


def secret_risk(text: str) -> bool:
    patterns = [
        r"api[_-]?key",
        r"secret",
        r"password",
        r"passphrase",
        r"token",
        r"private[_-]?key",
        r"access[_-]?token",
        r"refresh[_-]?token",
        r"bearer\s+[a-z0-9._-]+",
        r"sk-[a-z0-9_-]{12,}",
    ]
    return any(re.search(pattern, text or "", re.I) for pattern in patterns)


def new_state() -> ClairePublicState:
    return ClairePublicState()


def save_demo_memory(state: ClairePublicState | None, memory_text: str):
    state = state or new_state()
    memory = clean_text(memory_text)
    if not memory:
        return state, memory_rows(state), "Type a safe demo memory first.", ""
    if secret_risk(memory):
        return state, memory_rows(state), "Blocked: do not put secrets, credentials, private facts, or account data into this public demo.", memory_text
    record = {"timestamp": utc_ts(), "checksum": short_checksum(memory), "memory": memory, "preview": memory[:140]}
    state.memories.append(record)
    return state, memory_rows(state), f"Saved demo memory with checksum {record['checksum']}.", ""


def recall_support(state: ClairePublicState, user_input: str) -> dict[str, Any]:
    query_terms = {term for term in re.findall(r"[a-z0-9]+", user_input.lower()) if len(term) >= 3}
    if not query_terms or not state.memories:
        return {"status": "none", "summary": "No relevant prior memory found.", "items": []}
    scored = []
    for row in state.memories:
        memory_terms = {term for term in re.findall(r"[a-z0-9]+", row["memory"].lower()) if len(term) >= 3}
        overlap = query_terms & memory_terms
        if overlap:
            scored.append((len(overlap), row))
    scored.sort(key=lambda item: (item[0], item[1]["timestamp"]), reverse=True)
    if not scored:
        return {"status": "none", "summary": "No relevant prior memory found.", "items": []}
    best = scored[0][1]
    return {
        "status": "found",
        "summary": f"Found one relevant public demo memory: {best['preview']}",
        "items": [{"timestamp": best["timestamp"], "checksum": best["checksum"], "preview": best["preview"]}],
    }


def validate_policy(user_input: str) -> dict[str, Any]:
    text = user_input.lower()
    rules = []
    if secret_risk(user_input):
        rules.append("protect_secrets")
    if any(term in text for term in ["hack", "steal", "phish", "malware", "withdraw", "place a trade", "buy bitcoin for me"]):
        rules.append("block_real_or_unsafe_action")
    if rules:
        return {"status": "blocked", "summary": "Public demo blocked unsafe, private, credential, or real-world action content.", "rules_triggered": rules}
    return {"status": "allowed", "summary": "No policy constraints violated for public simulation.", "rules_triggered": []}


def decide_and_output(user_input: str, recall: dict[str, Any], policy: dict[str, Any]) -> tuple[str, str]:
    if policy["status"] == "blocked":
        return (
            "Blocked public demo action.",
            "I cannot perform or simulate unsafe/private actions here. Use this demo with synthetic, public-safe inputs only.",
        )
    if "horseback" in user_input.lower() or "schedule" in user_input.lower():
        return (
            "Simulated action only.",
            "CLAIRE would simulate the scheduling workflow for demonstration only. No calendar, booking, payment, message, or real-world action was performed.",
        )
    if recall["status"] == "found":
        return (
            "Answer with governed recall support.",
            f"CLAIRE found relevant prior demo memory and used it as support: {recall['summary']}",
        )
    return (
        "Answer from public demo pipeline.",
        "CLAIRE observed the input, checked demo memory, passed policy validation, and produced a simulated traceable response.",
    )


def run_claire_demo(state: ClairePublicState | None, user_input: str):
    state = state or new_state()
    text = clean_text(user_input, 800)
    if not text:
        return state, {}, "Type a public-safe demo input first.", "No memory checked yet.", simple_trace_rows(state), trace_rows(state)
    tid = trace_id()
    recall = recall_support(state, text)
    policy = validate_policy(text)
    decision, output = decide_and_output(text, recall, policy)
    trace = {
        "trace_id": tid,
        "timestamp": utc_ts(),
        "demo_mode": True,
        "identity": "CLAIRE public demo: observe, recall, validate, decide, output, trace.",
        "input_received": text,
        "recall_check": recall,
        "policy_validation": policy,
        "decision": decision,
        "output": output,
        "trace_summary": {
            "steps_executed": ["ingest_input", "retrieve_memory", "validate_policy", "generate_response", "persist_trace"],
            "decisions_made": [decision],
        },
    }
    state.traces.append(trace)
    return state, trace, output, memory_used_text(recall), simple_trace_rows(state), trace_rows(state)


def memory_rows(state: ClairePublicState | None) -> list[list[str]]:
    if not state:
        return []
    return [[row["timestamp"], row["checksum"], row["preview"]] for row in state.memories]


def trace_rows(state: ClairePublicState | None) -> list[list[str]]:
    if not state:
        return []
    rows = []
    for row in state.traces:
        rows.append(
            [
                row["timestamp"],
                row["trace_id"],
                row["input_received"],
                row["recall_check"]["status"],
                row["policy_validation"]["status"],
                row["decision"],
            ]
        )
    return rows


def simple_trace_rows(state: ClairePublicState | None) -> list[list[str]]:
    if not state or not state.traces:
        return []
    row = state.traces[-1]
    return [
        ["Trace", row["trace_id"]],
        ["Decision", row["decision"]],
        ["Policy", row["policy_validation"]["status"]],
    ]


def memory_used_text(recall: dict[str, Any] | None) -> str:
    recall = recall or {}
    if recall.get("status") == "found":
        return str(recall.get("summary") or "Memory was used.")
    if recall.get("status") == "error":
        return "Memory check had an error."
    return "No matching demo memory was used."


def replay_trace(state: ClairePublicState | None, requested_trace_id: str):
    state = state or new_state()
    wanted = clean_text(requested_trace_id, 120)
    for row in state.traces:
        if row["trace_id"] == wanted:
            return row
    return {"error": "Trace not found in this browser session."}


def reset_session():
    state = new_state()
    return state, [], [], [], {}, "", "", "No memory checked yet."


CSS = """
.gradio-container {
  max-width: 760px !important;
  font-size: 16px !important;
}
#claire-title h1 {
  font-size: clamp(26px, 7vw, 32px) !important;
  line-height: 1.1 !important;
  margin-bottom: 8px !important;
}
#claire-title p, #claire-title li {
  font-size: 17px !important;
  line-height: 1.45 !important;
}
.mobile-card {
  border: 1px solid #d8e0ec;
  border-radius: 12px;
  padding: 18px;
  background: rgba(255,255,255,0.74);
  margin-bottom: 16px;
}
.mobile-card h2, .mobile-card h3 {
  font-size: 22px !important;
  line-height: 1.2 !important;
}
.gr-button {
  width: 100% !important;
  min-height: 52px !important;
  font-size: 16px !important;
  white-space: normal !important;
}
textarea, input, .wrap, .prose, .markdown-body {
  font-size: 16px !important;
}
.gradio-container .dataframe, .gradio-container table {
  max-width: 100% !important;
}
.gradio-container table {
  table-layout: fixed !important;
}
.gradio-container td, .gradio-container th {
  white-space: normal !important;
  word-break: break-word !important;
  overflow-wrap: anywhere !important;
  font-size: 15px !important;
}
@media (max-width: 720px) {
  .gradio-container {
    padding-left: 12px !important;
    padding-right: 12px !important;
  }
  #claire-title h1 {
    font-size: 28px !important;
  }
  .mobile-card {
    padding: 14px;
  }
  .gr-form, .gr-box, .block {
    min-width: 0 !important;
  }
}
"""


with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"), css=CSS, title="CLAIRE Control Interface") as demo:
    state = gr.State(new_state())
    gr.Markdown(
        f"""
# CLAIRE Control Interface

Ask CLAIRE a question and see the response, memory check, and trace.

**This demo memory lasts only during this session.**

ARE Memory Module: [{ARE_SPACE_URL}]({ARE_SPACE_URL})
""",
        elem_id="claire-title",
    )

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 1: Ask CLAIRE")
        demo_input = gr.Textbox(
            lines=3,
            label="Question",
            value="Schedule a horseback ride tomorrow at 10am",
            placeholder="Use public-safe synthetic inputs only.",
        )
        run_btn = gr.Button("Ask CLAIRE", variant="primary")

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 2: Response")
        response = gr.Markdown("No response yet.")

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 3: Memory Used")
        memory_used = gr.Markdown("No memory checked yet.")

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 4: Trace")
        simple_trace = gr.Dataframe(
            headers=SIMPLE_TRACE_HEADERS,
            value=[],
            datatype=["str", "str"],
            interactive=False,
            wrap=True,
            label="Latest Trace",
        )

    with gr.Accordion("Optional: Add Demo Memory", open=False):
        memory_input = gr.Textbox(lines=3, label="Safe Demo Memory", placeholder="Example: I like red ice cream.")
        save_memory_btn = gr.Button("Save Demo Memory", variant="primary")
        memory_status = gr.Textbox(label="Memory Status", interactive=False)
        memory_table = gr.Dataframe(headers=MEMORY_HEADERS, value=[], datatype=["str", "str", "str"], interactive=False, wrap=True)

    with gr.Accordion("Show Technical Details", open=False):
        gr.Markdown("JSON trace and full ledger details for technical review.")
        trace_json = gr.JSON(label="Structured Trace")
        trace_table = gr.Dataframe(headers=TRACE_HEADERS, value=[], datatype=["str"] * len(TRACE_HEADERS), interactive=False, wrap=True)
        trace_lookup = gr.Textbox(label="Trace ID", placeholder="trace_...")
        replay_btn = gr.Button("Replay Trace")
        reset_btn = gr.Button("Reset Session")

    save_memory_btn.click(save_demo_memory, inputs=[state, memory_input], outputs=[state, memory_table, memory_status, memory_input])
    run_btn.click(run_claire_demo, inputs=[state, demo_input], outputs=[state, trace_json, response, memory_used, simple_trace, trace_table])
    replay_btn.click(replay_trace, inputs=[state, trace_lookup], outputs=trace_json)
    reset_btn.click(reset_session, inputs=None, outputs=[state, memory_table, simple_trace, trace_table, trace_json, response, memory_status, memory_used])


if __name__ == "__main__":
    demo.launch()
