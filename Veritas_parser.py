#!/usr/bin/env python3
import os, sys, json, time, hashlib, zipfile, traceback
from pathlib import Path

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def ingest_directory(target_path):
    mem_file = os.path.expanduser("~/claire/data/palantir_mem.jsonl")
    os.makedirs(os.path.dirname(mem_file), exist_ok=True)
    count = 0
    for root, _, files in os.walk(target_path):
        for file in files:
            full_path = os.path.join(root, file)
            try:
                with open(full_path, 'r', errors='ignore') as f:
                    content = f.read()
                    if content.strip():
                        entry = {
                            "hg_id": get_hash(content[:1000]),
                            "source_path": full_path,
                            "text": content,
                            "timestamp": time.time()
                        }
                        with open(mem_file, 'a') as m:
                            m.write(json.dumps(entry) + "\n")
                        count += 1
            except Exception:
                continue
    print(f"Ingested {count} files into ARE memory.")

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "ingest":
        ingest_directory(sys.argv[2])
