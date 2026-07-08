"""Hugging Face Spaces package for the public ARE Memory Lane demo."""

from __future__ import annotations

import gradio as gr

from are_store import (
    AREDemoStore,
    create_lane,
    ledger_rows,
    memory_rows,
    new_store,
    recall_memory,
    save_memory,
)


LEDGER_HEADERS = [
    "timestamp",
    "event type",
    "lane code",
    "checksum",
    "memory preview",
    "recall query",
    "recall result",
    "expiration",
]

MEMORY_HEADERS = ["timestamp", "checksum", "memory preview"]
SIMPLE_LEDGER_HEADERS = ["event", "detail"]


def blank_outputs(store: AREDemoStore | None = None):
    return (
        store or new_store(),
        "No Memory Lane is open yet.",
        [],
        [],
        "Create a Memory Lane to begin.",
        "Nominal State",
        "5,000 memories",
    )


def simple_ledger_rows(store: AREDemoStore | None) -> list[list[str]]:
    if not store:
        return []
    rows: list[list[str]] = []
    for row in store.ledger[-8:]:
        detail = row.get("memory_preview") or row.get("recall_query") or row.get("recall_result") or row.get("lane_code") or ""
        if row.get("recall_result"):
            detail = row["recall_result"]
        rows.append([row["event_type"].replace("_", " "), detail])
    return rows


def memory_pressure(available_kb: int):
    if available_kb < 350_000:
        return "Critical throttling", "500 memories"
    if available_kb < 600_000:
        return "Warning active", "2,000 memories"
    return "Nominal State", "5,000 memories"


def ui_create_lane(store: AREDemoStore | None):
    store, lane = create_lane(store)
    narrative = (
        f"Memory Lane created: {lane}\n\n"
        "This code identifies the session lane. It does not directly retrieve one note. "
        "Recall still searches the prior memories recorded in this lane."
    )
    return store, lane, memory_rows(store), simple_ledger_rows(store), ledger_rows(store), narrative


def ui_save_memory(store: AREDemoStore | None, text: str):
    try:
        store, record = save_memory(store, text)
        narrative = (
            "Create Memory completed.\n\n"
            f'ARE appended prior experience: "{record["memory_preview"]}"\n'
            f"Checksum: {record['checksum']}\n"
            "The event is now visible in the Memory Ledger."
        )
        return store, memory_rows(store), simple_ledger_rows(store), ledger_rows(store), narrative, ""
    except Exception as exc:
        return store or new_store(), memory_rows(store), simple_ledger_rows(store), ledger_rows(store), f"Memory was not saved: {exc}", text


def ui_recall_memory(store: AREDemoStore | None, query: str):
    try:
        store, result = recall_memory(store, query)
        narrative = (
            "Recall Memory completed.\n\n"
            f"Question: {query}\n"
            f"Recall Result: {result['recall_result']}\n\n"
            "ARE searched the opened lane chronologically and returned a matching prior experience if one existed."
        )
        return store, simple_ledger_rows(store), ledger_rows(store), result["recall_result"], narrative
    except Exception as exc:
        return store or new_store(), simple_ledger_rows(store), ledger_rows(store), f"Recall failed: {exc}", f"Recall failed: {exc}"


def ui_reset_session():
    store = new_store()
    return (
        store,
        "Session reset. No Memory Lane is open.",
        [],
        [],
        [],
        "Session memory cleared. Create a new Memory Lane to begin.",
        "",
        "",
    )


CSS = """
.gradio-container {
  max-width: 760px !important;
  font-size: 16px !important;
}
#are-title h1 {
  font-size: clamp(26px, 7vw, 32px) !important;
  line-height: 1.1 !important;
  margin-bottom: 8px !important;
}
#are-title p, #are-title li {
  font-size: 17px !important;
  line-height: 1.45 !important;
}
.mobile-card {
  border: 1px solid #d6e3ef;
  border-radius: 12px;
  padding: 18px;
  background: rgba(255,255,255,0.72);
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
.compact-note {
  font-size: 16px !important;
  line-height: 1.45 !important;
}
@media (max-width: 720px) {
  .gradio-container {
    padding-left: 12px !important;
    padding-right: 12px !important;
  }
  #are-title h1 {
    font-size: 28px !important;
  }
  .mobile-card {
    padding: 14px;
  }
  .gr-form, .gr-box, .block {
    min-width: 0 !important;
  }
  .mobile-card h2, .mobile-card h3 {
    font-size: 21px !important;
  }
}
"""


with gr.Blocks(theme=gr.themes.Soft(primary_hue="cyan", neutral_hue="slate"), css=CSS, title="Analog Recall Engine Demo") as demo:
    store_state = gr.State(new_store())

    gr.Markdown(
        """
# ARE Memory Demo

Create a memory lane, save a memory, ask a question, and see whether ARE recalls the matching prior memory.

**This demo memory lasts only during this session.**
""",
        elem_id="are-title",
    )

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 1: Create Memory Lane")
        lane_display = gr.Textbox(value="No Memory Lane is open yet.", label="Active Lane", interactive=False)
        create_lane_btn = gr.Button("Create Memory Lane", variant="primary")

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 2: Create Memory")
        memory_input = gr.Textbox(
            label="Demo Memory",
            lines=3,
            placeholder="Example: My dog eats red ice cream.",
        )
        save_btn = gr.Button("Create Memory", variant="primary")

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 3: Recall Memory")
        recall_query = gr.Textbox(label="Recall Question", placeholder="What did I say about my dog?")
        recall_btn = gr.Button("Recall Memory", variant="primary")

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 4: View Result")
        recall_result = gr.Textbox(label="Result", lines=3, interactive=False)

    with gr.Group(elem_classes="mobile-card"):
        gr.Markdown("## Step 5: View Memory Ledger")
        simple_ledger = gr.Dataframe(
            headers=SIMPLE_LEDGER_HEADERS,
            value=[],
            datatype=["str", "str"],
            interactive=False,
            wrap=True,
            label="Recent Memory Events",
        )

    with gr.Accordion("Show Technical Details", open=False):
        gr.Markdown("Checksums, timestamps, internal ledger rows, and memory mode are shown here for technical review.")
        narrative = gr.Textbox(
            value="Create a Memory Lane to begin.",
            label="Running Narrative",
            lines=5,
            interactive=False,
        )
        memories = gr.Dataframe(
            headers=MEMORY_HEADERS,
            value=[],
            datatype=["str", "str", "str"],
            interactive=False,
            wrap=True,
            label="Append-First Memory Records",
        )
        ledger = gr.Dataframe(
            headers=LEDGER_HEADERS,
            value=[],
            datatype=["str"] * len(LEDGER_HEADERS),
            interactive=False,
            wrap=True,
            label="Full Memory Ledger",
        )
        ram = gr.Slider(200_000, 1_000_000, value=800_000, step=10_000, label="Pretend Computer Memory Available (KB)")
        mode = gr.Textbox(value="Nominal State", label="Memory Mode", interactive=False)
        retain = gr.Textbox(value="5,000 memories", label="Active Retain Window", interactive=False)

    reset_btn = gr.Button("Reset Session Memory")

    ram.change(memory_pressure, inputs=ram, outputs=[mode, retain])
    create_lane_btn.click(
        ui_create_lane,
        inputs=store_state,
        outputs=[store_state, lane_display, memories, simple_ledger, ledger, narrative],
    )
    save_btn.click(
        ui_save_memory,
        inputs=[store_state, memory_input],
        outputs=[store_state, memories, simple_ledger, ledger, narrative, memory_input],
    )
    recall_btn.click(
        ui_recall_memory,
        inputs=[store_state, recall_query],
        outputs=[store_state, simple_ledger, ledger, recall_result, narrative],
    )
    reset_btn.click(
        ui_reset_session,
        inputs=None,
        outputs=[store_state, lane_display, memories, simple_ledger, ledger, narrative, memory_input, recall_result],
    )


if __name__ == "__main__":
    demo.launch()
