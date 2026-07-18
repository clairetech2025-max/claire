from __future__ import annotations

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_are.gateway import GovernedGateway

try:
    import gradio as gr
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install gradio to run the Hugging Face demo.") from exc


store = AREStore(AREConfig.from_env())
gateway = GovernedGateway(store)


def ingest_memory(text: str, lane: str, source: str) -> str:
    result = store.ingest(text=text, lane=lane, source=source or "hf_demo", metadata={"ui": "hf_demo"})
    return f"{result['status']} sha={result['sha']} truth_hash={result['truth_hash'][:16]}"


def recall_memory(query: str, lane: str) -> tuple[str, list[list[str]]]:
    result = store.recall(query=query, lane=lane, limit=8)
    rows = [[item["sha"], item["lane"], item["source"], item["text"][:160]] for item in result["memories"]]
    return f"recall_event_sha={result['recall_event_sha']}", rows


def ask_with_recall(prompt: str, lane: str) -> str:
    result = gateway.complete(prompt=prompt, lane=lane, model="local/stub", metadata={"ui": "hf_demo"})
    return result["answer"] + f"\n\nrecall_event_sha={result['recall_event_sha']}\ncompletion_event_sha={result['completion_event_sha']}"


def audit_rows() -> list[list[str]]:
    rows = []
    for event in store.audit_recent(limit=20):
        payload = event.get("payload") or {}
        rows.append([
            str(event.get("sequence")),
            str(payload.get("event_type")),
            str(payload.get("lane")),
            str(payload.get("source")),
            str(event.get("truth_hash"))[:16],
            str(payload.get("text"))[:160],
        ])
    return rows


def verify_memory() -> str:
    return str(store.verify())


with gr.Blocks(title="CLAIRE ARE Memory Module") as demo:
    gr.Markdown("# CLAIRE ARE Memory Module\nGoverned, verified, lane-scoped memory. Session storage depends on the Space runtime configuration.")
    lane = gr.Dropdown(["general", "architecture", "legal", "business"], value="general", label="Memory lane")
    with gr.Tab("Ingest Memory"):
        text = gr.Textbox(label="Memory text", lines=4)
        source = gr.Textbox(label="Source", value="hf_demo")
        out = gr.Textbox(label="Ingest result")
        gr.Button("Ingest").click(ingest_memory, [text, lane, source], out)
    with gr.Tab("Recall Memory"):
        query = gr.Textbox(label="Recall query", lines=2)
        recall_status = gr.Textbox(label="Recall event")
        recall_table = gr.Dataframe(headers=["sha", "lane", "source", "preview"], label="Matching memories")
        gr.Button("Recall").click(recall_memory, [query, lane], [recall_status, recall_table])
    with gr.Tab("Ask With Governed Recall"):
        prompt = gr.Textbox(label="Prompt", lines=3)
        answer = gr.Textbox(label="Answer", lines=8)
        gr.Button("Ask").click(ask_with_recall, [prompt, lane], answer)
    with gr.Tab("Audit / Verify"):
        audit = gr.Dataframe(headers=["seq", "type", "lane", "source", "truth_hash", "preview"], label="Recent audit")
        verify = gr.Textbox(label="Integrity")
        gr.Button("Refresh Audit").click(audit_rows, outputs=audit)
        gr.Button("Verify Memory").click(verify_memory, outputs=verify)


if __name__ == "__main__":
    demo.launch()
