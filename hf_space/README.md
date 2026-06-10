---
title: CLAIRE Portable Demo
sdk: docker
app_port: 7860
pinned: false
license: other
---

# CLAIRE Portable Demo

Private Hugging Face Docker Space packaging for a sanitized CLAIRE demonstration.

This Space reconstructs CLAIRE from the authoritative GitHub branch and downloads the selected GGUF model from Hugging Face at build/startup time. Model weights, private legal evidence, user memory, databases, tokens, and credentials are not committed.

Default provider profile: local `llama-server` with Microsoft Phi-3 Mini GGUF. NVIDIA NIM and Qwen GGUF remain replaceable provider profiles through environment variables.

## Required environment

```bash
CLAIRE_PROVIDER=llama
CLAIRE_LLAMA_URL=http://127.0.0.1:8081/v1/chat/completions
CLAIRE_LOCAL_MODEL_ID=microsoft/Phi-3-mini-4k-instruct-gguf
CLAIRE_LOCAL_MODEL_FILE=Phi-3-mini-4k-instruct-q4.gguf
CLAIRE_ORIGINAL_ARE_MEM_PATH=/app/demo_data/are_mem.jsonl
```

## Security boundary

- No secrets in Git.
- No model weights in Git.
- No private runtime memory, legal evidence, databases, certificates, or `.env` files.
- llama-server binds only to `127.0.0.1:8081`; only CLAIRE is exposed on `7860`.
- Original ARE demo history is sanitized and read-only.
- Provider failure is surfaced honestly.
