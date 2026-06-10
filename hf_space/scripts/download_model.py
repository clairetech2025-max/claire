from __future__ import annotations

import os
from pathlib import Path
from huggingface_hub import hf_hub_download, list_repo_files

repo_id = os.environ.get("CLAIRE_LOCAL_MODEL_ID", "microsoft/Phi-3-mini-4k-instruct-gguf").strip()
filename = os.environ.get("CLAIRE_LOCAL_MODEL_FILE", "Phi-3-mini-4k-instruct-q4.gguf").strip()
model_dir = Path(os.environ.get("CLAIRE_MODEL_DIR", "/app/models"))
model_dir.mkdir(parents=True, exist_ok=True)
target = model_dir / filename

if target.exists() and target.stat().st_size > 0:
    print(f"model_present={target}")
    raise SystemExit(0)

files = list_repo_files(repo_id)
if filename not in files:
    ggufs = [f for f in files if f.lower().endswith(".gguf")]
    raise SystemExit(f"Selected GGUF {filename!r} not found in {repo_id}. Available GGUF files: {ggufs}")

path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(model_dir), local_dir_use_symlinks=False)
print(f"model_downloaded={path}")
