#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-7860}"
export CLAIRE_RUNTIME_DATA_DIR="${CLAIRE_RUNTIME_DATA_DIR:-/data/claire_runtime}"
export CLAIRE_BASE_DIR="${CLAIRE_BASE_DIR:-/app}"
export CLAIRE_ORIGINAL_ARE_MEM_PATH="${CLAIRE_ORIGINAL_ARE_MEM_PATH:-$CLAIRE_RUNTIME_DATA_DIR/are/are_mem.jsonl}"
export CLAIRE_STATE_DIR="${CLAIRE_STATE_DIR:-$CLAIRE_RUNTIME_DATA_DIR/claire_state}"
export CLAIRE_MEMORY_VAULT_PATH="${CLAIRE_MEMORY_VAULT_PATH:-$CLAIRE_RUNTIME_DATA_DIR/memory_vault.jsonl}"
export CLAIRE_INGEST_SENTINEL_SPINE="${CLAIRE_INGEST_SENTINEL_SPINE:-$CLAIRE_RUNTIME_DATA_DIR/silo_data/sentinel_spine.jsonl}"
export CLAIRE_TRACE_PATH="${CLAIRE_TRACE_PATH:-$CLAIRE_RUNTIME_DATA_DIR/traces/claire_runtime_traces.jsonl}"
export CLAIRE_TRACE_DB_PATH="${CLAIRE_TRACE_DB_PATH:-$CLAIRE_RUNTIME_DATA_DIR/traces/claire_runtime_traces.db}"
export ARE_URL="${ARE_URL:-http://127.0.0.1:8002}"
export LLM_URL="${LLM_URL:-http://127.0.0.1:8080}"
export INGEST_BASE_URL="${INGEST_BASE_URL:-http://127.0.0.1:8081}"
export CLAIRE_ARE_INGEST_URL="${CLAIRE_ARE_INGEST_URL:-$ARE_URL/ingest}"
export CLAIRE_GO_ADDR="${CLAIRE_GO_ADDR:-127.0.0.1:8080}"
export CLAIRE_PUBLIC_DEMO_BUILD="${CLAIRE_PUBLIC_DEMO_BUILD:-0}"
export CLAIRE_CREATOR_MODE_ENABLED="${CLAIRE_CREATOR_MODE_ENABLED:-0}"
export VERITAS_TRADING_MODE="${VERITAS_TRADING_MODE:-paper}"
export VERITAS_ENABLE_LIVE_TRADING="${VERITAS_ENABLE_LIVE_TRADING:-false}"
export CLAIRE_CORE_SHADOW_MODE="${CLAIRE_CORE_SHADOW_MODE:-true}"
export CLAIRE_CORE_ENABLED="${CLAIRE_CORE_ENABLED:-false}"

mkdir -p \
  "$CLAIRE_RUNTIME_DATA_DIR/are" \
  "$CLAIRE_RUNTIME_DATA_DIR/traces" \
  "$CLAIRE_RUNTIME_DATA_DIR/uploads" \
  "$CLAIRE_RUNTIME_DATA_DIR/veritas_legal_gui" \
  "$CLAIRE_RUNTIME_DATA_DIR/silo_data"

# Do not copy Azure .env, private ARE memory, DBs, logs, generated indexes, or legal files into this container.
# Secrets must be supplied through Hugging Face Space secrets by name only.

exec /app/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
