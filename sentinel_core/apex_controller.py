import requests
import json

# --- CONFIG ---
ARE_URL = "http://0.0.0.0:8000/recall"


def ask_claire(query_text):
    print(f"[*] APEX: Querying the Memory Spine for '{query_text}'...")

    # 1. Reach out to the ARE Muscle
    response = requests.post(ARE_URL, json={"text": query_text})

    if response.status_code == 200:
        data = response.json()
        count = data.get("count", 0)
        print(f"[+] APEX: Found {count} relevant memory fragments.")

        # 2. Display the 'Beef'
        for hit in data.get("hits", []):
            print(f"--- Memory Fragment ({hit['hg_id']}) ---")
            print(f"Source: {hit['source']}")
            print(f"Data: {hit['payload']}")
            print("-" * 30)
    else:
        print(f"[!] APEX Error: Could not reach ARE_SERVER.")


if __name__ == "__main__":
    import sys

    user_input = sys.argv[1] if len(sys.argv) > 1 else "Genesis"
    ask_claire(user_input)
