#!/usr/bin/env bash
# Stage the Hugging Face Space tree and the Cloudflare Worker into one deploy
# directory, so the edge container is built from the exact commit the primary
# (HF) twin runs. Uses `git archive HEAD`: uncommitted edits never reach the edge.
set -euo pipefail

SPACE_DIR="${1:?usage: build_cloudflare_tree.sh <hf-space-checkout> <output-dir>}"
OUT="${2:?usage: build_cloudflare_tree.sh <hf-space-checkout> <output-dir>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

rm -rf "$OUT"
mkdir -p "$OUT"
git -C "$SPACE_DIR" lfs pull >/dev/null 2>&1 || true
# Repository bytes only: a Windows autocrlf checkout would otherwise emit CRLF
# and break start.sh inside the Linux container.
git -C "$SPACE_DIR" -c core.autocrlf=false -c core.eol=lf archive --format=tar HEAD | tar -x -C "$OUT"
if grep -q $'\r' "$OUT/start.sh"; then
  echo "start.sh has CRLF line endings in the Space commit; fix before deploying." >&2
  exit 1
fi

for required in Dockerfile start.sh app.py state_sync.py; do
  [[ -f "$OUT/$required" ]] || { echo "Space tree is missing $required" >&2; exit 1; }
done
if grep -q "claire_are.api:app" "$OUT/Dockerfile"; then
  echo "Space Dockerfile runs the ARE-only API, not the full CLAIRE runtime; refusing to build the edge twin from it." >&2
  exit 1
fi

cp "$REPO_ROOT"/deploy/cloudflare/{worker.ts,runtime_prefix.ts,wrangler.jsonc,package.json,tsconfig.json} "$OUT/"
git -C "$SPACE_DIR" rev-parse HEAD > "$OUT/.space-sha"
echo "Staged Space $(cat "$OUT/.space-sha") + Cloudflare worker into $OUT"
