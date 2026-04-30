import time
import threading
import math
from typing import List, Dict, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np

# ===============================
# CONFIG
# ===============================
_EMB_DIM = 384
TIME_DECAY_LAMBDA = 0.015
REGIME_BOOST = 1.15

# ===============================
# EMBEDDING LAYER (With Fallback)
# ===============================
try:
    from sentence_transformers import SentenceTransformer

    _emb_model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed_text(texts: List[str]) -> np.ndarray:
        return np.asarray(
            _emb_model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        )

except Exception:
    import hashlib

    def embed_text(texts: List[str]) -> np.ndarray:
        # Deterministic fallback if model isn't loaded yet
        out = []
        for t in texts:
            h = hashlib.md5(t.encode()).digest()
            vec = np.frombuffer(h, dtype=np.int8).astype(np.float32)
            padded = np.pad(vec, (0, _EMB_DIM - len(vec)), "constant")
            out.append(padded / (np.linalg.norm(padded) + 1e-9))
        return np.array(out)


class VectorIndex:
    def __init__(self):
        self.records = []
        self.embeddings = None

    def add(self, new_records: List[Dict]):
        texts = [r["text"] for r in new_records]
        new_embs = embed_text(texts)
        for i, r in enumerate(new_records):
            r["timestamp"] = r.get("timestamp") or time.time()
            self.records.append(r)
        if self.embeddings is None:
            self.embeddings = new_embs
        else:
            self.embeddings = np.vstack([self.embeddings, new_embs])


# ===============================
# FASTAPI ENGINE
# ===============================
app = FastAPI(title="Analog Recall Engine (ARE)", version="2.0")
INDEX = VectorIndex()


class AddRecordReq(BaseModel):
    id: str

    regime: Optional[str] = None
    timestamp: Optional[float] = None


@app.get("/health")
def health():
    return {"status": "ok", "records": len(INDEX.records)}


@app.post("/add_record")
def add_record(req: AddRecordReq):
    # your index expects separate lists
    INDEX.add([req.id], [req.text])
    return {"status": "ok"}


@app.post("/chat")
def chat(req: dict):
    user_input = req.get("query", "")

    # your VectorIndex uses search()
    results = INDEX.search(user_input, top_k=5)

    # results = [(id, text, score), ...]
    memory = "\n".join([t[1] for t in results])

    prompt = f"Relevant memory:\n{memory}\n\nUser:\n{user_input}"

    r = requests.post(
        "http://127.0.0.1:8081/v1/chat/completions",
        json={"messages": [{"role": "user", "content": prompt}]},
        timeout=15,
    )

    return r.json()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
