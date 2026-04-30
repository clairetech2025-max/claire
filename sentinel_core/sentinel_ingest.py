import os
import json
import hashlib
import time
import zipfile
import io
from pathlib import Path

# --- SYSTEM ANCHORS ---
BASE_DIR = Path("/home/LuciusPrime/claire")
SPINE_PATH = BASE_DIR / "silo_data/sentinel_spine.jsonl"
INBOX = BASE_DIR / "exports"


def get_hg_id(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def seal_record(text: str, source: str):
    if not text.strip():
        return
    chunks = [text[i : i + 2000] for i in range(0, len(text), 2000)]
    with open(SPINE_PATH, "a", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            entry = {
                "hg_id": get_hg_id(chunk),
                "source": source,
                "ts": time.time(),
                "payload": chunk.strip(),
                "v_sig": "SENTINEL_ZIP_INGEST_V1",
            }
            f.write(json.dumps(entry) + "\n")


def process_zip(zip_path):
    print(f"[*] Extracting and Crushing: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "r") as z:
        for file_info in z.infolist():
            if file_info.is_dir():
                continue
            # Only crush text-based files (JSON, TXT, HTML)
            if file_info.filename.endswith((".json", ".txt", ".html", ".csv")):
                with z.open(file_info) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    seal_record(content, f"{zip_path.name}/{file_info.filename}")


if __name__ == "__main__":
    SPINE_PATH.touch(exist_ok=True)
    print(f"[*] Sentinel Online. Monitoring: {INBOX}")
    for p in INBOX.glob("*"):
        if p.suffix.lower() == ".zip":
            process_zip(p)
        elif p.is_file():
            seal_record(p.read_text(errors="ignore"), p.name)
    print("[+] Ingest Complete.")
