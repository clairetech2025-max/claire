#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <manifest.json> <build-dir> <commit-message>" >&2
  exit 2
fi

manifest="$1"
build_dir="$2"
commit_message="$3"

space_id="$(
  python - "$manifest" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data.get("space_id", ""))
PY
)"
space_id="${HF_SPACE_ID:-$space_id}"

if [ -z "$space_id" ]; then
  echo "manifest has no space_id and HF_SPACE_ID is unset; refusing upload" >&2
  exit 2
fi

if ! command -v hf >/dev/null 2>&1; then
  echo "hf CLI not found; install huggingface_hub[cli] or run venv/bin/hf directly" >&2
  exit 2
fi

python scripts/deploy/build_hf_tree.py "$manifest" "$build_dir"
python scripts/deploy/validate_hf_tree.py "$build_dir"
python scripts/deploy/preflight_hf_space.py "$manifest" "$build_dir"
if [ -n "${HF_TOKEN:-}" ]; then
  hf upload "$space_id" "$build_dir" . --type space --token "$HF_TOKEN" --commit-message "$commit_message"
else
  hf upload "$space_id" "$build_dir" . --type space --commit-message "$commit_message"
fi
