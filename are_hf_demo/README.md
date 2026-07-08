---
title: Analog Recall Engine Memory Lane Demo
emoji: 🧠
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
license: mit
---

# Analog Recall Engine Memory Lane Demo

ARE is a governed memory concept that records experiences chronologically, stamps them with checksums, and recalls prior experiences when asked.

This public Hugging Face demonstration is intentionally limited to session-scoped memory. It stores memory only during the current browser session through Gradio state. It does not claim cross-session persistence, server persistence, or 30-day retention.

## What This Demonstrates

- Create a scoped Memory Lane.
- Append demo memories into that lane.
- Stamp each memory with a deterministic checksum.
- Ask a recall question.
- Show the Memory Ledger so recall is inspectable.

## What This Does Not Include

- No FAISS or vector database.
- No production CLAIRE memory.
- No Sentinel internals.
- No Diode, Veritas, legal files, security tooling, Azure config, secrets, credentials, or API keys.
- No live external actions.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Then open the local Gradio URL, create a Memory Lane, save a demo memory, and ask a recall question.
