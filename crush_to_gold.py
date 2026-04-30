import os
from pypdf import PdfReader
import requests

# The Gate to the ARE
ARE_URL = "http://127.0.0.1:8000/add_record"

# List of the "Gravel" to turn into "Gold"
FILES_TO_CRUSH = [
    {"path": "Complaint For The Horse.pdf", "regime": "litigation"},
    {"path": "OAL response.docx - Copy - Copy.pdf", "regime": "regulatory_failure"},
    {"path": "The Bureaucratic Garden of Eden.pdf", "regime": "forensic_history"},
    {"path": "THRIVING BUSINESS.pdf", "regime": "economic_damages"},
]


def crush():
    for item in FILES_TO_CRUSH:
        if not os.path.exists(item["path"]):
            print(f"Skipping {item['path']} - Not found.")
            continue

        print(f"Crushing {item['path']}...")
        reader = PdfReader(item["path"])
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"

        # Send to the ARE
        payload = {"id": item["path"], "text": full_text, "regime": item["regime"]}
        response = requests.post(ARE_URL, json=payload)
        print(f"Result: {response.json().get('status')}")


if __name__ == "__main__":
    crush()
