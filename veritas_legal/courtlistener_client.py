from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .engine import EvidenceRecord, safe_id, source_doc_id_for

COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
COURTLISTENER_WEB_BASE = "https://www.courtlistener.com"


@dataclass
class CaseLawCase:
    case_name: str
    citation: str
    court: str
    date_filed: str
    url: str
    source_doc_id: str = ""
    source_hash: str = ""


@dataclass
class CaseLawResult:
    status: str
    query: str
    matter_id: str
    cases: list[CaseLawCase]
    reason: str = ""
    retrieved_at: str = ""


def _headers() -> dict[str, str]:
    token = os.getenv("COURTLISTENER_API_KEY", "").strip() or os.getenv("COURTLISTENER_TOKEN", "").strip()
    return {"Authorization": f"Token {token}"} if token else {}


def _case_name(row: dict[str, Any]) -> str:
    return str(row.get("caseName") or row.get("caseNameFull") or row.get("case_name") or row.get("absolute_url") or "").strip()


def _citation(row: dict[str, Any]) -> str:
    value = row.get("citation") or row.get("citations") or ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item)
    return str(value or "").strip()


def _url(row: dict[str, Any]) -> str:
    absolute = str(row.get("absolute_url") or row.get("cluster_absolute_url") or row.get("url") or "").strip()
    if absolute.startswith("/"):
        return COURTLISTENER_WEB_BASE + absolute
    return absolute


def _result_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return [item for item in payload["results"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _write_external_case_record(state_dir: Path, matter_id: str, query: str, case: CaseLawCase, raw_row: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "CourtListener (external)",
        "query": query,
        "case": asdict(case),
        "raw_keys": sorted(raw_row.keys()),
    }
    source_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8", errors="ignore")).hexdigest()
    source_doc_id = source_doc_id_for(matter_id, source_hash)
    case.source_hash = source_hash
    case.source_doc_id = source_doc_id
    text = " | ".join(part for part in [case.case_name, case.citation, case.court, case.date_filed, case.url] if part)
    record = EvidenceRecord(
        ts=int(time.time()),
        matter_id=matter_id,
        source_doc_id=source_doc_id,
        source_path=case.url or "CourtListener external search result",
        source_hash=source_hash,
        source_sha256=source_hash,
        text_sha256=hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest(),
        are_event_sha="",
        dates=[case.date_filed] if case.date_filed else [],
        entities=[case.case_name] if case.case_name else [],
        excerpt=text[:500],
        redactions=0,
        parser="courtlistener_external",
    )
    with (state_dir / "evidence_records.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    with (state_dir / "source_manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "source": "CourtListener (external)",
            "matter_id": matter_id,
            "source_doc_id": source_doc_id,
            "source_hash": source_hash,
            "source_url": case.url,
            "query": query,
            "ingested_ts": record.ts,
        }, ensure_ascii=False) + "\n")
    with (state_dir / "legal_metadata.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "matter_id": matter_id,
            "source_doc_id": source_doc_id,
            "source_hash": source_hash,
            "source": "CourtListener (external)",
            "source_url": case.url,
            "case_name": case.case_name,
            "citation": case.citation,
            "court": case.court,
            "date_filed": case.date_filed,
            "review_status": "unreviewed",
            "authority_level": "attorney_review_required",
            "provenance_status": "external_source_linked" if case.url else "external_source_partial",
            "are_event_sha": "",
            "search_authority": False,
            "faiss_authority": False,
            "external_authority": "CourtListener API result for attorney review",
        }, ensure_ascii=False) + "\n")
    with (state_dir / "trace.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "event": "courtlistener_lookup_recorded",
            "matter_id": matter_id,
            "query": query,
            "source_doc_id": source_doc_id,
            "source_hash": source_hash,
            "status": "OK",
        }, ensure_ascii=False) + "\n")


def lookup_case_law(
    query: str,
    matter_id: str,
    *,
    state_dir: str | Path | None = None,
    timeout: int = 20,
    session: Any = requests,
) -> CaseLawResult:
    matter = safe_id(matter_id)
    clean_query = str(query or "").strip()
    if not clean_query:
        return CaseLawResult(status="UNAVAILABLE", query=clean_query, matter_id=matter, cases=[], reason="query is required")
    try:
        response = session.get(
            f"{COURTLISTENER_BASE_URL}/search/",
            headers=_headers(),
            params={"q": clean_query, "type": "o", "format": "json"},
            timeout=timeout,
        )
    except Exception as exc:
        return CaseLawResult(status="UNAVAILABLE", query=clean_query, matter_id=matter, cases=[], reason=str(exc))

    if getattr(response, "status_code", 0) != 200:
        body = str(getattr(response, "text", ""))[:300]
        return CaseLawResult(
            status="UNAVAILABLE",
            query=clean_query,
            matter_id=matter,
            cases=[],
            reason=f"CourtListener HTTP {getattr(response, 'status_code', 'unknown')}: {body}",
        )
    try:
        payload = response.json()
    except Exception as exc:
        return CaseLawResult(status="UNAVAILABLE", query=clean_query, matter_id=matter, cases=[], reason=f"invalid JSON: {exc}")

    cases: list[CaseLawCase] = []
    rows = _result_rows(payload)
    target_state = Path(state_dir) if state_dir is not None else Path("veritas_legal_state")
    for row in rows[:5]:
        case = CaseLawCase(
            case_name=_case_name(row),
            citation=_citation(row),
            court=str(row.get("court") or row.get("court_citation_string") or "").strip(),
            date_filed=str(row.get("dateFiled") or row.get("date_filed") or "").strip(),
            url=_url(row),
        )
        _write_external_case_record(target_state, matter, clean_query, case, row)
        cases.append(case)
    return CaseLawResult(
        status="OK",
        query=clean_query,
        matter_id=matter,
        cases=cases,
        reason="" if cases else "no results returned",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
