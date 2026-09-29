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
export CLAIRE_RUNTIME_TRUTH_SPINE="${CLAIRE_RUNTIME_TRUTH_SPINE:-$CLAIRE_RUNTIME_DATA_DIR/traces/runtime_truth_spine.jsonl}"
export CLAIRE_RUNTIME_TRUTH_SPINE_DEGRADED="${CLAIRE_RUNTIME_TRUTH_SPINE_DEGRADED:-$CLAIRE_RUNTIME_DATA_DIR/traces/runtime_truth_spine_degraded.jsonl}"
export CLAIRE_TEMPORAL_STATE_PATH="${CLAIRE_TEMPORAL_STATE_PATH:-$CLAIRE_RUNTIME_DATA_DIR/temporal/temporal_events.jsonl}"
export ARE_URL="${ARE_URL:-http://127.0.0.1:8002}"
export LLM_URL="${LLM_URL:-http://127.0.0.1:8080}"
export INGEST_BASE_URL="${INGEST_BASE_URL:-http://127.0.0.1:8081}"
export CLAIRE_ARE_INGEST_URL="${CLAIRE_ARE_INGEST_URL:-$ARE_URL/ingest}"
export CLAIRE_GO_ADDR="${CLAIRE_GO_ADDR:-127.0.0.1:8080}"
export CLAIRE_PROVIDER="${CLAIRE_PROVIDER:-nim}"
export NVIDIA_NIM_BASE_URL="${NVIDIA_NIM_BASE_URL:-https://integrate.api.nvidia.com/v1}"
export NVIDIA_NIM_MODEL="${NVIDIA_NIM_MODEL:-nvidia/nemotron-3-ultra-550b-a55b}"
export CLAIRE_PUBLIC_DEMO_BUILD="${CLAIRE_PUBLIC_DEMO_BUILD:-0}"
export CLAIRE_CREATOR_MODE_ENABLED="${CLAIRE_CREATOR_MODE_ENABLED:-0}"
export VERITAS_TRADING_MODE="${VERITAS_TRADING_MODE:-paper}"
export VERITAS_ENABLE_LIVE_TRADING="${VERITAS_ENABLE_LIVE_TRADING:-false}"
export CLAIRE_CORE_SHADOW_MODE="${CLAIRE_CORE_SHADOW_MODE:-true}"
export CLAIRE_CORE_ENABLED="${CLAIRE_CORE_ENABLED:-false}"

mkdir -p \
  "$CLAIRE_RUNTIME_DATA_DIR/are" \
  "$CLAIRE_RUNTIME_DATA_DIR/traces" \
  "$CLAIRE_RUNTIME_DATA_DIR/temporal" \
  "$CLAIRE_RUNTIME_DATA_DIR/uploads" \
  "$CLAIRE_RUNTIME_DATA_DIR/veritas_legal_gui" \
  "$CLAIRE_RUNTIME_DATA_DIR/silo_data"

# Do not copy Azure .env, private ARE memory, DBs, logs, generated indexes, or legal files into this container.
# Secrets must be supplied through deployment secrets by name only.

if [[ "$CLAIRE_PROVIDER" == "nim" && -z "${NVIDIA_API_KEY:-}" && -z "${CLAIRE_GO_UPSTREAM_URL:-}" ]]; then
  echo "CLAIRE provider credentials are not configured; starting in degraded public-demo mode." >&2
fi

/app/bin/claire-go-provider &
go_pid=$!

go_ready=0
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null; then
    go_ready=1
    break
  fi
  if ! kill -0 "$go_pid" 2>/dev/null; then
    wait "$go_pid"
  fi
  sleep 1
done

if [[ "$go_ready" != "1" ]]; then
  echo "CLAIRE Go provider failed health check at http://127.0.0.1:8080/health" >&2
  exit 1
fi

exec /app/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
