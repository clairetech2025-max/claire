# Install

## Requirements

- Python 3.11 or newer
- Git
- Optional: local llama.cpp-compatible model server for live model responses
- Optional: Hugging Face CLI for Space deployment

## Setup

```bash
python -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -e .
```

When test tools are needed:

```bash
venv/bin/python -m pip install pytest
```

## Configuration

```bash
cp .env.example .env
cp config.example.yaml config.yaml
```

Edit local values only in `.env` or `config.yaml`. Do not commit live secrets,
databases, indexes, uploads, evidence, or model files.

## Verify

```bash
venv/bin/python -m py_compile claire_gui.py claire_runtime.py claire_core/*.py claire_core/adapters/*.py claire_core/runtime/*.py
venv/bin/python -m pytest tests/test_claire_core_governance.py tests/test_runtime_truth_spine.py tests/test_temporal_engine.py tests/test_three_crp_turn_commit.py -q
```
