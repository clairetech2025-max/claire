# CLAIRE RUNTIME STATUS

Date: 2026-06-08
Branch: codex/claire-backend-repair
Phase: Phase One backend hook implemented, not committed

## Current Status

- Phase Zero audit complete.
- Phase One planning complete.
- Phase One backend route modules added.
- `claire_gui.py` normal chat now delegates to `claire_runtime_router.route_chat_message()`.
- Visible GUI surface remains protected; no intentional GUI-facing changes were made.

## Runtime Path

input -> normalization -> provisional orientation -> C3RP lane classification -> authority -> memory eligibility -> optional governed retrieval -> relevance projection -> Sentinel/Diode admission -> GO/provider generation -> output validation -> WriteBarrier -> trace/session persistence

## Tests

- `venv/bin/python -m py_compile claire_gui.py claire_runtime_router.py memory_eligibility.py write_barrier.py test_phase_one_runtime.py`: passed
- `venv/bin/python test_phase_one_runtime.py`: passed, 8 tests

## Known Remaining Bypass

The Python route now blocks Python-side pre-classification recall and canned final-answer handlers. The live GO fallback at `main.go` remains scripted and can still return canned keyword responses. Editing that provider was not part of the approved GUI-folder backend hook.

## Next Required Approval

Wait for `APPROVED TO COMMIT PHASE ONE` before committing or pushing.

## Hugging Face Portable Demo

- Branch: `codex/huggingface-portable-demo`.
- Deployment folder: `hf_space/`.
- Default local provider: `CLAIRE_PROVIDER=llama` using Microsoft Phi-3 Mini GGUF downloaded at build/startup.
- Public port: `7860` for CLAIRE only; llama-server binds to `127.0.0.1:8081`.
- Demo ARE history: sanitized JSONL at `hf_space/demo_data/are_mem.jsonl`.
- Model weights, private evidence, databases, credentials, and runtime memory are excluded.
- Qwen2.5 GGUF and NVIDIA NIM remain replaceable provider profiles through environment variables.

