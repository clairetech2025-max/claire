# Veritas Acceptance Test Results

Audit date: 2026-07-12

This file records the current evidence baseline from code inspection and live service checks. It does not claim the full restoration work is complete.

## Live service checks already observed

- `http://127.0.0.1:8000/health` returns the dark CLAIRE GUI health payload.
- `http://127.0.0.1:8000/` serves the dark `CLAIRE` workspace.
- `http://127.0.0.1:8020/veritas-legacy/` is the standalone dark Veritas shell route.
- `http://127.0.0.1:8011/veritas-mobile` serves the reduced mobile replacement.

## Current test evidence on record

- `tests/test_veritas_legal.py` proves:
  - source hashing
  - matter-scoped source IDs
  - parser JSONL adaptation
  - ZIP-slip rejection
  - timeline
  - contradiction candidates
  - review packet generation
- `tests/test_veritas_mobile_ui.py` proves:
  - the mobile slice exists and works for its narrow supported inputs
  - unsupported-file handling is readable
  - technical details are hidden behind a disclosure control
  - private-case isolation holds within the mobile slice
- `tests/test_veritas_claire_runtime.py` proves:
  - onboarding / guide mode
  - destructive-action blocking
  - bias guard guidance
  - teacher-mode correction storage
- `tests/test_veritas_court_listener.py` and `tests/test_courtlistener_client.py` prove:
  - CourtListener workflow separation
  - trace writing
  - citation lookup behavior
  - token/rate-limit handling
- `tests/test_venture_security_controls.py` proves the Venture auth/rate-limit layer currently exists, but that is separate from Veritas Legal.

## Focused verification run from this pass

Main repo:

```text
./venv/bin/python -m pytest -q tests/test_veritas_legal.py test_veritas_end_to_end.py test_claire_stream_routes.py test_veritas_mobile_ui.py
28 passed, 72 warnings in 3.59s
```

Standalone legal repo:

```text
/home/LuciusPrime/claire/venv/bin/python -m pytest -q tests/test_veritas_claire_runtime.py tests/test_veritas_court_listener.py tests/test_courtlistener_client.py
15 passed in 0.10s
```

## Current gaps relative to the full Veritas product

- no certified persistent firm profile / staff directory
- no certified resumable 10 GB matter-import session
- no certified audio/video ingest in the live legal workspace
- no certified image/photo OCR in the live legal workspace
- no certified PACER-style matter model as a single coherent product surface
- no certified front-door CLAIRE typed workflow contract

## Current verdict

The core building blocks are real. The product is not yet complete as a single, governed legal workstation. The current challenge is integration and product consolidation, not inventing every subsystem from scratch.
