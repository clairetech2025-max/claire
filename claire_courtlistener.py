import os
import sys
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

from current_truth_loader import get_subsystem_entry

COURTLISTENER_BASE = "https://www.courtlistener.com/api/rest/v4"
INGEST_URL = "http://127.0.0.1:8081/parser/push"
NOT_REGISTERED = "CourtListener subsystem not registered."


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


def _registry_entry():
    return get_subsystem_entry("CourtListener")


def _registered_root():
    entry = _registry_entry()
    if not entry:
        return None
    root = Path(str(entry.get("absolute_path") or "")).expanduser()
    if root.exists():
        return root
    return None


def _not_configured(extra=None):
    status = {"status": "not_configured", "summary": NOT_REGISTERED}
    if extra:
        status.update(extra)
    return status


def _registry_path(key):
    entry = _registry_entry() or {}
    value = entry.get(key)
    return Path(str(value)).expanduser() if value else None


def _read_jsonl(path, limit=10):
    if not path or not path.exists():
        return []
    items = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                items.append({"raw": line[:500]})
    except Exception as exc:
        return [{"error": str(exc)}]
    return items


def get_courtlistener_status():
    root = _registered_root()
    if root is None:
        return _not_configured()
    return {
        "status": "configured",
        "subsystem": "CourtListener",
        "root_path": str(root),
        "api_key_present": bool(os.getenv("COURTLISTENER_API_KEY") or os.getenv("COURTLISTENER_TOKEN")),
        "memory_authority": False,
        "default_runtime_authority": False,
        "legal_filing_from_chat": "blocked",
    }


def get_tracked_cases():
    root = _registered_root()
    if root is None:
        return _not_configured({"items": []})
    path = _registry_path("cases_path")
    items = _read_jsonl(path, limit=25)
    return {
        "status": "configured" if path and path.exists() else "not_configured",
        "summary": "Tracked legal cases loaded." if items else "No tracked cases file registered or no cases found.",
        "cases_path": str(path) if path else None,
        "items": items,
    }


def get_recent_docket_events():
    root = _registered_root()
    if root is None:
        return _not_configured({"items": []})
    traces = _registry_path("traces_path")
    cache = _registry_path("cache_path")
    items = _read_jsonl(traces, limit=10) or _read_jsonl(cache, limit=10)
    return {
        "status": "configured" if items else "not_configured",
        "summary": "Recent legal monitor events loaded." if items else "No recent docket events found.",
        "traces_path": str(traces) if traces else None,
        "cache_path": str(cache) if cache else None,
        "items": items,
    }


def check_case_updates():
    status = get_courtlistener_status()
    if status.get("status") != "configured":
        return status
    cases = get_tracked_cases()
    events = get_recent_docket_events()
    return {
        "status": "configured",
        "summary": "CourtListener monitor check completed from registered local ledgers.",
        "tracked_case_count": len(cases.get("items") or []),
        "recent_event_count": len(events.get("items") or []),
        "legal_filing_from_chat": "blocked",
    }


def get_legal_monitor_summary():
    status = get_courtlistener_status()
    if status.get("status") != "configured":
        return status
    return {
        "status": "configured",
        "summary": "CourtListener is registered as a legal docket monitor, not CLAIRE memory.",
        "tracked_cases": get_tracked_cases(),
        "recent_docket_events": get_recent_docket_events(),
        "legal_filing_from_chat": "blocked",
    }


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
