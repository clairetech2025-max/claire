from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from itertools import count
from pathlib import Path
from typing import Any

import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde.evidence import AdmissionGate, EvidenceDraft


DEFAULT_FIXTURE_DIR = Path("tests/fixtures/federal_register")
DEFAULT_RESULTS_DIR = Path("benchmark_results")
FEDERAL_REGISTER_ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"
DEFAULT_QUERIES = [
    "artificial intelligence regulatory notice",
    "Management and Budget Office classification system",
    "Native American technology manufacturing grant",
    "advanced manufacturing drone geospatial systems",
]


@dataclass(frozen=True)
class EvidenceItem:
    title: str
    text: str
    source: str
    collector: str
    plane: str
    value: float
    precision: float
    confidence: float
    provenance_url: str
    entity_refs: list[str]
    metadata: dict[str, Any]


@dataclass
class Sample:
    kind: str
    elapsed_s: float
    latency_ms: float
    ok: bool
    records: int | None = None
    error: str = ""


class SampleSink:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.samples: list[Sample] = []

    def add(self, sample: Sample) -> None:
        with self._lock:
            self.samples.append(sample)

    def snapshot(self) -> list[Sample]:
        with self._lock:
            return list(self.samples)


def load_federal_register_items(fixture_dir: Path) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for path in sorted(fixture_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.extend(items_from_federal_register_payload(payload, corpus_label="recorded_federal_register_official_api_response", fixture_file=str(path)))
    if not items:
        raise RuntimeError(f"No Federal Register fixture records found in {fixture_dir}")
    return items


def items_from_federal_register_payload(payload: dict[str, Any], *, corpus_label: str, fixture_file: str = "") -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for raw in payload.get("results") or []:
        if not isinstance(raw, dict):
            continue
        title = clean_text(raw.get("title") or raw.get("document_number") or "Federal Register document")
        abstract = clean_text(raw.get("abstract") or "")
        excerpt = clean_text(raw.get("excerpts") or "")
        text = abstract or excerpt or title
        agencies = raw.get("agencies") or []
        agency_names = [
            str(agency.get("name") or agency.get("raw_name") or "").strip()
            for agency in agencies
            if isinstance(agency, dict)
        ]
        metadata = {
            "fixture_file": fixture_file,
            "source_record_id": str(raw.get("document_number") or ""),
            "publication_date": str(raw.get("publication_date") or ""),
            "document_type": str(raw.get("type") or ""),
            "source_url": str(raw.get("html_url") or ""),
            "agency_names": agency_names,
            "benchmark_corpus": corpus_label,
        }
        items.append(
            EvidenceItem(
                title=title,
                text=text,
                source="federal_register",
                collector="federal_register_benchmark",
                plane="regulatory_pressure",
                value=0.35,
                precision=1.0,
                confidence=0.8,
                provenance_url=str(raw.get("html_url") or ""),
                entity_refs=agency_names,
                metadata=metadata,
            )
        )
    return items


def fetch_live_federal_register_items(*, query: str, pages: int, per_page: int, delay_s: float) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    session = requests.Session()
    headers = {
        "User-Agent": "CLAIRE ARE Truth Spine Benchmark/1.0 respectful local research",
        "Accept": "application/json",
    }
    for page in range(1, max(1, int(pages)) + 1):
        response = session.get(
            FEDERAL_REGISTER_ENDPOINT,
            params={
                "conditions[term]": query,
                "conditions[publication_date][gte]": "2024-01-01",
                "order": "newest",
                "per_page": max(1, min(int(per_page), 1000)),
                "page": page,
                "format": "json",
            },
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        items.extend(items_from_federal_register_payload(payload, corpus_label="live_federal_register_official_api_response"))
        if delay_s > 0 and page < pages:
            time.sleep(delay_s)
    seen: set[str] = set()
    unique: list[EvidenceItem] = []
    for item in items:
        key = str(item.metadata.get("source_record_id") or item.provenance_url or item.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    if not unique:
        raise RuntimeError("Federal Register live fetch returned no evidence records")
    return unique


def clean_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def extract_semantics(item: EvidenceItem) -> dict[str, Any]:
    text = f"{item.title}\n{item.text}\n{json.dumps(item.metadata, sort_keys=True)}"
    dates = sorted(set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)))
    document_numbers = sorted(set(re.findall(r"\b\d{4}-\d{5}\b", text)))
    agencies = list(item.entity_refs)
    ai_terms = sorted(
        term
        for term in [
            "artificial intelligence",
            "advanced manufacturing",
            "geospatial",
            "classification system",
            "workforce",
            "technology",
        ]
        if term in text.lower()
    )
    return {
        "dates": dates,
        "document_numbers": document_numbers,
        "agencies": agencies,
        "ai_terms": ai_terms,
        "source_record_id": item.metadata.get("source_record_id"),
        "source_url": item.provenance_url,
    }


def make_draft(item: EvidenceItem, sequence: int) -> EvidenceDraft:
    metadata = dict(item.metadata)
    metadata["benchmark_sequence"] = sequence
    metadata["semantic_extraction"] = extract_semantics(item)
    return EvidenceDraft(
        title=item.title,
        text=item.text,
        source=item.source,
        collector=item.collector,
        plane=item.plane,
        value=item.value,
        precision=item.precision,
        confidence=item.confidence,
        provenance_url=item.provenance_url,
        entity_refs=list(item.entity_refs),
        metadata=metadata,
        observed_at=time.time(),
    )


def timed_call(kind: str, start_time: float, sink: SampleSink, func) -> Any:
    t0 = time.perf_counter()
    try:
        result = func()
        latency = (time.perf_counter() - t0) * 1000.0
        records = None
        if isinstance(result, dict):
            records = result.get("records")
            if records is None and isinstance(result.get("memories"), list):
                records = len(result["memories"])
        sink.add(Sample(kind=kind, elapsed_s=time.perf_counter() - start_time, latency_ms=latency, ok=True, records=records))
        return result
    except Exception as exc:
        latency = (time.perf_counter() - t0) * 1000.0
        sink.add(
            Sample(
                kind=kind,
                elapsed_s=time.perf_counter() - start_time,
                latency_ms=latency,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        )
        raise


def continuous_writer(
    *,
    store: AREStore,
    items: list[EvidenceItem],
    sink: SampleSink,
    start_time: float,
    stop: threading.Event,
    sequence: Any,
    worker_id: int,
) -> None:
    index = 0
    while not stop.is_set():
        seq = next(sequence)
        item = items[index % len(items)]
        semantics = extract_semantics(item)
        payload = {
            "kind": "truth_spine_sustained_write",
            "worker_id": worker_id,
            "sequence": seq,
            "title": item.title,
            "source_record_id": item.metadata.get("source_record_id"),
            "semantic_extraction": semantics,
        }
        timed_call(
            "write",
            start_time,
            sink,
            lambda payload=payload: store.log_event(
                text=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                lane="business",
                source="are_truth_spine_sustained_load_benchmark",
                event_type="benchmark_write",
                metadata={"source_record_id": item.metadata.get("source_record_id"), "worker_id": worker_id},
            ),
        )
        index += 1


def semantic_admitter(
    *,
    gate: AdmissionGate,
    items: list[EvidenceItem],
    store: AREStore,
    sink: SampleSink,
    start_time: float,
    stop: threading.Event,
    sequence: Any,
    worker_id: int,
    admission_pause_s: float,
) -> None:
    index = 0
    while not stop.is_set():
        seq = next(sequence)
        item = items[index % len(items)]
        draft = make_draft(item, seq)
        evidence = timed_call("admit", start_time, sink, lambda draft=draft: gate.admit(draft))
        extraction = extract_semantics(item)
        timed_call(
            "semantic_extract",
            start_time,
            sink,
            lambda extraction=extraction, evidence=evidence: store.log_event(
                text=json.dumps(
                    {
                        "kind": "semantic_extraction",
                        "worker_id": worker_id,
                        "are_hash": evidence.are_hash,
                        "source_record_id": extraction.get("source_record_id"),
                        "extraction": extraction,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                lane="business",
                source="federal_register_semantic_extractor",
                event_type="semantic_extraction",
                metadata={"are_hash": evidence.are_hash, "source_record_id": extraction.get("source_record_id")},
            ),
        )
        index += 1
        if admission_pause_s > 0:
            stop.wait(admission_pause_s)


def recall_probe(
    *,
    store: AREStore,
    sink: SampleSink,
    start_time: float,
    stop: threading.Event,
    interval_s: float,
) -> None:
    index = 0
    while not stop.is_set():
        query = DEFAULT_QUERIES[index % len(DEFAULT_QUERIES)]
        timed_call("recall", start_time, sink, lambda query=query: store.recall(query=query, lane="business", limit=8, log=True))
        index += 1
        stop.wait(interval_s)


def verify_probe(
    *,
    store: AREStore,
    sink: SampleSink,
    start_time: float,
    stop: threading.Event,
    interval_s: float,
) -> None:
    while not stop.is_set():
        timed_call("verify", start_time, sink, lambda: store.verify())
        stop.wait(interval_s)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return ordered[int(pos)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def bucketize(samples: list[Sample], *, bucket_s: int) -> list[dict[str, Any]]:
    if not samples:
        return []
    max_bucket = int(max(sample.elapsed_s for sample in samples) // bucket_s)
    rows: list[dict[str, Any]] = []
    kinds = sorted({sample.kind for sample in samples})
    for bucket in range(max_bucket + 1):
        start = bucket * bucket_s
        end = start + bucket_s
        row: dict[str, Any] = {"bucket_start_s": start, "bucket_end_s": end}
        for kind in kinds:
            selected = [sample for sample in samples if sample.kind == kind and start <= sample.elapsed_s < end]
            latencies = [sample.latency_ms for sample in selected if sample.ok]
            row[f"{kind}_count"] = len(selected)
            row[f"{kind}_errors"] = len([sample for sample in selected if not sample.ok])
            row[f"{kind}_p50_ms"] = percentile(latencies, 0.50)
            row[f"{kind}_p99_ms"] = percentile(latencies, 0.99)
            row[f"{kind}_max_ms"] = max(latencies) if latencies else math.nan
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row.keys()})
    preferred = ["bucket_start_s", "bucket_end_s"]
    fields = preferred + [field for field in fields if field not in preferred]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_samples(path: Path, samples: list[Sample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["kind", "elapsed_s", "latency_ms", "ok", "records", "error"])
        writer.writeheader()
        for sample in samples:
            writer.writerow(asdict(sample))


def summarize(samples: list[Sample], verify_result: dict[str, Any], args: argparse.Namespace, are_root: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "duration_s": args.duration_s,
        "bucket_s": args.bucket_s,
        "write_threads": args.write_threads,
        "admission_threads": args.admission_threads,
        "recall_interval_s": args.recall_interval_s,
        "verify_interval_s": args.verify_interval_s,
        "are_root": str(are_root),
        "final_verify": verify_result,
        "corpus": {
            "type": "live Federal Register official API fetch" if args.live_federal_register else "recorded Federal Register official API fixtures",
            "fixture_dir": str(args.fixture_dir),
            "live_query": args.live_query if args.live_federal_register else None,
            "live_pages": args.live_pages if args.live_federal_register else None,
            "live_per_page": args.live_per_page if args.live_federal_register else None,
            "records_loaded": args.records_loaded,
            "note": "The benchmark replays real recorded evidence records to create sustained load; it does not fabricate evidence text.",
        },
        "by_kind": {},
    }
    for kind in sorted({sample.kind for sample in samples}):
        selected = [sample for sample in samples if sample.kind == kind]
        latencies = [sample.latency_ms for sample in selected if sample.ok]
        summary["by_kind"][kind] = {
            "count": len(selected),
            "errors": len([sample for sample in selected if not sample.ok]),
            "p50_ms": percentile(latencies, 0.50),
            "p99_ms": percentile(latencies, 0.99),
            "max_ms": max(latencies) if latencies else math.nan,
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sustained ARE Truth Spine benchmark with concurrent real evidence admission.")
    parser.add_argument("--duration-s", type=int, default=120)
    parser.add_argument("--bucket-s", type=int, default=10)
    parser.add_argument("--write-threads", type=int, default=2)
    parser.add_argument("--admission-threads", type=int, default=1)
    parser.add_argument("--recall-interval-s", type=float, default=2.0)
    parser.add_argument("--verify-interval-s", type=float, default=10.0)
    parser.add_argument("--admission-pause-s", type=float, default=0.0)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--live-federal-register", action="store_true")
    parser.add_argument("--live-query", default="artificial intelligence")
    parser.add_argument("--live-pages", type=int, default=3)
    parser.add_argument("--live-per-page", type=int, default=100)
    parser.add_argument("--live-delay-s", type=float, default=0.2)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--max-segment-records", type=int, default=1000)
    parser.add_argument("--hmac-key", default="benchmark-local-key")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_dir = args.fixture_dir.resolve()
    results_dir = args.results_dir.resolve()
    if args.live_federal_register:
        items = fetch_live_federal_register_items(
            query=args.live_query,
            pages=args.live_pages,
            per_page=args.live_per_page,
            delay_s=args.live_delay_s,
        )
    else:
        items = load_federal_register_items(fixture_dir)
    args.records_loaded = len(items)

    run_id = time.strftime("are_sustained_%Y%m%dT%H%M%SZ", time.gmtime())
    output_dir = results_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    are_root = Path(tempfile.mkdtemp(prefix=f"{run_id}_", dir=str(output_dir)))

    store = AREStore(AREConfig(root=are_root, hmac_key=args.hmac_key.encode("utf-8"), max_segment_records=args.max_segment_records))
    gate = AdmissionGate(store, repository=None)
    sink = SampleSink()
    stop = threading.Event()
    sequence = count(1)
    start_time = time.perf_counter()
    threads: list[threading.Thread] = []

    for worker_id in range(args.write_threads):
        threads.append(
            threading.Thread(
                target=continuous_writer,
                kwargs={
                    "store": store,
                    "items": items,
                    "sink": sink,
                    "start_time": start_time,
                    "stop": stop,
                    "sequence": sequence,
                    "worker_id": worker_id,
                },
                daemon=True,
            )
        )
    for worker_id in range(args.admission_threads):
        threads.append(
            threading.Thread(
                target=semantic_admitter,
                kwargs={
                    "gate": gate,
                    "items": items,
                    "store": store,
                    "sink": sink,
                    "start_time": start_time,
                    "stop": stop,
                    "sequence": sequence,
                    "worker_id": worker_id,
                    "admission_pause_s": args.admission_pause_s,
                },
                daemon=True,
            )
        )
    threads.append(
        threading.Thread(
            target=recall_probe,
            kwargs={"store": store, "sink": sink, "start_time": start_time, "stop": stop, "interval_s": args.recall_interval_s},
            daemon=True,
        )
    )
    threads.append(
        threading.Thread(
            target=verify_probe,
            kwargs={"store": store, "sink": sink, "start_time": start_time, "stop": stop, "interval_s": args.verify_interval_s},
            daemon=True,
        )
    )

    for thread in threads:
        thread.start()
    deadline = time.perf_counter() + args.duration_s
    while time.perf_counter() < deadline:
        time.sleep(0.5)
    stop.set()
    for thread in threads:
        thread.join(timeout=5)
    store.truth.flush()
    final_verify = store.verify()
    store.stop()

    samples = sink.snapshot()
    buckets = bucketize(samples, bucket_s=args.bucket_s)
    write_samples(output_dir / "raw_samples.csv", samples)
    write_csv(output_dir / "latency_buckets.csv", buckets)
    summary = summarize(samples, final_verify, args, are_root)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "run_config.json").write_text(json.dumps(vars(args), default=str, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({"output_dir": str(output_dir), "summary": summary}, indent=2, sort_keys=True))
    return 0 if final_verify.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
