import json
import requests
import os

# CONFIG
JSONL_INPUT = "/home/LuciusPrime/claire/data/parser_output.jsonl"
ARE_ADD_URL = "http://127.0.0.1:8081/ingest"


def load_to_memory():
    if not os.path.exists(JSONL_INPUT):
        print(f"Error: {JSONL_INPUT} not found. Check ~/claire/data/")
        return

    count = 0
    with open(JSONL_INPUT, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)

                # Mapping the JSONL fields to the Go Brain's expectations
                payload = {
                    "id": chunk.get("chunk_id", f"auto_{count}"),
                    "text": chunk.get("text", ""),
                    "regime": chunk.get("doc_type", "general"),
                    "timestamp": chunk.get("created_at_unix", 0),
                }

                # Sending the pulse through the Parser/Sentinel ingest bridge on 8081
                r = requests.post(ARE_ADD_URL, json=payload, timeout=5)

                if r.status_code == 200:
                    count += 1
                else:
                    print(f"Failed to load chunk {payload['id']}: {r.text}")

            except Exception as e:
                print(f"Error at line {count}: {e}")
                continue

    print(f"\nSUCCESS: Fed {count} memory chunks into Claire's ARE.")


if __name__ == "__main__":
    load_to_memory()
