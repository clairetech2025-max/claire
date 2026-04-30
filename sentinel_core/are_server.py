from fastapi import FastAPI
import json
from pathlib import Path

app = FastAPI(title="ARE_SERVER_TURBO_V1")
SPINE_PATH = Path("/home/LuciusPrime/claire/silo_data/sentinel_spine.jsonl")

# GLOBAL CACHE: We load the whole spine into your 32GB of RAM
MEMORY_CACHE = []


@app.on_event("startup")
def load_spine():
    print("[*] Turbo Mode: Loading Spine into RAM...")
    if SPINE_PATH.exists():
        with open(SPINE_PATH, "r") as f:
            for line in f:
                try:
                    MEMORY_CACHE.append(json.loads(line))
                except:
                    continue
    print(f"[+] Loaded {len(MEMORY_CACHE)} records into RAM.")


@app.post("/recall")
async def recall(query: dict):
    search_term = query.get("text", "").lower()
    # Instant in-memory filtering using your 32GB RAM
    hits = [r for r in MEMORY_CACHE if search_term in r["payload"].lower()]
    return {"hits": hits[:50]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
