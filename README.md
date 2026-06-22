# Claire

Claire is a governed memory-first AI architecture designed for persistent recall, governed continuity, provenance tracing, and orientation before generation.

This repository is the private engineering workspace for Claire's live demo, ARE memory runtime, governance experiments, documentation package, and market/evidence assets.

## Current Positioning

Claire is not a generic chatbot, CRM copilot, native Salesforce product, or standard RAG wrapper.

Claire's core principle:

> Orient before generate.

The system is designed to separate:

- memory from the model
- governance from generation
- provenance from prompt history
- orientation from raw retrieval
- trace from normal user output

## Key Components

- `claire_gui.py`: primary public GUI/runtime surface.
- `ARE_SERVER.py` / `ARE_SERVER_LOCKED.py`: ARE memory service variants.
- `intent_classifier.py`, `lane_router.py`, `relevance_gate.py`, `answer_planner.py`: routing and answer-planning support.
- `archimedes_demo.py`: controlled demo scenario payloads.
- `test_memory_routing.py`: regression tests for memory routing, response shaping, and key demo behaviors.
- `docs/`: architecture, proof, benchmark, partner, enterprise, and developer handoff documentation.

## Safety Rules

Do not casually change:

- GUI layout
- voice visualizer
- live demo structure
- ARE memory behavior
- Sentinel/governance core
- trace/replay behavior
- backend APIs
- secrets, runtime logs, or production memory data

Use documentation and tests before making behavioral changes.

## Validation

Current baseline checks:

```bash
venv/bin/python -m py_compile claire_gui.py test_memory_routing.py
venv/bin/python test_memory_routing.py
```

## Repository Hygiene

This private repository intentionally contains active prototypes and product-development material. Public release should be split into a separate sanitized repository with only reviewed docs, benchmark artifacts, and reproducible proof scripts.

See `docs/CLAIRE_REPO_CLEANUP_AUDIT.md` for cleanup status and next steps.
