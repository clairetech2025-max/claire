from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claire_are.core import AREStore

from .contracts import NormalizedDocument, ProvenanceSearchResult


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_hardened_parser() -> Any:
    parser_path = Path(__file__).resolve().parents[1] / "claire_parser"
    if not parser_path.is_file():
        raise FileNotFoundError("The hardened extensionless ClaireParser is unavailable")
    module_name = "claire_crb_hardened_parser"
    loader = importlib.machinery.SourceFileLoader(module_name, str(parser_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise RuntimeError("Unable to load the hardened ClaireParser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


class CRBPipeline:
    """Acquisition-to-ARE bridge; evidence providers remain read-only."""

    def __init__(self, store: AREStore, *, lane: str = "legal") -> None:
        self.store = store
        self.lane = lane

    def ingest_document(self, document: NormalizedDocument) -> dict[str, Any]:
        document_key = self._document_key(document)
        with tempfile.TemporaryDirectory(prefix="claire-crb-") as temporary:
            root = Path(temporary)
            staged = root / self._safe_filename(document.filename)
            staged.write_bytes(document.content)
            output = root / "parser_chunks.jsonl"
            parser_module = load_hardened_parser()
            parser = parser_module.ClaireParser(
                output_jsonl=output,
                temp_root=root / "parser_temp",
                enable_ocr=False,
                enable_media=False,
            )
            parsed_units = parser.parse_path(staged)
            chunks = self._read_jsonl(output)
            if parsed_units <= 0 or not chunks:
                raise ValueError(f"Existing ClaireParser produced no chunks for {document.filename}")

            ingested: list[dict[str, Any]] = []
            deduplicated: list[dict[str, Any]] = []
            existing_keys = self._existing_chunk_keys()
            for chunk in chunks:
                chunk_hash = str(chunk.get("sha256") or hashlib.sha256(str(chunk.get("text") or "").encode()).hexdigest())
                chunk_key = hashlib.sha256(f"{document_key}:{chunk_hash}".encode()).hexdigest()
                if chunk_key in existing_keys:
                    deduplicated.append({"parser_chunk_id": chunk.get("chunk_id"), "chunk_key": chunk_key})
                    continue
                metadata = self._metadata(document, chunk, document_key, chunk_key)
                result = self.store.ingest(
                    text=str(chunk.get("text") or ""),
                    lane=self.lane,
                    source="claire_crb.google_drive",
                    metadata=metadata,
                )
                if not result.get("accepted"):
                    raise ValueError(f"ARE rejected CRB chunk: {result.get('reason')}")
                ingested.append({
                    "parser_chunk_id": chunk.get("chunk_id"),
                    "parser_chunk_hash": chunk_hash,
                    "truth_hash": result.get("truth_hash"),
                })
                existing_keys.add(chunk_key)
        return {
            "provider": document.provider,
            "provider_document_id": document.provider_document_id,
            "document_key": document_key,
            "content_hash": document.content_hash,
            "parsed_chunks": len(chunks),
            "ingested_chunks": len(ingested),
            "deduplicated_chunks": len(deduplicated),
            "ingested": ingested,
            "deduplicated": deduplicated,
        }

    def search(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        recalled = self.store.recall(query=query, lane=self.lane, limit=limit, log=False)
        retrieval_timestamp = _utc_now()
        results: list[dict[str, Any]] = []
        for memory in recalled.get("memories", []):
            metadata = dict(memory.get("metadata") or {})
            if metadata.get("kind") != "crb_parser_chunk":
                continue
            result = ProvenanceSearchResult(
                query=query,
                matched_excerpt=self._matched_excerpt(str(memory.get("text") or ""), query),
                provider=str(metadata.get("provider") or ""),
                provider_document_id=str(metadata.get("provider_document_id") or ""),
                original_uri=str(metadata.get("original_uri") or ""),
                original_path=str(metadata.get("original_path") or ""),
                title=str(metadata.get("title") or ""),
                filename=str(metadata.get("filename") or ""),
                mime_type=str(metadata.get("mime_type") or ""),
                source_content_hash=str(metadata.get("source_content_hash") or ""),
                parser_chunk_id=str(metadata.get("parser_chunk_id") or ""),
                parser_chunk_hash=str(metadata.get("parser_chunk_hash") or ""),
                extraction_method=str(metadata.get("extraction_method") or ""),
                source_created_time=str(metadata.get("source_created_time") or ""),
                source_modified_time=str(metadata.get("source_modified_time") or ""),
                retrieval_timestamp=retrieval_timestamp,
                are_truth_hash=str(memory.get("truth_hash") or ""),
            )
            results.append(result.to_dict())
        return results

    def _existing_chunk_keys(self) -> set[str]:
        keys: set[str] = set()
        for envelope in self.store.truth.envelopes():
            payload = envelope.get("payload") or {}
            if payload.get("event_type") != "memory":
                continue
            metadata = payload.get("metadata") or {}
            if metadata.get("kind") == "crb_parser_chunk" and metadata.get("crb_chunk_key"):
                keys.add(str(metadata["crb_chunk_key"]))
        return keys

    @staticmethod
    def _document_key(document: NormalizedDocument) -> str:
        return hashlib.sha256(
            f"{document.provider}:{document.provider_document_id}:{document.content_hash}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _metadata(
        document: NormalizedDocument,
        chunk: dict[str, Any],
        document_key: str,
        chunk_key: str,
    ) -> dict[str, Any]:
        return {
            "kind": "crb_parser_chunk",
            "schema_version": "crb.normalized-document.v1",
            "provider": document.provider,
            "provider_document_id": document.provider_document_id,
            "original_uri": document.original_uri,
            "original_path": document.original_path,
            "title": document.title,
            "filename": document.filename,
            "mime_type": document.mime_type,
            "source_content_hash": document.content_hash,
            "source_created_time": document.created_time,
            "source_modified_time": document.modified_time,
            "acquired_at": document.acquired_at,
            "parser_chunk_id": chunk.get("chunk_id"),
            "parser_chunk_hash": chunk.get("sha256"),
            "parser_file_hash": chunk.get("file_sha256"),
            "extraction_method": chunk.get("extraction_method"),
            "parser_sequence": chunk.get("sequence"),
            "parser_total_chunks": chunk.get("total_chunks"),
            "parent_archive": chunk.get("parent_archive"),
            "page_number": chunk.get("page_number"),
            "media_seconds": chunk.get("media_seconds"),
            "crb_document_key": document_key,
            "crb_chunk_key": chunk_key,
            "veritas_compatibility": {
                "source_doc_id_basis": f"{document.provider}:{document.provider_document_id}",
                "source_hash": document.content_hash,
                "parser_chunk_id": chunk.get("chunk_id"),
                "parser_chunk_hash": chunk.get("sha256"),
            },
        }

    @staticmethod
    def _safe_filename(filename: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name).strip("._")
        return clean or "evidence.txt"

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _matched_excerpt(text: str, query: str, radius: int = 260) -> str:
        lowered = text.lower()
        index = lowered.find(str(query or "").lower())
        if index < 0:
            terms = [term for term in re.findall(r"[a-z0-9']+", str(query or "").lower()) if len(term) > 2]
            index = min((lowered.find(term) for term in terms if lowered.find(term) >= 0), default=0)
        start = max(0, index - radius)
        end = min(len(text), index + len(query) + radius)
        return text[start:end].strip()
