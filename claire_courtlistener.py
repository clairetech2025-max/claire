import os
import sys
import json
import requests
from datetime import datetime, timezone

COURTLISTENER_BASE = "https://www.courtlistener.com/api/rest/v4"
INGEST_URL = "http://127.0.0.1:8081/parser/push"


def load_env(path="claire_keys.env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def courtlistener_headers():
    token = os.getenv("COURTLISTENER_API_KEY", "").strip()
    if not token:
        raise SystemExit("COURTLISTENER_API_KEY is missing from claire_keys.env")
    return {"Authorization": f"Token {token}"}


def courtlistener_get(endpoint, params):
    url = f"{COURTLISTENER_BASE}/{endpoint.strip('/')}/"
    r = requests.get(url, headers=courtlistener_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def search_opinions(query, limit=5):
    data = courtlistener_get("search", {"q": query, "type": "o"})
    return (data.get("results") or [])[:limit]


def citation_lookup(citation):
    return courtlistener_get("citation-lookup", {"citation": citation})


def make_legal_payload(kind, query, result):
    title = (
        result.get("caseName")
        or result.get("caseNameFull")
        or result.get("absolute_url")
        or kind
    )

    citations = ", ".join(result.get("citation") or [])
    opinion_snippets = []
    for opinion in result.get("opinions") or []:
        snippet = (opinion.get("snippet") or "").strip()
        if snippet:
            opinion_snippets.append(snippet)
    snippet_text = "\n".join(opinion_snippets[:3])
    absolute_url = result.get("absolute_url") or ""
    courtlistener_url = (
        "https://www.courtlistener.com" + absolute_url
        if absolute_url.startswith("/")
        else absolute_url
    )

    summary = "\n".join(
        [
            f"CourtListener legal record for query: {query}",
            f"Record kind: {kind}",
            f"Case name: {title}",
            f"Full case name: {result.get('caseNameFull') or ''}",
            f"Court: {result.get('court') or ''}",
            f"Date filed: {result.get('dateFiled') or ''}",
            f"Docket number: {result.get('docketNumber') or ''}",
            f"Citations: {citations}",
            f"CourtListener URL: {courtlistener_url}",
            "Opinion snippets:",
            snippet_text,
            "Raw CourtListener JSON:",
            json.dumps(result, ensure_ascii=False, indent=2),
        ]
    )

    text = summary.strip()

    return {
        "source": "courtlistener",
        "pipeline": "courtlistener_to_parser_to_sentinel",
        "kind": kind,
        "query": query,
        "title": title,
        "text": text,
        "metadata": {
            "source_system": "CourtListener",
            "source_url": "https://www.courtlistener.com",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "legal_advisor_boundary": "research_only_not_legal_advice",
            "provenance": "CourtListener API v4",
        },
    }


def push_to_claire(payload):
    r = requests.post(INGEST_URL, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def cmd_search(args):
    query = " ".join(args).strip()
    if not query:
        raise SystemExit("Usage: python3 claire_courtlistener.py search <query>")

    results = search_opinions(query)
    print(f"found: {len(results)}")

    for result in results:
        payload = make_legal_payload("opinion_search", query, result)
        ingest = push_to_claire(payload)
        print("ingested:", payload["title"], ingest)


def cmd_cite(args):
    citation = " ".join(args).strip()
    if not citation:
        raise SystemExit("Usage: python3 claire_courtlistener.py cite <citation>")

    data = citation_lookup(citation)
    payload = make_legal_payload("citation_lookup", citation, data)
    ingest = push_to_claire(payload)
    print("ingested citation:", citation, ingest)


def main():
    load_env()

    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage:\n"
            "  python3 claire_courtlistener.py search <query>\n"
            "  python3 claire_courtlistener.py cite <citation>"
        )

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    if cmd == "search":
        cmd_search(args)
    elif cmd in ("cite", "citation"):
        cmd_cite(args)
    else:
        raise SystemExit(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
