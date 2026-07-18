from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


DATE_RE = re.compile(r"\b(?:19|20)\d{2}(?:-\d{1,2}-\d{1,2})?|\b\d{1,2}/\d{1,2}/(?:19|20)\d{2}\b")
ENTITY_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
SECRET_RE = re.compile(
    r"(bearer\s+[a-z0-9._-]+|"
    r"(?:api[_-]?key|secret|token|password|passwd|private[_ -]?key|refresh"
    r"_token|access"
    r"_token|client"
    r"_secret|oauth)\s*[:=]?\s*[^\s,;\"']+|"
    r"BEGIN [A-Z ]*PRIVATE KEY)",
    re.IGNORECASE,
)
MAX_FILE_BYTES = 5_000_000


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class EvidenceRecord:
    ts: int
    matter_id: str
    source_doc_id: str
    source_path: str
    source_hash: str
    source_sha256: str
    text_sha256: str
    are_event_sha: str
    dates: list[str]
    entities: list[str]
    excerpt: str
    redactions: int
    parser: str


@dataclass
class Contradiction:
    matter_id: str
    contradiction_type: str
    description: str
    source_doc_id_a: str
    source_hash_a: str
    excerpt_a: str
    source_doc_id_b: str
    source_hash_b: str
    excerpt_b: str
    confidence: str = "rule_based_candidate"


def safe_id(value: str, fallback: str = "matter_default") -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    return clean[:120] or fallback


def source_doc_id_for(matter_id: str, source_hash: str) -> str:
    digest = hashlib.sha256(f"{matter_id}|{source_hash}".encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"src_{digest}"


def build_legal_are_event_text(
    *,
    matter_id: str,
    source_doc_id: str,
    source_hash: str,
    path: Path,
    excerpt: str,
    dates: list[str],
    entities: list[str],
    parser_name: str,
    event_type: str = "legal_source_ingested",
    parser_chunk_id: str | None = None,
    page_number: int | None = None,
    timecode: float | str | None = None,
) -> str:
    payload = {
        "event_type": event_type,
        "matter_id": matter_id,
        "source_doc_id": source_doc_id,
        "source_hash": source_hash,
        "source_path": str(path),
        "parser": parser_name,
        "parser_chunk_id": parser_chunk_id,
        "page_number": page_number,
        "timecode": timecode,
        "dates": dates[:20],
        "entities": entities[:20],
        "excerpt": excerpt[:1500],
        "boundary": "evidence organization only; not legal advice",
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def default_append_are_event(text: str) -> dict[str, Any]:
    try:
        from enhanced_governed_are import ARERecord, EnhancedGovernedAREStore

        metadata: dict[str, Any] = {}
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                metadata = {
                    key: payload.get(key)
                    for key in (
                        "matter_id",
                        "source_doc_id",
                        "source_hash",
                        "page_number",
                        "timecode",
                        "parser_chunk_id",
                        "entities",
                    )
                    if key in payload
                }
                if "parser_chunk_id" in metadata:
                    metadata["chunk_id"] = metadata.pop("parser_chunk_id")
                if "entities" in metadata:
                    metadata["entity_tags"] = metadata.pop("entities")
                metadata.setdefault("review_status", "unreviewed")
                metadata.setdefault("authority_level", "attorney_review_required")
                metadata.setdefault("provenance_status", "source_linked")
                metadata.setdefault("fact_type", "legal_event")
                metadata.setdefault("generated_by", "veritas_legal")
        except Exception:
            metadata = {"generated_by": "veritas_legal"}
        store = EnhancedGovernedAREStore(Path("data/veritas_legal_are"))
        try:
            return store.append(ARERecord(text=text, event_type="veritas_legal_event", metadata=metadata))
        finally:
            store.stop()
    except Exception:
        try:
            from original_are_bridge import append_original_are_memory

            return append_original_are_memory(text)
        except Exception:
            value = str(text or "")[:8000]
            return {
                "memory_file": "",
                "record": {
                    "ts": int(time.time()),
                    "sha": hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:10],
                    "text": value,
                },
                "fallback": True,
            }


NEGATION_RE = re.compile(r"\b(?:did\s+not|didn't|was\s+not|wasn't|were\s+not|weren't|is\s+not|isn't|no\s+evidence\s+of|denied|never)\b", re.IGNORECASE)
AFFIRMATION_RE = re.compile(r"\b(?:did|was|were|is|confirmed|reported|sent|received|filed|met|signed|paid|delivered|scheduled|attended)\b", re.IGNORECASE)
STOPWORD_RE = re.compile(r"\b(?:the|and|or|but|with|from|that|this|there|then|than|about|into|onto|over|under|notice|evidence|record|document|reported|stated|says|said|sent|received|filed|met|signed|paid|delivered|scheduled|attended|did|not|was|were|is|on|at|to|of|for|in|by|as|a|an)\b", re.IGNORECASE)


def _normalize_matter(value: str) -> str:
    return safe_id(value)


def _record_keyword_set(record: EvidenceRecord) -> set[str]:
    text = DATE_RE.sub(" ", record.excerpt or "")
    for entity in record.entities:
        text = re.sub(re.escape(entity), " ", text, flags=re.IGNORECASE)
    text = STOPWORD_RE.sub(" ", text)
    return {token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text)}


def _records_share_event_context(left: EvidenceRecord, right: EvidenceRecord) -> bool:
    shared_entities = {item.lower() for item in left.entities} & {item.lower() for item in right.entities}
    if not shared_entities:
        return False
    left_keywords = _record_keyword_set(left)
    right_keywords = _record_keyword_set(right)
    return bool(left_keywords & right_keywords)


def _has_negation(record: EvidenceRecord) -> bool:
    return bool(NEGATION_RE.search(record.excerpt or ""))


def _has_affirmation(record: EvidenceRecord) -> bool:
    return bool(AFFIRMATION_RE.search(record.excerpt or ""))


class EvidenceEngine:
    """Evidence organization prototype. It does not provide legal advice."""

    def __init__(
        self,
        state_dir: Path,
        matter_id: str = "matter_default",
        are_append: Callable[[str], dict[str, Any]] | None = None,
    ):
        self.state_dir = state_dir
        self.matter_id = safe_id(matter_id)
        self.are_append = are_append or default_append_are_event
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.state_dir / "evidence_records.jsonl"
        self.trace_path = self.state_dir / "trace.jsonl"
        self.manifest_path = self.state_dir / "source_manifest.jsonl"
        self.legal_metadata_path = self.state_dir / "legal_metadata.jsonl"

    def ingest_path(self, path: Path) -> list[EvidenceRecord]:
        if path.is_dir():
            records: list[EvidenceRecord] = []
            for child in sorted(p for p in path.rglob("*") if p.is_file()):
                try:
                    records.append(self.ingest_file(child))
                except ValueError as exc:
                    self._append_jsonl(self.trace_path, {"event": "skip_file", "path": str(child), "reason": str(exc)})
            return records
        return [self.ingest_file(path)]

    def ingest_file(self, path: Path) -> EvidenceRecord:
        data = path.read_bytes()
        source_hash = sha256_bytes(data)
        source_doc_id = source_doc_id_for(self.matter_id, source_hash)
        text, parser_name = self._extract_text(path)
        text, redactions = self._redact(text)
        dates = sorted(set(DATE_RE.findall(text)))
        entities = sorted(set(ENTITY_RE.findall(text)))[:25]
        excerpt = re.sub(r"\s+", " ", text).strip()[:500]
        are_event = self.are_append(
            build_legal_are_event_text(
                matter_id=self.matter_id,
                source_doc_id=source_doc_id,
                source_hash=source_hash,
                path=path,
                excerpt=excerpt,
                dates=dates,
                entities=entities,
                parser_name=parser_name,
            )
        )
        are_event_sha = str((are_event.get("record") or {}).get("sha") or "")
        truth_hash = str(are_event.get("truth_hash") or "")
        record = EvidenceRecord(
            ts=int(time.time()),
            matter_id=self.matter_id,
            source_doc_id=source_doc_id,
            source_path=str(path),
            source_hash=source_hash,
            source_sha256=source_hash,
            text_sha256=hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest(),
            are_event_sha=are_event_sha,
            dates=dates,
            entities=entities,
            excerpt=excerpt,
            redactions=redactions,
            parser=parser_name,
        )
        self._append_jsonl(self.records_path, asdict(record))
        self._append_jsonl(
            self.manifest_path,
            {
                "source_path": str(path),
                "matter_id": self.matter_id,
                "source_doc_id": source_doc_id,
                "source_hash": record.source_hash,
                "source_sha256": record.source_sha256,
                "size_bytes": len(data),
                "parser": parser_name,
                "redactions": redactions,
                "ingested_ts": record.ts,
            },
        )
        self._append_jsonl(
            self.legal_metadata_path,
            {
                "matter_id": self.matter_id,
                "source_doc_id": source_doc_id,
                "source_hash": record.source_hash,
                "source_path": str(path),
                "page_number": None,
                "timecode": None,
                "entity_tags": entities,
                "are_event_sha": are_event_sha,
                "truth_hash": truth_hash,
                "lane": "LEGAL_CASE",
                "scope": "matter",
                "review_status": "unreviewed",
                "provenance_status": "source_linked",
                "authority_level": "attorney_review_required",
                "faiss_authority": False,
                "search_authority": False,
            },
        )
        self._append_jsonl(
            self.trace_path,
            {
                "event": "ingest_file",
                "matter_id": self.matter_id,
                "source_doc_id": source_doc_id,
                "source_sha256": record.source_sha256,
                "are_event_sha": are_event_sha,
                "truth_hash": truth_hash,
                "path": str(path),
            },
        )
        return record

    def ingest_parser_record(self, parser_record: dict[str, Any]) -> EvidenceRecord:
        """
        Adapt a Claire/Veritas parser chunk into a legal evidence signal.

        The parser chunk is not the authority by itself. This method wraps it in
        matter/source metadata, appends a chronological ARE event, then stores
        governed metadata that references the ARE event sha.
        """
        source_path = str(parser_record.get("source_path") or parser_record.get("title") or "parser_record")
        text_raw = str(parser_record.get("text") or "")
        source_hash = str(parser_record.get("file_sha256") or parser_record.get("source_hash") or "").strip()
        if not source_hash:
            source_hash = hashlib.sha256(
                f"{source_path}\n{text_raw}".encode("utf-8", errors="ignore")
            ).hexdigest()
        source_doc_id = source_doc_id_for(self.matter_id, source_hash)
        text, redactions = self._redact(text_raw)
        dates = sorted(set(DATE_RE.findall(text)))
        entities = sorted(set(ENTITY_RE.findall(text)))[:25]
        excerpt = re.sub(r"\s+", " ", text).strip()[:500]
        parser_name = str(parser_record.get("extraction_method") or parser_record.get("parser") or "parser_record")
        parser_chunk_id = str(parser_record.get("chunk_id") or "") or None
        page_number = parser_record.get("page_number")
        timecode = parser_record.get("media_seconds") if parser_record.get("media_seconds") is not None else parser_record.get("timecode")
        are_event = self.are_append(
            build_legal_are_event_text(
                matter_id=self.matter_id,
                source_doc_id=source_doc_id,
                source_hash=source_hash,
                path=Path(source_path),
                excerpt=excerpt,
                dates=dates,
                entities=entities,
                parser_name=parser_name,
                event_type="legal_parser_chunk_ingested",
                parser_chunk_id=parser_chunk_id,
                page_number=page_number if isinstance(page_number, int) else None,
                timecode=timecode,
            )
        )
        are_event_sha = str((are_event.get("record") or {}).get("sha") or "")
        truth_hash = str(are_event.get("truth_hash") or "")
        record = EvidenceRecord(
            ts=int(time.time()),
            matter_id=self.matter_id,
            source_doc_id=source_doc_id,
            source_path=source_path,
            source_hash=source_hash,
            source_sha256=source_hash,
            text_sha256=hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest(),
            are_event_sha=are_event_sha,
            dates=dates,
            entities=entities,
            excerpt=excerpt,
            redactions=redactions,
            parser=parser_name,
        )
        self._append_jsonl(self.records_path, asdict(record))
        self._append_jsonl(
            self.manifest_path,
            {
                "source_path": source_path,
                "matter_id": self.matter_id,
                "source_doc_id": source_doc_id,
                "source_hash": source_hash,
                "source_sha256": source_hash,
                "chunk_id": parser_chunk_id,
                "parser": parser_name,
                "redactions": redactions,
                "ingested_ts": record.ts,
            },
        )
        self._append_jsonl(
            self.legal_metadata_path,
            {
                "matter_id": self.matter_id,
                "source_doc_id": source_doc_id,
                "source_hash": source_hash,
                "source_path": source_path,
                "parser_chunk_id": parser_chunk_id,
                "page_number": page_number if isinstance(page_number, int) else None,
                "timecode": timecode,
                "entity_tags": entities,
                "are_event_sha": are_event_sha,
                "truth_hash": truth_hash,
                "lane": "LEGAL_CASE",
                "scope": "matter",
                "review_status": "unreviewed",
                "provenance_status": "source_linked",
                "authority_level": "attorney_review_required",
                "faiss_authority": False,
                "search_authority": False,
            },
        )
        self._append_jsonl(
            self.trace_path,
            {
                "event": "ingest_parser_record",
                "matter_id": self.matter_id,
                "source_doc_id": source_doc_id,
                "source_sha256": source_hash,
                "parser_chunk_id": parser_chunk_id,
                "are_event_sha": are_event_sha,
                "truth_hash": truth_hash,
                "path": source_path,
            },
        )
        return record

    def ingest_parser_jsonl(self, parser_jsonl: Path) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for line_no, line in enumerate(parser_jsonl.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                parser_record = json.loads(line)
            except json.JSONDecodeError as exc:
                self._append_jsonl(
                    self.trace_path,
                    {
                        "event": "skip_parser_record",
                        "matter_id": self.matter_id,
                        "parser_jsonl": str(parser_jsonl),
                        "line": line_no,
                        "reason": f"invalid json: {exc}",
                    },
                )
                continue
            records.append(self.ingest_parser_record(parser_record))
        return records

    def _extract_text(self, path: Path) -> tuple[str, str]:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(f"file too large for prototype parser: {size} bytes")
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md", ".log", ".csv", ".json", ".jsonl"}:
            return path.read_text(encoding="utf-8", errors="ignore"), "text"
        if suffix == ".docx":
            return self._extract_docx(path), "docx"
        if suffix == ".pdf":
            return self._extract_pdf(path), "pdf"
        raise ValueError(f"unsupported file type: {suffix or '<none>'}")

    @staticmethod
    def _extract_docx(path: Path) -> str:
        with zipfile.ZipFile(path) as z:
            raw = z.read("word/document.xml").decode("utf-8", errors="ignore")
        return html.unescape(re.sub(r"<[^>]+>", " ", raw))

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        try:
            import PyPDF2  # type: ignore
        except Exception as exc:
            raise ValueError("PDF parsing requires optional PyPDF2") from exc
        parts: list[str] = []
        with path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:25]:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
        return "\n".join(parts)

    @staticmethod
    def _redact(text: str) -> tuple[str, int]:
        count = 0

        def repl(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return "[REDACTED_SECRET_MARKER]"

        return SECRET_RE.sub(repl, text), count

    def records(self) -> list[EvidenceRecord]:
        out: list[EvidenceRecord] = []
        if not self.records_path.exists():
            return out
        for line in self.records_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                out.append(EvidenceRecord(**json.loads(line)))
            except Exception:
                continue
        return out

    def build_timeline(self) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        for record in self.records():
            for date in record.dates:
                timeline.append(
                    {
                        "date": date,
                        "matter_id": record.matter_id,
                        "source_doc_id": record.source_doc_id,
                        "source_sha256": record.source_sha256,
                        "are_event_sha": record.are_event_sha,
                        "excerpt": record.excerpt,
                    }
                )
        return sorted(timeline, key=lambda item: item["date"])

    def detect_contradictions(self, matter_id: str | None = None) -> list[Contradiction]:
        target_matter = _normalize_matter(matter_id or self.matter_id)
        records = [record for record in self.records() if record.matter_id == target_matter]
        contradictions: list[Contradiction] = []
        seen: set[tuple[str, str, str]] = set()

        for idx, left in enumerate(records):
            for right in records[idx + 1:]:
                if left.source_doc_id == right.source_doc_id:
                    continue
                if not _records_share_event_context(left, right):
                    continue

                left_dates = set(left.dates)
                right_dates = set(right.dates)
                if left_dates and right_dates and left_dates != right_dates:
                    key = ("conflicting_dates", left.source_doc_id, right.source_doc_id)
                    if key not in seen:
                        contradictions.append(
                            Contradiction(
                                matter_id=target_matter,
                                contradiction_type="conflicting_dates",
                                description=(
                                    "Records reference overlapping entities/event terms but list different date strings: "
                                    f"{sorted(left_dates)} versus {sorted(right_dates)}."
                                ),
                                source_doc_id_a=left.source_doc_id,
                                source_hash_a=left.source_hash,
                                excerpt_a=left.excerpt,
                                source_doc_id_b=right.source_doc_id,
                                source_hash_b=right.source_hash,
                                excerpt_b=right.excerpt,
                            )
                        )
                        seen.add(key)

                left_negated = _has_negation(left)
                right_negated = _has_negation(right)
                left_affirmed = _has_affirmation(left)
                right_affirmed = _has_affirmation(right)
                if left_dates & right_dates and left_negated != right_negated and (left_affirmed or right_affirmed):
                    key = ("negation_conflict", left.source_doc_id, right.source_doc_id)
                    if key not in seen:
                        contradictions.append(
                            Contradiction(
                                matter_id=target_matter,
                                contradiction_type="negation_conflict",
                                description=(
                                    "Records reference the same date/entity context but one excerpt contains a negating phrase "
                                    "while the other contains an affirmative factual phrase."
                                ),
                                source_doc_id_a=left.source_doc_id,
                                source_hash_a=left.source_hash,
                                excerpt_a=left.excerpt,
                                source_doc_id_b=right.source_doc_id,
                                source_hash_b=right.source_hash,
                                excerpt_b=right.excerpt,
                            )
                        )
                        seen.add(key)
        return contradictions

    def generate_review_packet(self, matter_id: str | None = None, output_format: str = "markdown") -> Path:
        target_matter = _normalize_matter(matter_id or self.matter_id)
        output_format = str(output_format or "markdown").lower().strip()
        records = [record for record in self.records() if record.matter_id == target_matter]
        generated_at = datetime.now(timezone.utc).isoformat()
        packet_text = self._review_packet_markdown(target_matter, records, generated_at)

        if output_format in {"markdown", "md"}:
            out_path = self.state_dir / f"{target_matter}_attorney_review_packet.md"
            out_path.write_text(packet_text, encoding="utf-8")
            return out_path
        if output_format == "pdf":
            out_path = self.state_dir / f"{target_matter}_attorney_review_packet.pdf"
            self._write_simple_pdf(out_path, packet_text)
            return out_path
        raise ValueError("output_format must be 'markdown' or 'pdf'")

    def _review_packet_markdown(self, matter_id: str, records: list[EvidenceRecord], generated_at: str) -> str:
        timeline = [item for item in self.build_timeline() if item.get("matter_id") == matter_id]
        contradictions = self.detect_contradictions(matter_id)
        redacted_records = [record for record in records if record.redactions]
        lines = [
            f"# Veritas Legal Attorney-Review Packet",
            "",
            "## Matter Header",
            f"- Matter ID: {matter_id}",
            f"- Generated at: {generated_at}",
            f"- Evidence record count: {len(records)}",
            "",
            "## Exhibit Index",
        ]
        if records:
            for number, record in enumerate(records, start=1):
                lines.append(
                    f"{number}. `{record.source_doc_id}` | SHA-256 `{record.source_hash}` | {record.source_path}"
                )
        else:
            lines.append("No source documents were found for this matter.")

        lines.extend(["", "## Timeline"])
        if timeline:
            for item in timeline:
                lines.append(
                    f"- {item.get('date')}: {item.get('excerpt')} "
                    f"[source_doc_id: `{item.get('source_doc_id')}`, source_sha256: `{item.get('source_sha256')}`, ARE: `{item.get('are_event_sha')}`]"
                )
        else:
            lines.append("No date references were found in the processed evidence.")

        lines.extend(["", "## Contradictions"])
        if contradictions:
            for number, contradiction in enumerate(contradictions, start=1):
                lines.extend([
                    f"{number}. {contradiction.description}",
                    f"   - Source A: `{contradiction.source_doc_id_a}` | SHA-256 `{contradiction.source_hash_a}` | Excerpt: {contradiction.excerpt_a}",
                    f"   - Source B: `{contradiction.source_doc_id_b}` | SHA-256 `{contradiction.source_hash_b}` | Excerpt: {contradiction.excerpt_b}",
                ])
        else:
            lines.append("NO_CONTRADICTIONS_DETECTED by the current rule-based checks.")

        lines.extend(["", "## Verified Case Law"])
        try:
            from .courtlistener_client import lookup_case_law

            lookup = lookup_case_law(matter_id=matter_id, query=matter_id, state_dir=self.state_dir)
            if lookup.status == "OK" and lookup.cases:
                for case in lookup.cases:
                    lines.append(
                        f"- {case.case_name or 'Unknown case'} | {case.citation or 'No citation listed'} | "
                        f"{case.court or 'Unknown court'} | {case.date_filed or 'Unknown date'} | {case.url or 'No URL'}"
                    )
            else:
                lines.append(f"Case-law verification unavailable: {lookup.reason or lookup.status}.")
        except Exception as exc:
            lines.append(f"Case-law verification unavailable: {exc}.")

        lines.extend(["", "## Redaction Notice"])
        if redacted_records:
            total = sum(record.redactions for record in redacted_records)
            lines.append(f"Secret-like markers were redacted {total} time(s) before evidence records were written.")
            for record in redacted_records:
                lines.append(f"- `{record.source_doc_id}` | {record.redactions} redaction(s) | {record.source_path}")
        else:
            lines.append("No secret-like markers were redacted during ingestion.")

        lines.extend([
            "",
            "## Boundary",
            "This is research support and evidence organization only, not legal advice. A qualified attorney must verify legal arguments, citations, deadlines, filing strategy, and any source quotations.",
        ])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _write_simple_pdf(path: Path, text: str) -> None:
        def esc(value: str) -> str:
            return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        lines = []
        for raw in text.splitlines():
            while len(raw) > 92:
                lines.append(raw[:92])
                raw = raw[92:]
            lines.append(raw)
        pages = [lines[i:i + 42] for i in range(0, len(lines), 42)] or [[""]]
        objects: list[bytes] = []
        catalog_id = 1
        pages_id = 2
        page_ids: list[int] = []
        content_ids: list[int] = []
        next_id = 3
        for _page in pages:
            page_ids.append(next_id)
            content_ids.append(next_id + 1)
            next_id += 2
        objects.append(f"{catalog_id} 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n".encode())
        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objects.append(f"{pages_id} 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>\nendobj\n".encode())
        for page_id, content_id, page_lines in zip(page_ids, content_ids, pages):
            content = ["BT", "/F1 10 Tf", "50 760 Td"]
            first = True
            for line in page_lines:
                if first:
                    content.append(f"({esc(line)}) Tj")
                    first = False
                else:
                    content.append(f"0 -16 Td ({esc(line)}) Tj")
            content.append("ET")
            stream = "\n".join(content).encode("latin-1", errors="replace")
            objects.append(
                f"{page_id} 0 obj\n<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_id} 0 R >>\nendobj\n".encode()
            )
            objects.append(
                f"{content_id} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream\nendobj\n"
            )
        offset = 0
        out = bytearray(b"%PDF-1.4\n")
        offset = len(out)
        offsets = [0]
        for obj in objects:
            offsets.append(offset)
            out.extend(obj)
            offset += len(obj)
        xref_at = len(out)
        out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
        for item in offsets[1:]:
            out.extend(f"{item:010d} 00000 n \n".encode())
        out.extend(f"trailer\n<< /Size {len(objects)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode())
        path.write_bytes(bytes(out))


    def summary(self) -> dict[str, Any]:
        records = self.records()
        return {
            "matter_id": self.matter_id,
            "record_count": len(records),
            "date_count": sum(len(r.dates) for r in records),
            "entity_count": sum(len(r.entities) for r in records),
            "redaction_count": sum(r.redactions for r in records),
            "source_doc_count": len({r.source_doc_id for r in records}),
            "are_event_count": len([r for r in records if r.are_event_sha]),
            "search_authority": "source_records_and_are_events_only",
            "faiss_authority": False,
            "timeline": self.build_timeline()[:25],
            "notice": "Evidence organization only; not legal advice.",
            "state_dir": str(self.state_dir),
            "records_path": str(self.records_path),
            "manifest_path": str(self.manifest_path),
            "legal_metadata_path": str(self.legal_metadata_path),
            "trace_path": str(self.trace_path),
        }

    @staticmethod
    def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def detect_contradictions(matter_id: str) -> list[Contradiction]:
    engine = EvidenceEngine(Path("veritas_legal_state"), matter_id=matter_id)
    return engine.detect_contradictions(matter_id)


def generate_review_packet(matter_id: str, output_format: str = "markdown") -> Path:
    engine = EvidenceEngine(Path("veritas_legal_state"), matter_id=matter_id)
    return engine.generate_review_packet(matter_id, output_format)


def claire_explains_summary(summary: dict[str, Any]) -> str:
    timeline = summary.get("timeline") or []
    record_count = int(summary.get("record_count", 0) or 0)
    date_count = int(summary.get("date_count", 0) or 0)
    entity_count = int(summary.get("entity_count", 0) or 0)
    redaction_count = int(summary.get("redaction_count", 0) or 0)
    lines = [
        "Claire explains Veritas Legal:",
        "",
        "Veritas Legal is an evidence organizer.",
        "I organized the uploaded evidence so a human reviewer can understand it faster. This is not legal advice, and I did not file or send anything.",
        "",
        "What I did:",
        f"- Matter ID: {summary.get('matter_id', 'matter_default')}",
        f"- Ingested evidence records: {record_count}",
        f"- Source documents: {summary.get('source_doc_count', 0)}",
        f"- ARE chronological events referenced: {summary.get('are_event_count', 0)}",
        f"- Found date references: {date_count}",
        f"- Found possible names/entities: {entity_count}",
        f"- Redacted secret-like markers: {redaction_count}",
        "- Wrote hashes, a source manifest, a trace log, and a timeline.",
    ]
    if timeline:
        lines.append("")
        lines.append("What I found first:")
        for item in timeline[:5]:
            lines.append(f"- {item.get('date')}: {item.get('excerpt')}")
    else:
        lines.extend(
            [
                "",
                "What I found first:",
                "- I did not find date references in the processed evidence. That may be normal for some files, but it means the timeline needs human review or more source material.",
            ]
        )
    lines.extend(
        [
            "",
            "What you can do next:",
            "- Ask me to explain the timeline.",
            "- Ask me what evidence is missing.",
            "- Ask me to list the files and checksums.",
            "- Ask me to prepare a non-legal evidence summary for attorney review.",
            "",
            "Where the proof files are:",
            "- source_manifest.jsonl proves which files were ingested and their hashes.",
            "- evidence_records.jsonl stores redacted excerpts, dates, entities, and checksums.",
            "- legal_metadata.jsonl links matter/source metadata to the chronological ARE event.",
            "- trace.jsonl records what the engine did.",
            "",
            "Boundary: this is research support and evidence organization only, not legal advice. A qualified attorney must verify legal arguments, citations, deadlines, filing strategy, and any source quotations.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Veritas Legal evidence organizer")
    parser.add_argument("paths", nargs="+", help="Files or folders to ingest")
    parser.add_argument("--state-dir", default="veritas_legal_state", help="Local state directory")
    parser.add_argument("--matter-id", default="matter_default", help="Matter/case identifier for scoped legal ingest")
    parser.add_argument("--parser-jsonl", action="store_true", help="Treat paths as claire_parser JSONL chunk output")
    parser.add_argument("--claire-explains", action="store_true", help="Print Claire's plain-English explanation")
    args = parser.parse_args(argv)

    engine = EvidenceEngine(Path(args.state_dir), matter_id=args.matter_id)
    for raw_path in args.paths:
        path = Path(raw_path)
        if args.parser_jsonl:
            engine.ingest_parser_jsonl(path)
        else:
            engine.ingest_path(path)
    summary = engine.summary()
    print(json.dumps(summary, indent=2))
    if args.claire_explains:
        print("\n" + claire_explains_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
