from __future__ import annotations

import hashlib
import html
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import requests

from claire_vde.collectors import CollectorRun, EvidenceCollector
from claire_vde.evidence import EvidenceDraft
from claire_vde.storage import VentureRepository


DEFAULT_ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"
DEFAULT_QUERY = "artificial intelligence"
DEFAULT_CUTOFF = "2024-01-01"
DEFAULT_VERSION = "federal_register_collector_v1"
DEFAULT_USER_AGENT = "CLAIRE Venture Intelligence Federal Register Collector/1.0 (respectful; contact local-dev)"
DEFAULT_SEARCH_TERMS = [
    "artificial intelligence",
    "automated decision systems",
    "AI safety",
    "algorithmic accountability",
    "machine learning governance",
]


@dataclass(frozen=True)
class FederalRegisterCollectorConfig:
    query: str = DEFAULT_QUERY
    cutoff_date: str = DEFAULT_CUTOFF
    endpoint: str = DEFAULT_ENDPOINT
    per_page: int = 20
    max_pages: int = 1
    user_agent: str = DEFAULT_USER_AGENT
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 30.0
    retries: int = 3
    backoff_base_s: float = 0.5
    respectful_delay_s: float = 0.2
    version: str = DEFAULT_VERSION
    domain: str = "AI_AGENT_GOVERNANCE"
    search_terms: list[str] = field(default_factory=lambda: list(DEFAULT_SEARCH_TERMS))


class FederalRegisterCollector(EvidenceCollector):
    name = "federal_register"

    def __init__(
        self,
        *,
        repository: VentureRepository | None = None,
        config: FederalRegisterCollectorConfig | None = None,
        cursor: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or FederalRegisterCollectorConfig()
        self.cursor = cursor
        self.session = session or requests.Session()

    def collect(self) -> CollectorRun:
        state = self._load_state()
        errors: list[str] = []
        evidence: list[EvidenceDraft] = []
        duplicates: list[dict[str, Any]] = []
        result_count = 0
        pages = 0
        last_page_url: str | None = None

        while pages < max(1, int(self.config.max_pages)):
            request_spec = self._request_spec(state)
            last_page_url = request_spec["url"] if request_spec["url"] else None
            response = self._get(request_spec["url"], request_spec["params"], errors)
            if response is None:
                break
            try:
                body = response.json()
            except Exception as exc:
                errors.append(f"malformed_response:{exc}")
                break
            if not isinstance(body, dict) or "results" not in body:
                errors.append("malformed_response:missing_results")
                break
            page_evidence, page_duplicates, page_state = self._normalize_body(body, request_spec)
            evidence.extend(page_evidence)
            duplicates.extend(page_duplicates)
            result_count += len(body.get("results") or [])
            pages += 1
            state = page_state
            next_url = body.get("next_page_url")
            if not next_url:
                break
            time.sleep(max(0.0, float(self.config.respectful_delay_s)))
            state["next_page_url"] = str(next_url)

        next_cursor = json.dumps(state, sort_keys=True)
        metadata = {
            "collector": self.name,
            "collector_version": self.config.version,
            "domain": self.config.domain,
            "endpoint": self.config.endpoint,
            "query": self.config.query,
            "cutoff": self.config.cutoff_date,
            "search_terms": list(self.config.search_terms),
            "result_count": result_count,
            "pages_fetched": pages,
            "pagination_state": state,
            "source": "Federal Register public API",
            "duplicates": duplicates,
        }
        return CollectorRun(
            collector=self.name,
            evidence=evidence,
            errors=errors,
            next_cursor=next_cursor,
            metadata=metadata,
            error_details=[{"code": self._error_code(item), "message": item} if isinstance(item, str) else item for item in errors],
        )

    def _load_state(self) -> dict[str, Any]:
        raw = self.cursor
        if raw is None and self.repository:
            raw = self.repository.get_collector_cursor(self.name)
        if not raw:
            return {
                "query": self.config.query,
                "cutoff": self.config.cutoff_date,
                "endpoint": self.config.endpoint,
                "page": 1,
                "next_page_url": None,
            }
        try:
            state = json.loads(raw)
            if isinstance(state, dict):
                return state
        except Exception:
            pass
        return {
            "query": self.config.query,
            "cutoff": self.config.cutoff_date,
            "endpoint": self.config.endpoint,
            "page": 1,
            "next_page_url": None,
        }

    def _request_spec(self, state: dict[str, Any]) -> dict[str, Any]:
        next_page_url = state.get("next_page_url")
        if next_page_url:
            return {"url": str(next_page_url), "params": None}
        params = {
            "conditions[term]": self.config.query,
            "conditions[publication_date][gte]": state.get("cutoff") or self.config.cutoff_date,
            "order": "newest",
            "per_page": self.config.per_page,
            "page": int(state.get("page") or 1),
            "format": "json",
        }
        return {"url": self.config.endpoint, "params": params}

    def _get(self, url: str, params: dict[str, Any] | None, errors: list[str]) -> requests.Response | None:
        headers = {"User-Agent": self.config.user_agent, "Accept": "application/json"}
        attempt = 0
        while attempt <= int(self.config.retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=(self.config.connect_timeout_s, self.config.read_timeout_s),
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    retry_after = response.headers.get("Retry-After")
                    delay = self._backoff(attempt, retry_after)
                    errors.append(f"http_{response.status_code}:retrying")
                    time.sleep(delay)
                    attempt += 1
                    continue
                response.raise_for_status()
                return response
            except requests.Timeout:
                errors.append("timeout")
            except requests.RequestException as exc:
                errors.append(f"request_error:{exc}")
            if attempt >= int(self.config.retries):
                break
            time.sleep(self._backoff(attempt, None))
            attempt += 1
        return None

    def _backoff(self, attempt: int, retry_after: Any | None) -> float:
        if retry_after is not None:
            try:
                return max(float(retry_after), 0.0)
            except Exception:
                pass
        return max(0.0, float(self.config.backoff_base_s) * (2**attempt))

    def _normalize_body(self, body: dict[str, Any], request_spec: dict[str, Any]) -> tuple[list[EvidenceDraft], list[dict[str, Any]], dict[str, Any]]:
        evidence: list[EvidenceDraft] = []
        duplicates: list[dict[str, Any]] = []
        seen_source_ids: set[str] = set()
        seen_content_hashes: set[str] = set()
        page = body.get("page") or 1
        next_state = {
            "query": self.config.query,
            "cutoff": self.config.cutoff_date,
            "endpoint": self.config.endpoint,
            "page": int(page) + 1,
            "next_page_url": body.get("next_page_url"),
        }
        for item in body.get("results") or []:
            if not isinstance(item, dict):
                continue
            draft, duplicate = self._normalize_item(item, request_spec)
            if duplicate:
                duplicates.append(duplicate)
                continue
            source_record_id = str(draft.metadata.get("source_record_id") or "")
            content_hash = str(draft.metadata.get("content_hash") or "")
            if source_record_id in seen_source_ids or content_hash in seen_content_hashes:
                duplicates.append(
                    {
                        "source_record_id": source_record_id,
                        "content_hash": content_hash,
                        "reason": "duplicate_within_batch",
                    }
                )
                continue
            seen_source_ids.add(source_record_id)
            seen_content_hashes.add(content_hash)
            evidence.append(draft)
        return evidence, duplicates, next_state

    def _error_code(self, message: str) -> str:
        text = str(message or "")
        if text.startswith("timeout"):
            return "timeout"
        if text.startswith("malformed_response"):
            return "malformed_response"
        if text.startswith("request_error"):
            return "request_error"
        if text.startswith("http_"):
            return text.split(":", 1)[0]
        return "collector_error"

    def _normalize_item(self, item: dict[str, Any], request_spec: dict[str, Any]) -> tuple[EvidenceDraft, dict[str, Any] | None]:
        document_number = str(item.get("document_number") or "").strip()
        title = self._clean_text(item.get("title") or document_number or "Federal Register document").strip() or document_number or "Federal Register document"
        abstract = self._clean_text(item.get("abstract") or "").strip()
        excerpt = self._clean_text(item.get("excerpts") or "").strip()
        text = abstract or excerpt or title
        agencies = item.get("agencies") or []
        agency_names = [str(agency.get("name") or agency.get("raw_name") or "").strip() for agency in agencies if isinstance(agency, dict)]
        source_url = str(item.get("html_url") or "").strip()
        published = str(item.get("publication_date") or "").strip()
        retrieved_at = time.time()
        observed_at = self._iso_to_epoch(published) if published else retrieved_at
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "title": title,
                    "text": text,
                    "publication_date": published,
                    "agencies": agency_names,
                    "type": str(item.get("type") or ""),
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        revision_of = ""
        duplicate_of = ""
        if self.repository and document_number:
            existing = self.repository.get_evidence_by_source_record_id(document_number)
            if existing:
                existing_hash = str(existing.metadata.get("content_hash") or "")
                if existing_hash == content_hash:
                    duplicate_of = str(existing.are_hash)
                else:
                    revision_of = str(existing.are_hash)
        if self.repository and content_hash:
            content_existing = self.repository.get_evidence_by_content_hash(content_hash)
            if content_existing and content_existing.metadata.get("source_record_id") != document_number:
                duplicate_of = str(content_existing.are_hash)
        metadata = {
            "domain": self.config.domain,
            "collector": self.name,
            "collector_version": self.config.version,
            "endpoint": self.config.endpoint,
            "query": self.config.query,
            "search_terms": list(self.config.search_terms),
            "retrieval_cutoff": self.config.cutoff_date,
            "result_count": None,
            "publication_date": published,
            "retrieved_at": retrieved_at,
            "observed_at": observed_at,
            "source_record_id": document_number,
            "source_url": source_url,
            "agency_metadata": agencies,
            "agency_names": agency_names,
            "document_type": str(item.get("type") or ""),
            "docket_number": str(item.get("docket_number") or item.get("docket") or ""),
            "content_hash": content_hash,
            "parser_version": self.config.version,
            "revision_of": revision_of,
            "duplicate_of": duplicate_of,
            "source_system": "Federal Register public API",
        }
        if duplicate_of:
            return EvidenceDraft(
                title=title,
                text=text,
                source="federal_register",
                collector=self.name,
                plane="regulatory_pressure",
                value=0.35,
                precision=1.0,
                confidence=0.8,
                provenance_url=source_url,
                entity_refs=agency_names,
                metadata=metadata,
            ), {"source_record_id": document_number, "content_hash": content_hash, "reason": "duplicate_existing"}
        draft = EvidenceDraft(
            title=title,
            text=text,
            source="federal_register",
            collector=self.name,
            plane="regulatory_pressure",
            value=0.35,
            precision=1.0,
            confidence=0.8,
            provenance_url=source_url,
            entity_refs=agency_names,
            metadata=metadata,
        )
        return draft, None

    def _clean_text(self, value: Any) -> str:
        text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
        return re.sub(r"\s+", " ", text).strip()

    def _iso_to_epoch(self, date_text: str) -> float:
        try:
            dt = datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return time.time()
