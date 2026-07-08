from __future__ import annotations

import hashlib
import hmac
import json
import os
import queue
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()


@dataclass
class TruthDecision:
    allowed: bool = True
    reason: str = "accepted"
    rules_triggered: list[str] = field(default_factory=list)


@dataclass
class TruthRecord:
    text: str
    lane: str
    source: str
    event_type: str = "memory"
    metadata: dict[str, Any] = field(default_factory=dict)
    ts: int = 0

    def normalized(self) -> "TruthRecord":
        self.text = str(self.text or "")[:8000]
        self.lane = str(self.lane or "general")
        self.source = str(self.source or "unknown")
        self.event_type = str(self.event_type or "memory")
        self.metadata = dict(self.metadata or {})
        if not self.ts:
            self.ts = int(time.time())
        return self


class TruthSpine:
    """
    Segmented append-first JSONL Truth Spine.

    Segments are archive-not-delete storage: older segment files remain part of
    the verified chain and can be replayed to rebuild downstream indexes.
    """

    def __init__(self, root: str | Path, *, hmac_key: bytes, max_segment_records: int = 1000) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.segment_dir = self.root / "segments"
        self.segment_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self.hmac_key = hmac_key
        self.max_segment_records = max(1, int(max_segment_records))
        self.lock = threading.RLock()
        self.q: queue.Queue[tuple[TruthRecord, TruthDecision, queue.Queue]] = queue.Queue()
        self._stop = False
        self._writer_error: Exception | None = None
        self.manifest = self._load_manifest()
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
            default.update({key: loaded.get(key, value) for key, value in default.items()})
        except Exception:
            pass
        return default

    def _save_manifest(self) -> None:
        tmp = self.manifest_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(self.manifest, indent=2, sort_keys=True))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.manifest_path)

    def _segment_path(self, index: int | None = None) -> Path:
        idx = self.manifest["current_segment_index"] if index is None else index
        return self.segment_dir / f"segment_{int(idx):06d}.jsonl"

    def append(self, record: TruthRecord, decision: TruthDecision | None = None) -> dict[str, Any]:
        ack: queue.Queue = queue.Queue(maxsize=1)
        self.q.put((record, decision or TruthDecision(), ack))
        result = ack.get()
        if isinstance(result, Exception):
            raise result
        return result

    def _writer_loop(self) -> None:
        while not self._stop or not self.q.empty():
            try:
                record, decision, ack = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                ack.put(self._write_record(record, decision))
            except Exception as exc:
                self._writer_error = exc
                ack.put(exc)
            finally:
                self.q.task_done()

    def _sequence_number(self) -> int:
        total = 0
        for name in self.manifest.get("segments", []):
            path = self.segment_dir / name
            if path.exists():
                total += len(path.read_text(encoding="utf-8").splitlines())
        return total + 1

    def _write_record(self, record: TruthRecord, decision: TruthDecision) -> dict[str, Any]:
        record = record.normalized()
        text_sha = sha256_text(record.text)
        compat = {"ts": record.ts, "sha": text_sha[:10], "text": record.text}
        payload = {
            "ts": record.ts,
            "text": record.text,
            "text_sha": text_sha,
            "lane": record.lane,
            "source": record.source,
            "event_type": record.event_type,
            "metadata": record.metadata,
        }
        with self.lock:
            if int(self.manifest["current_segment_records"]) >= self.max_segment_records:
                self.manifest["current_segment_index"] = int(self.manifest["current_segment_index"]) + 1
                self.manifest["current_segment_records"] = 0
            unsigned = {
                "envelope_id": "are_" + uuid.uuid4().hex[:16],
                "sequence": self._sequence_number(),
                "previous_hash": str(self.manifest.get("previous_hash") or "0"),
                "payload": payload,
                "decision": asdict(decision),
                "compat": compat,
            }
            truth_hash = sha256_text(canonical_json(unsigned))
            signature = hmac.new(self.hmac_key, truth_hash.encode("utf-8"), hashlib.sha256).hexdigest()
            envelope = dict(unsigned)
            envelope["truth_hash"] = truth_hash
            envelope["signature"] = signature

            segment_path = self._segment_path()
            with segment_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            segment_name = segment_path.name
            if segment_name not in self.manifest["segments"]:
                self.manifest["segments"].append(segment_name)
            self.manifest["previous_hash"] = truth_hash
            self.manifest["current_segment_records"] = int(self.manifest["current_segment_records"]) + 1
            self._save_manifest()
        return {
            "memory_file": str(segment_path),
            "record": compat,
            "truth_hash": truth_hash,
            "envelope": envelope,
        }

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

    def verify(self) -> dict[str, Any]:
        previous = "0"
        count = 0
        for envelope in self.envelopes():
            if envelope.get("previous_hash") != previous:
                return {"valid": False, "reason": "previous_hash_mismatch", "index": count}
            try:
                unsigned = {key: envelope[key] for key in ("envelope_id", "sequence", "previous_hash", "payload", "decision", "compat")}
            except KeyError:
                return {"valid": False, "reason": "missing_envelope_field", "index": count}
            expected_truth = sha256_text(canonical_json(unsigned))
            if envelope.get("truth_hash") != expected_truth:
                return {"valid": False, "reason": "truth_hash_mismatch", "index": count}
            expected_sig = hmac.new(self.hmac_key, expected_truth.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(envelope.get("signature") or ""), expected_sig):
                return {"valid": False, "reason": "signature_mismatch", "index": count}
            previous = expected_truth
            count += 1
        return {"valid": True, "records": count, "previous_hash": previous}
