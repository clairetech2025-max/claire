# CLAIRE

## CLAIRE Controller Contract

The controller layer proves CLAIRE as a governed runtime around a worker AI. The worker AI performs a task; CLAIRE decides whether the worker is allowed to proceed, which memory scopes it may use, which tools it may call, whether its output is safe to release, and what redacted audit evidence must be recorded.

CLAIRE governs a worker AI instead of doing everything directly to keep authority separate from task performance. This avoids turning CLAIRE into a large tool-using agent and makes the control surface explicit: task state is observed, policy is applied, actions are approved or denied, output is inspected, and trace evidence is written.

Controller lifecycle:

```text
worker state -> policy -> redaction -> tool approval -> output inspection -> trace
```

Controller tools:

- `get_state()` reads the worker AI's current task, prompt, lane, memory scope, requested tools, draft output, and status.
- `set_policy()` applies task boundaries, allowed lanes, forbidden actions, memory limits, and tool constraints.
- `approve_tool_call()` returns `ALLOW`, `DENY`, `ALLOW_READ_ONLY`, `ALLOW_DRAFT_ONLY`, or `ASK_USER_APPROVAL`.
- `inspect_output()` reviews the worker AI's proposed response before release or action.
- `redact()` removes secrets from prompts, memory, tool calls, logs, traces, and output.
- `stop_agent()` pauses the worker when it drifts, escalates authority, leaks secrets, or requests unsafe action.
- `write_trace()` records redacted audit metadata only.
- `replay_trace()` replays failed or suspicious cases for regression testing without raw secrets.

Security guarantees currently tested:

- unauthorized private memory access is denied
- malicious plugin/tool requests are denied
- secret values are redacted from state, trace, and replay
- live trading requests are blocked
- legal filing requests are blocked
- debug access without authority is denied
- authorized file/repo inspection is read-only
- email actions are draft-only
- trace replay contains capsule and audit metadata, not raw secrets

Current limits:

- demo/proof layer only
- not enterprise-proven
- worker state is mocked
- no live production actions

Run the controller tests:

```bash
python3 -m py_compile claire_controller.py test_claire_controller.py diode_protocol.py
python3 test_claire_controller.py
```
