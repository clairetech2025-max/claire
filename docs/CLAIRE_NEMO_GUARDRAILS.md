# CLAIRE NeMo Guardrails

This installs NVIDIA NeMo Guardrails as an optional guardrail layer for Claire.

It must not replace Cortex, ARE, Sentinel, Veritas, Session Capsules, or trace.

Intended placement:

```text
Question
-> Orientation
-> ARE recall
-> Sentinel / relevance gate
-> Model synthesis if needed
-> NeMo output guardrail
-> Trace
-> Claire response
```

Current status:

- `nemoguardrails` is installed in Claire's Python virtualenv.
- Claire-specific config exists at `guardrails/claire/`.
- Offline safety helper exists at `claire_guardrails.py`.
- Offline test harness exists at `scripts/test_claire_guardrails.py`.
- NeMo is not wired into the live chat path yet.

Run checks:

```bash
cd /home/LuciusPrime/claire
venv/bin/python scripts/test_claire_guardrails.py
venv/bin/python - <<'PY'
from nemoguardrails import RailsConfig
RailsConfig.from_path("guardrails/claire")
print("NeMo config loaded")
PY
```

Rules:

- NeMo guards visible output.
- NeMo does not decide memory truth.
- NeMo does not replace Sentinel.
- NeMo does not own Claire's identity.
- NeMo must not turn Claire into a generic chatbot.
