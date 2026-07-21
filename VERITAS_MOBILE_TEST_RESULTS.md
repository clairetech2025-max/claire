# Veritas Mobile Test Results

## Environment

- Working directory: `/home/LuciusPrime/claire`
- Python environment: `venv/bin/python`
- Test data: synthetic controlled text evidence only
- Private Steve documents ingested: no
- Azure BLUE changed: no

## Mobile Smoke Workflow Result

Executed with FastAPI `TestClient` against `claire_gui.app`.

Result:

```text
home 200 True
create 200 created
upload 200 processed 1 1 1 None
search 200 1
timeline 200 1
ask 200 answered 1
report 200 saved 20260712_034908_document_index.md None
```

This proves:

- `/veritas-mobile` loads.
- A case can be created.
- A TXT document can be processed.
- Dates, people, and rules can be extracted.
- Search returns source-linked results.
- Timeline returns a source-linked event.
- Ask Veritas returns a case-backed answer with a source.
- Document Index report is saved.

## Commands Run

```bash
venv/bin/python -m py_compile claire_gui.py
```

Result:

```text
pass
```

```bash
venv/bin/python -m pytest -q test_veritas_mobile_ui.py
```

Result:

```text
11 passed, 60 warnings in 2.44s
```

```bash
venv/bin/python -m py_compile claire_gui.py && venv/bin/python -m pytest -q tests/test_veritas_legal.py test_claire_stream_routes.py test_veritas_mobile_ui.py
```

Result:

```text
25 passed, 60 warnings in 3.08s
```

```bash
venv/bin/python -m pytest -q test_session_continuity.py test_conversation_continuity.py test_green_restart_continuity.py test_veritas_end_to_end.py tests/test_veritas_legal.py claire_are/tests/test_plugin_are.py test_governed_runtime.py test_memory_routing.py test_claire_stream_routes.py test_veritas_mobile_ui.py
```

Result:

```text
111 passed, 171 warnings in 19.53s
```

## New Tests Added

- `test_mobile_home_loads_with_android_first_controls`
  - Verifies the mobile home loads, viewport is present, primary actions exist, tap targets are sized, and developer labels are not on the home page.
- `test_new_case_flow_and_case_dashboard`
  - Verifies case creation and dashboard empty-state behavior.
- `test_upload_success_extracts_plain_english_results`
  - Verifies upload, parser processing, source record creation, extracted date/person/rule counts, source hash, and ARE event reference.
- `test_upload_failure_is_readable_and_not_success`
  - Verifies unsupported image upload fails clearly and does not appear successful.
- `test_document_detail_hides_technical_data_behind_details`
  - Verifies document detail includes extracted facts and technical provenance is available for the advanced section.
- `test_natural_language_search_returns_source_linked_result`
  - Verifies natural-language search returns a source-linked evidence result.
- `test_timeline_source_linkage`
  - Verifies timeline events include date, source document ID, and ARE event reference.
- `test_ask_veritas_uses_case_sources_and_not_demo_path`
  - Verifies Ask Veritas uses case evidence, returns sources, includes boundary language, and does not use demo/canned output.
- `test_report_creation_saves_reopenable_source_referenced_report`
  - Verifies report file creation and source references.
- `test_unsupported_controls_are_not_advertised_as_working`
  - Verifies photo/OCR controls are not advertised as working.
- `test_private_case_isolation`
  - Verifies evidence from one mobile case is not searchable from another.

## Warnings

Warnings are deprecation warnings from existing `datetime.utcnow()` usage and PyPDF2 deprecation. They did not fail the suite.

## Android Viewport Coverage

The automated tests verify the mobile viewport meta tag, fixed bottom navigation, full-width action controls, and minimum tap-target CSS. Browser-level screenshot testing on an actual Android device is still a manual acceptance step.

Playwright is not installed in the project virtualenv, so no automated screenshot was captured in this run.

## Local Test Server

A separate test server was started without changing production routing:

```bash
setsid bash -lc 'cd /home/LuciusPrime/claire && exec venv/bin/uvicorn claire_gui:app --host 0.0.0.0 --port 8011 > /tmp/veritas_mobile_8011.log 2>&1' &
```

Verification:

```text
LISTEN 0      2048         0.0.0.0:8011       0.0.0.0:*    users:(("uvicorn",pid=3593283,fd=7))
200 15543
```

Local URL:

```text
http://127.0.0.1:8011/veritas-mobile
```

Phone URL on the same reachable network:

```text
http://<vm-public-host-or-ip>:8011/veritas-mobile
```
