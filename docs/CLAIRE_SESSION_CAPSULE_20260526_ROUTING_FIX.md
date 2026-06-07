# Claire Session Capsule - 2026-05-26 Routing / Conversation Fix

## Current Mission

Keep Claire 1 conversational, useful, and governed without turning her into a generic chatbot and without letting Claire 3 lesson-plan/study-guide behavior leak into Claire 1.

Do not change GUI face, voice visualizer, ARE core, Sentinel core, memory core, trace core, backend APIs, or demo visual identity.

## Live Process State

Claire GUI is running manually, not through a user systemd unit.

Current live GUI process before cutoff:

```text
/home/LuciusPrime/claire/venv/bin/python3 /home/LuciusPrime/claire/venv/bin/uvicorn claire_gui:app --host 0.0.0.0 --port 8000
PID observed: 2089399
```

Other services observed:

```text
ARE_SERVER on 127.0.0.1:8002, PID 911
claire_ingest_bridge on 127.0.0.1:8081, PID 914
Go fallback/main on 127.0.0.1:8080, PID 2036734
cloudflared points at http://127.0.0.1:8000
```

Restart pattern used:

```bash
kill <current_gui_pid>
nohup /home/LuciusPrime/claire/venv/bin/python3 /home/LuciusPrime/claire/venv/bin/uvicorn claire_gui:app --host 0.0.0.0 --port 8000 > gui.log 2>&1 &
curl -sS http://127.0.0.1:8000/health
```

## Verified Fixes Completed

- `hello Claire can you hear me` now routes to `VOICE`, not Salesforce/enterprise positioning.
- `question is there anything in that document that talks about geomagnetic navigation` now routes to `DOCUMENT`, not `WRITING`.
- `Claire can you summarize that last document for me` routes to `DOCUMENT`, not `WRITING`.
- Lesson-plan/study-guide complaint route now repairs instead of outputting the canned Claire Code Academy lesson plan.
- Voice playback has auto-resume on paused audio.
- LLM default max tokens increased from 900 to 1400 and has a completion guard to avoid mid-sentence endings.
- Tone prompt now says ordinary conversation should be warmer and less defensive.

Most recent full tests before the last interrupted broadening patch:

```text
67 tests OK
```

## Current Dirty Worktree

Observed dirty files:

```text
 M answer_planner.py
 M claire_gui.py
 M docs/CLAIRE_ARCHITECTURE_BRIEF.md
 M docs/CLAIRE_DEVELOPER_HANDOFF.md
 M docs/CLAIRE_PARTNER_EVALUATION_PACKET.md
 M docs/CLAIRE_PROOF_LAYER.md
 M main.go
 M test_memory_routing.py
?? .writer_venv/
?? "PROOF_OF_CONTINUITY - Copy-2.md"
?? docs/CLAIRE_SESSION_CAPSULE_ROOM.md
?? writer_mode/
?? docs/CLAIRE_SESSION_CAPSULE_20260526_ROUTING_FIX.md
```

Do not revert unrelated dirty files. They may be from another Codex or earlier work.

## Important Current Bug

User reports: after summarizing one ingested document, trying another document can still cause Claire to repeat the user's prompt as a polite letter:

```text
Hi,

Claire can you summarize that last document for me.

Thank you.
```

Root cause: `is_longform_writing_task()` is still too broad and can capture document/file/upload prompts before the document route. Existing guards catch some exact phrases but not all voice-transcribed variants.

## Patch That Was Started Then Interrupted

The next intended fix is classifier-level:

Any prompt that references a document/file/upload/recent/last/new/second/another item and asks to summarize, describe, read, review, analyze, explain, tell me about it, or check contents should route to `DOCUMENT`, never `WRITING`.

Add or complete helper:

```python
def is_latest_document_request_query(prompt: str) -> bool:
    cleaned = _clean_for_match(prompt)
    if not cleaned or not last_uploaded_filename():
        return False
    if re.search(r"\b(rewrite|reword|polish|proofread|edit|clean up)\b", cleaned):
        return False
    document_ref = any(marker in cleaned for marker in [
        "document", "doc", "file", "upload", "uploaded",
        "last one", "new one", "second one", "another one",
        "the one i just", "the one i uploaded",
    ])
    document_action = any(marker in cleaned for marker in [
        "summarize", "summary", "describe", "tell me about",
        "read", "review", "analyze", "explain",
        "what is in", "what's in", "what does it say",
        "what does this say", "what does that say",
        "what is this", "what's this",
    ])
    return document_ref and document_action
```

Then:

1. In `is_longform_writing_task(prompt)`, return `False` if `is_latest_document_request_query(prompt)`.
2. In `build_reply(q)`, before `is_continue_last_thought_query()` and before `is_longform_writing_task(q)`, route:

```python
if is_latest_document_request_query(q):
    document_reply = search_uploaded_documents(q)
    reply = shape_document_reply(q, document_reply) if is_useful_reply(document_reply) else document_content_not_found_reply(q)
    source = "DOCUMENT"
    return finalize_reply(q, source, reply)
```

3. Add tests:

```python
def test_broad_latest_document_requests_do_not_become_rewrite(self):
    prompts = [
        "summarize the new file",
        "describe the second document",
        "tell me about the one I just uploaded",
        "review another document for me",
    ]
```

Assert source is `DOCUMENT`, and reply does not include `Hi,` or `Thank you.`

## Existing Relevant Tests Added

In `test_memory_routing.py`:

- `test_voice_check_stays_local_not_salesforce`
- `test_document_content_followup_does_not_become_rewrite`
- `test_document_content_followup_has_no_match_fallback`
- `test_last_document_summary_requests_do_not_become_rewrite`
- `test_lesson_plan_hijack_repairs_instead_of_repeating_template`
- `test_rewrite_setup_waits_for_pasted_text`
- `test_voice_auto_resumes_paused_audio`

Run:

```bash
venv/bin/python -m py_compile claire_gui.py test_memory_routing.py
venv/bin/python test_memory_routing.py
```

## Current Design Boundary

Claire 1 should:

- converse naturally like a capable assistant
- write/rewrite well when explicitly asked
- answer normal questions directly
- use document lane for uploaded document questions
- use governance/ARE/Sentinel/trace when relevant or when demo button is used
- avoid architecture manifesto tone
- avoid repeating the user as a letter

Claire 3 / writer mode should hold:

- Code Academy
- lesson plans
- study guides
- personal assistant teaching workflows

Do not delete `writer_mode/`; just keep it out of Claire 1 default routing.

## SSH Note

User posted:

```bash
ssh LuciusPrime@20.97.65.94
```

This appears to be the Azure host access path if a new session needs to reconnect.

