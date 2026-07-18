#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-7860}"
export CLAIRE_PROVIDER="${CLAIRE_PROVIDER:-llama}"
export CLAIRE_LLAMA_URL="${CLAIRE_LLAMA_URL:-http://127.0.0.1:8081/v1/chat/completions}"
export CLAIRE_LOCAL_MODEL_ID="${CLAIRE_LOCAL_MODEL_ID:-microsoft/Phi-3-mini-4k-instruct-gguf}"
export CLAIRE_LOCAL_MODEL_FILE="${CLAIRE_LOCAL_MODEL_FILE:-Phi-3-mini-4k-instruct-q4.gguf}"
export CLAIRE_MODEL_DIR="${CLAIRE_MODEL_DIR:-/app/models}"
export CLAIRE_ORIGINAL_ARE_MEM_PATH="${CLAIRE_ORIGINAL_ARE_MEM_PATH:-/app/demo_data/are_mem.jsonl}"
export CLAIRE_PROVIDER_TIMEOUT_SECONDS="${CLAIRE_PROVIDER_TIMEOUT_SECONDS:-120}"

echo "== CLAIRE HF startup =="
df -h /app || true
free -h || true

MODEL_PATH="$CLAIRE_MODEL_DIR/$CLAIRE_LOCAL_MODEL_FILE"
LLAMA_STATUS="not_started"

if [[ "$CLAIRE_PROVIDER" == "llama" ]]; then
  /app/venv/bin/python /app/hf_space/scripts/download_model.py || LLAMA_STATUS="model_download_failed"
  if [[ -f "$MODEL_PATH" ]]; then
    /app/llama.cpp/build/bin/llama-server \
      -m "$MODEL_PATH" \
      --host 127.0.0.1 \
      --port 8081 \
      -c "${CLAIRE_LLAMA_CONTEXT:-4096}" \
      -ngl "${CLAIRE_LLAMA_N_GPU_LAYERS:-0}" \
      > /tmp/llama-server.log 2>&1 &
    LLAMA_PID=$!
    echo "llama_pid=$LLAMA_PID"
    for i in $(seq 1 90); do
      if /app/venv/bin/python /app/hf_space/scripts/healthcheck_llama.py >/tmp/llama-health.log 2>&1; then
        LLAMA_STATUS="ready"
        break
      fi
      sleep 2
    done
    if [[ "$LLAMA_STATUS" != "ready" ]]; then
      echo "llama_status=$LLAMA_STATUS"
      tail -80 /tmp/llama-server.log || true
    fi
  fi
fi

/app/bin/claire-go-provider > /tmp/claire-go.log 2>&1 &
echo "go_provider_pid=$!"

exec /app/venv/bin/python -m uvicorn claire_gui:app --host 0.0.0.0 --port "$PORT"
