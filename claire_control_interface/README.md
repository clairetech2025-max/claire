---
title: CLAIRE Control Interface
emoji: 🧭
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
license: mit
---

# CLAIRE Control Interface

This is a public-safe interface for demonstrating the CLAIRE control loop:

```text
observe -> recall -> validate -> decide -> output -> trace
```

It is intentionally limited. It is not CLAIRE herself, and it does not include private CLAIRE memory, Azure configuration, legal files, trading data, account data, security tooling, secrets, credentials, or production internals.

The dedicated public ARE Memory Module is here:

```text
https://blackstormhorse-are-memory-module.hf.space/
```

## What The Interface Demonstrates

- Public-safe demo memory.
- Session-scoped recall.
- Policy validation.
- Simulated decision only.
- Structured trace output.
- In-session trace replay.

## What It Does Not Do

- No real scheduling.
- No live actions.
- No private memory.
- No legal advice.
- No trading.
- No security scanning.
- No external account access.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```
