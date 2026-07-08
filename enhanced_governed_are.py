from __future__ import annotations

import hashlib
import hmac
import json
import os
import queue
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


LEGAL_METADATA_FIELDS = {
    "matter_id",
    "source_doc_id",
    "source_hash",
    "page_number",
    "timecode",
    "chunk_id",
    "entity_tags",
    "review_status",
    "authority_level",
    "provenance_status",
    "fact_type",
    "generated_by",
    "are_event_sha",
    "truth_hash",
}


@dataclass
class SentinelDecision:
    allowed: bool = True
    reason: str = "accepted"
    rules_triggered: list[str] = field(default_factory=list)


@dataclass
class ARERecord:
    text: str
    ts: int = 0
    event_type: str = "memory"
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "ARERecord":
        self.text = str(self.text or "")[:8000]
        if not self.ts:
            self.ts = int(time.time())
        self.metadata = dict(self.metadata or {})
        return self

    def simple_shape(self, sha: str) -> dict[str, Any]:
        return {"ts": self.ts, "sha": sha[:10], "text": self.text}


@dataclass
class ParserManifest:
    source_path: str
    source_sha256: str
    source_doc_id: str
    matter_id: str
    size_bytes: int
    modified_timestamp: float
    ingested_timestamp: float
    suffix: str
    source_type: str

    @classmethod
    def from_path(cls, path: str | Path, *, matter_id: str) -> "ParserManifest":
        source = Path(path)
        stat = source.stat()
        source_sha256 = sha256_file(source)
        source_doc_id = source_doc_id_for(matter_id, source_sha256)
        return cls(
            source_path=str(source),
            source_sha256=source_sha256,
            source_doc_id=source_doc_id,
            matter_id=matter_id,
            size_bytes=stat.st_size,
            modified_timestamp=stat.st_mtime,
            ingested_timestamp=time.time(),
            suffix=source.suffix.lower(),
            source_type=source.suffix.lower().lstrip(".") or "unknown",
        )


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_doc_id_for(matter_id: str, source_hash: str) -> str:
    return "src_" + hashlib.sha256(f"{matter_id}|{source_hash}".encode("utf-8", errors="ignore")).hexdigest()[:16]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SentinelAdmissionGate:
    def evaluate(self, record: ARERecord) -> SentinelDecision:
        text = record.text or ""
        if not text.strip():
            return SentinelDecision(False, "empty record", ["empty_text"])
        lowered = text.lower()
        if any(marker in lowered for marker in ["api_key=", "password=", "private key", "bearer "]):
            return SentinelDecision(False, "secret-like content rejected", ["secret_like_content"])
        return SentinelDecision(True, "accepted", [])


class DeterministicIndex:
    """
    Rebuildable downstream relevance helper.

    This index is not memory authority. It can be deleted and rebuilt from ARE
    envelopes. It never mutates ARE and only stores references to truth_hash.
    """

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def rebuild(self, envelopes: list[dict[str, Any]]) -> None:
        self.records = []
        for envelope in envelopes:
            decision = envelope.get("decision") or {}
            if not decision.get("allowed", False):
                continue
            payload = envelope.get("payload") or {}
            self.records.append(
                {
                    "truth_hash": envelope.get("truth_hash"),
                    "sha": envelope.get("compat", {}).get("sha"),
                    "text": payload.get("text", ""),
                    "metadata": payload.get("metadata") or {},
                }
            )

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        query_terms = set(str(query or "").lower().split())
        scored: list[tuple[int, dict[str, Any]]] = []
        for record in self.records:
            text_terms = set(str(record.get("text") or "").lower().split())
            score = len(query_terms & text_terms)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "truth_hash": record["truth_hash"],
                "sha": record["sha"],
                "score": score,
                "preview": str(record.get("text") or "")[:300],
                "metadata": record.get("metadata") or {},
            }
            for score, record in scored[:limit]
        ]


class EnhancedGovernedAREStore:
    def __init__(
        self,
        root: str | Path,
        *,
        hmac_key: bytes | None = None,
        max_segment_records: int = 1000,
        gate: SentinelAdmissionGate | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.hmac_key = hmac_key or os.environ.get("CLAIRE_ARE_HMAC_KEY", "local-dev-are-key").encode("utf-8")
        self.max_segment_records = max(1, int(max_segment_records or 1000))
        self.gate = gate or SentinelAdmissionGate()
        self.manifest_path = self.root / "manifest.json"
        self.segment_dir = self.root / "segments"
        self.segment_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.q: queue.Queue[tuple[ARERecord, queue.Queue]] = queue.Queue()
        self._stop = False
        self._writer_error: Exception | None = None
        self.manifest = self._load_manifest()
        self.index = DeterministicIndex()
        self._writer = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer.start()

    def _load_manifest(self) -> dict[str, Any]:
        default = {
            "version": "1.1",
            "current_segment_index": 0,
            "current_segment_records": 0,
            "previous_hash": "0",
            "segments": [],
        }
        if not self.manifest_path.exists():
            return default
        try:
            loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            default.update({k: loaded.get(k, v) for k, v in default.items()})
        except Exception:
            pass
        return default

    def _save_manifest(self) -> None:
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.manifest, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.manifest_path)

    def _segment_path(self, index: int | None = None) -> Path:
        idx = self.manifest["current_segment_index"] if index is None else index
        return self.segment_dir / f"segment_{int(idx):06d}.jsonl"

    def append(self, record: ARERecord | str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(record, str):
            record = ARERecord(text=record)
        elif isinstance(record, dict):
            record = ARERecord(**{k: v for k, v in record.items() if k in ARERecord.__dataclass_fields__})
        ack: queue.Queue = queue.Queue(maxsize=1)
        self.q.put((record, ack))
        result = ack.get()
        if isinstance(result, Exception):
            raise result
        return result

    def _writer_loop(self) -> None:
        while not self._stop or not self.q.empty():
            try:
                record, ack = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                result = self._write_record(record)
                ack.put(result)
            except Exception as exc:
                self._writer_error = exc
                ack.put(exc)
            finally:
                self.q.task_done()

    def _write_record(self, record: ARERecord) -> dict[str, Any]:
        record = record.normalized()
        decision = self.gate.evaluate(record)
        text_sha = sha256_text(record.text)
        compat_sha = text_sha[:10]
        payload = {
            "ts": record.ts,
            "text": record.text,
            "text_sha": text_sha,
            "event_type": record.event_type,
            "metadata": record.metadata,
        }
        with self.lock:
            if int(self.manifest["current_segment_records"]) >= self.max_segment_records:
                self.manifest["current_segment_index"] = int(self.manifest["current_segment_index"]) + 1
                self.manifest["current_segment_records"] = 0
            previous_hash = str(self.manifest.get("previous_hash") or "0")
            unsigned = {
                "envelope_id": "are_" + uuid.uuid4().hex[:16],
                "sequence": self._sequence_number(),
                "previous_hash": previous_hash,
                "payload": payload,
                "decision": asdict(decision),
                "compat": {"ts": record.ts, "sha": compat_sha, "text": record.text},
            }
            truth_hash = sha256_text(canonical_json(unsigned))
            signature = hmac.new(self.hmac_key, truth_hash.encode("utf-8"), hashlib.sha256).hexdigest()
            envelope = dict(unsigned)
            envelope["truth_hash"] = truth_hash
            envelope["signature"] = signature
            with self._segment_path().open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            segment_name = self._segment_path().name
            if segment_name not in self.manifest["segments"]:
                self.manifest["segments"].append(segment_name)
            self.manifest["previous_hash"] = truth_hash
            self.manifest["current_segment_records"] = int(self.manifest["current_segment_records"]) + 1
            self._save_manifest()
        return {"memory_file": str(self._segment_path()), "record": record.simple_shape(compat_sha), "truth_hash": truth_hash, "envelope": envelope}

    def _sequence_number(self) -> int:
        total = 0
        for name in self.manifest.get("segments", []):
            path = self.segment_dir / name
            if path.exists():
                total += len(path.read_text(encoding="utf-8").splitlines())
        return total + 1

    def flush(self) -> None:
        self.q.join()
        if self._writer_error:
            exc = self._writer_error
            self._writer_error = None
            raise exc

    def stop(self, timeout: float = 2.0) -> None:
        self.flush()
        self._stop = True
        self._writer.join(timeout=timeout)

    def envelopes(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in self.manifest.get("segments", []):
            path = self.segment_dir / name
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def last_n(self, n: int) -> list[dict[str, Any]]:
        accepted = [row.get("compat") for row in self.envelopes() if (row.get("decision") or {}).get("allowed")]
        return [row for row in accepted[-max(0, int(n)):] if row]

    def verify_chain(self) -> dict[str, Any]:
        previous = "0"
        count = 0
        for envelope in self.envelopes():
            actual_previous = envelope.get("previous_hash")
            if actual_previous != previous:
                return {"valid": False, "reason": "previous_hash_mismatch", "index": count}
            unsigned = {k: envelope[k] for k in ("envelope_id", "sequence", "previous_hash", "payload", "decision", "compat")}
            expected_truth = sha256_text(canonical_json(unsigned))
            if envelope.get("truth_hash") != expected_truth:
                return {"valid": False, "reason": "truth_hash_mismatch", "index": count}
            expected_sig = hmac.new(self.hmac_key, expected_truth.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(envelope.get("signature") or ""), expected_sig):
                return {"valid": False, "reason": "signature_mismatch", "index": count}
            previous = expected_truth
            count += 1
        return {"valid": True, "records": count, "previous_hash": previous}

    def rebuild_index(self) -> DeterministicIndex:
        self.index = DeterministicIndex()
        self.index.rebuild(self.envelopes())
        return self.index


def copy_store_without_line(src: Path, dst: Path, *, skip_line_index: int) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "manifest.json", dst / "manifest.json")
    (dst / "segments").mkdir(parents=True, exist_ok=True)
    for segment in (src / "segments").glob("*.jsonl"):
        lines = segment.read_text(encoding="utf-8").splitlines()
        kept = [line for idx, line in enumerate(lines) if idx != skip_line_index]
        (dst / "segments" / segment.name).write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
