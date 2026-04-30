import os
import re
from typing import Any, Dict, List

import requests


OPENALEX_URL = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _abstract_from_inverted_index(index: Dict[str, List[int]]) -> str:
    if not isinstance(index, dict) or not index:
        return ""
    positions = []
    for word, offsets in index.items():
        for offset in offsets or []:
            if isinstance(offset, int):
                positions.append((offset, word))
    if not positions:
        return ""
    positions.sort()
    return " ".join(word for _, word in positions)


def is_scholar_query(prompt: str) -> bool:
    cleaned = " ".join(prompt.lower().split())
    markers = [
        "google scholar",
        "scholar",
        "scholarly",
        "academic",
        "peer reviewed",
        "peer-reviewed",
        "journal article",
        "research paper",
        "papers on",
        "studies on",
        "study on",
        "literature review",
        "openalex",
        "semantic scholar",
    ]
    return any(marker in cleaned for marker in markers)


def normalize_scholar_query(prompt: str) -> str:
    cleaned = " ".join(prompt.split()).strip()
    cleaned = re.sub(r"^(please\s+)?(search|find|look up|lookup)\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"^(google scholar|scholar|scholarly|academic|peer[-\s]?reviewed)\s+",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"^(papers|research papers|studies|study|articles|journal articles|literature)\s+(on|about|for)\s+",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"^(on|about|for)\s+", "", cleaned, flags=re.I)
    return cleaned.strip() or prompt.strip()


def _openalex_work_to_result(work: Dict[str, Any]) -> Dict[str, Any]:
    authorships = work.get("authorships") or []
    authors = []
    for authorship in authorships[:5]:
        author = authorship.get("author") or {}
        name = _clean(author.get("display_name"))
        if name:
            authors.append(name)

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    open_access = work.get("open_access") or {}

    return {
        "provider": "OpenAlex",
        "title": _clean(work.get("title") or work.get("display_name")),
        "year": work.get("publication_year"),
        "authors": authors,
        "venue": _clean(source.get("display_name")),
        "doi": _clean(work.get("doi")),
        "url": _clean(primary_location.get("landing_page_url") or work.get("doi") or work.get("id")),
        "cited_by_count": work.get("cited_by_count") or 0,
        "is_open_access": bool(open_access.get("is_oa")),
        "abstract": _clean(_abstract_from_inverted_index(work.get("abstract_inverted_index") or "")),
    }


def search_openalex(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    params = {
        "search": query,
        "per-page": max(1, min(limit, 10)),
        "sort": "relevance_score:desc",
    }
    mailto = os.environ.get("OPENALEX_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto

    response = requests.get(OPENALEX_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    return [_openalex_work_to_result(work) for work in data.get("results", [])]


def _semantic_paper_to_result(paper: Dict[str, Any]) -> Dict[str, Any]:
    authors = [
        _clean(author.get("name"))
        for author in paper.get("authors", [])[:5]
        if _clean(author.get("name"))
    ]
    external = paper.get("externalIds") or {}
    doi = external.get("DOI") or ""
    return {
        "provider": "Semantic Scholar",
        "title": _clean(paper.get("title")),
        "year": paper.get("year"),
        "authors": authors,
        "venue": _clean(paper.get("venue")),
        "doi": _clean(doi),
        "url": _clean(paper.get("url")),
        "cited_by_count": paper.get("citationCount") or 0,
        "is_open_access": False,
        "abstract": _clean(paper.get("abstract")),
    }


def search_semantic_scholar(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    headers = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": query,
        "limit": max(1, min(limit, 10)),
        "fields": "title,authors,year,abstract,citationCount,url,venue,externalIds",
    }
    response = requests.get(SEMANTIC_SCHOLAR_URL, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    return [_semantic_paper_to_result(paper) for paper in data.get("data", [])]


def search_scholar(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    results = []
    try:
        results.extend(search_openalex(query, limit=limit))
    except Exception as e:
        print("OpenAlex scholar error:", e)

    if len(results) < min(3, limit):
        try:
            results.extend(search_semantic_scholar(query, limit=limit))
        except Exception as e:
            print("Semantic Scholar error:", e)

    seen = set()
    unique = []
    for result in results:
        key = (result.get("doi") or result.get("title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique[:limit]


def format_scholar_reply(query: str, results: List[Dict[str, Any]]) -> str:
    if not results:
        return (
            "I searched the Scholar lane, but I did not find a clean result yet.\n\n"
            "Try giving me a tighter topic, author name, DOI, phrase from the title, or the field you care about."
        )

    lines = [
        "Scholar lane read:",
        "I treated this as academic research support, not legal authority or final proof.",
        "",
        f"Query: {query}",
        "",
        "Top scholarly leads:",
    ]

    for index, result in enumerate(results, start=1):
        authors = ", ".join(result.get("authors") or []) or "Unknown authors"
        year = result.get("year") or "Unknown year"
        venue = result.get("venue") or "Unknown venue"
        citations = result.get("cited_by_count") or 0
        url = result.get("url") or result.get("doi") or "No URL listed"
        abstract = result.get("abstract") or ""
        if len(abstract) > 420:
            abstract = abstract[:420].rsplit(" ", 1)[0] + "..."

        lines.extend(
            [
                "",
                f"{index}. {result.get('title') or 'Untitled'}",
                f"   Authors: {authors}",
                f"   Year / venue: {year} / {venue}",
                f"   Source: {result.get('provider')} | Citations: {citations}",
                f"   URL: {url}",
            ]
        )
        if abstract:
            lines.append(f"   Abstract signal: {abstract}")

    lines.extend(
        [
            "",
            "Claire's next move:",
            "Use these papers as leads. I should compare methods, publication date, citation context, and whether the source actually answers your question before treating it as guidance.",
        ]
    )
    return "\n".join(lines)


def scholar_reply(query: str, limit: int = 5) -> str:
    normalized = normalize_scholar_query(query)
    return format_scholar_reply(normalized, search_scholar(normalized, limit=limit))


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]).strip()
    if not q:
        raise SystemExit("Usage: python3 claire_scholar.py <query>")
    print(scholar_reply(q))
