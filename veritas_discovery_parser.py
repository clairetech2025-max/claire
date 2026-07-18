#!/usr/bin/env python3
"""Veritas Discovery Parser.

Discovery only. This tool finds candidate files and creates redacted H&G
breadcrumbs for non-financial notes/evidence. It does not reconstruct trades.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import traceback
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    import docx
except ImportError:  # pragma: no cover - optional dependency
    docx = None

try:
    import PyPDF2
except ImportError:  # pragma: no cover - optional dependency
    PyPDF2 = None

try:
    import pytesseract
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None
    Image = None


PARSER_VERSION = "0.2"
ROOT_DIR = Path(".").resolve()
OUT_DIR = ROOT_DIR / "veritas_discovery_data"
MEM_FILE = OUT_DIR / "veritas_mem.jsonl"
LOG_FILE = OUT_DIR / "parser_log.txt"
DISCOVERY_REPORT_FILE = OUT_DIR / "discovery_report.json"
TMP_ZIP_DIR = OUT_DIR / "tmp_zip"

CHUNK_SIZE_CHARS = 1200
OVERLAP_CHARS = 200
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
MAX_OCR_FILE_SIZE_BYTES = 10 * 1024 * 1024

FINANCIAL_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}
TEXT_EXTENSIONS = {".txt", ".md", ".log", ".py", ".js", ".ts", ".json", ".jsonl", ".yaml", ".yml", ".toml"}
DOC_EXTENSIONS = {".docx", ".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

SECRET_FILE_MARKERS = (
    ".env",
    "api_key",
    "apikey",
    "api-key",
    "secret",
    "token",
    "passphrase",
    "password",
    "passwd",
    "credential",
    "credentials",
    "kraken.key",
    "coinbase",
    "private_key",
    "seed",
    "recovery",
    "wallet",
)

KRAKEN_MARKERS = ("kraken", "tradeshistory", "closedorders", "ledger", "ledgers", "xbt", "xxbt", "zec", "krkn")
COINBASE_MARKERS = ("coinbase", "coinbasepro", "coinbase_pro", "advanced trade", "fills", "portfolio")
BOT_LOG_MARKERS = ("bot", "trader", "tradebot", "veritas", "strategy", "paper", "backtest", "signals")
STRATEGY_MARKERS = ("strategy", "alpha", "edge", "momentum", "mean reversion", "arbitrage", "spread", "signal")

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_ -]?key|api[_ -]?secret|secret|token|bearer|password|passphrase|private[_ -]?key)\b\s*[:=]\s*['\"]?[^'\"\s]{6,}"),
    re.compile(r"(?i)\b(seed phrase|recovery phrase|mnemonic)\b\s*[:=]\s*.+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),
]

REDACTION = "[REDACTED_BY_VERITAS_DISCOVERY]"


def ensure_output_dir() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def log(*args: Any) -> None:
    ensure_output_dir()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] " + " ".join(str(arg) for arg in args)
    print(line)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def sha256_file(path: Path, max_bytes: int = MAX_FILE_SIZE_BYTES) -> str:
    h = hashlib.sha256()
    read = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            read += len(chunk)
            if read > max_bytes:
                h.update(b"[TRUNCATED_FOR_HASH_GUARD]")
                break
            h.update(chunk)
    return h.hexdigest()


def redact_secrets(text: str) -> str:
    safe = text or ""
    for pattern in SECRET_PATTERNS:
        safe = pattern.sub(REDACTION, safe)
    return safe


def contains_secret(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def is_secret_risk_file(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in {".pem", ".key", ".p12", ".pfx", ".kdbx"}:
        return True
    return any(marker in name for marker in SECRET_FILE_MARKERS)


def classify_path(path: Path) -> dict[str, bool]:
    blob = str(path).lower()
    suffix = path.suffix.lower()
    is_financial = suffix in FINANCIAL_EXTENSIONS
    return {
        "possible_kraken_export": is_financial and any(marker in blob for marker in KRAKEN_MARKERS),
        "possible_coinbase_export": is_financial and any(marker in blob for marker in COINBASE_MARKERS),
        "possible_bot_log": any(marker in blob for marker in BOT_LOG_MARKERS) and suffix in TEXT_EXTENSIONS,
        "possible_strategy_note": any(marker in blob for marker in STRATEGY_MARKERS) and suffix in (TEXT_EXTENSIONS | DOC_EXTENSIONS),
        "secret_risk": is_secret_risk_file(path),
    }


def classify_csv_headers(path: Path) -> dict[str, bool]:
    try:
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return {}
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            sample = handle.read(8192)
        lowered = sample.lower()
    except Exception:
        return {}
    kraken_hits = ("txid", "ordertxid", "pair", "fee", "vol", "cost", "margin", "kraken")
    coinbase_hits = ("portfolio", "trade id", "order id", "product", "fill", "coinbase", "side", "size")
    return {
        "possible_kraken_export": sum(token in lowered for token in kraken_hits) >= 3,
        "possible_coinbase_export": sum(token in lowered for token in coinbase_hits) >= 3,
    }


def unsafe_zip_member(name: str) -> bool:
    if not name or name.endswith("/"):
        return True
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        return True
    return ".." in posix.parts or ".." in windows.parts


def iter_zip_files(zip_path: Path, report: dict[str, Any]) -> list[Path]:
    extracted: list[Path] = []
    target_root = TMP_ZIP_DIR / f"{zip_path.stem}_{sha256_text(str(zip_path))[:8]}"
    target_root.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.infolist():
                if unsafe_zip_member(member.filename):
                    report["parse_errors"].append(
                        {"path": str(zip_path), "member": member.filename, "reason": "unsafe_zip_path_blocked"}
                    )
                    continue
                if member.file_size > MAX_FILE_SIZE_BYTES:
                    report["parse_errors"].append(
                        {"path": str(zip_path), "member": member.filename, "reason": "zip_member_too_large"}
                    )
                    continue
                target = target_root / member.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source, target.open("wb") as dest:
                    dest.write(source.read())
                extracted.append(target)
    except Exception as exc:
        report["parse_errors"].append({"path": str(zip_path), "reason": f"zip_extract_error:{exc}"})
    return extracted


def iter_input_files(root: Path, report: dict[str, Any]) -> list[Path]:
    root = root.resolve()
    if root.is_file():
        if root.suffix.lower() == ".zip":
            return iter_zip_files(root, report)
        return [root]

    files: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() == ".zip":
                files.extend(iter_zip_files(path, report))
            else:
                files.append(path)
    return files


def extract_text(path: Path, report: dict[str, Any]) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        report["parse_errors"].append({"path": str(path), "reason": f"stat_error:{exc}"})
        return ""
    if size > MAX_FILE_SIZE_BYTES:
        report["parse_errors"].append({"path": str(path), "reason": "file_too_large"})
        return ""

    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTENSIONS or ext not in (DOC_EXTENSIONS | IMAGE_EXTENSIONS | FINANCIAL_EXTENSIONS):
            return path.read_text(encoding="utf-8", errors="ignore")
        if ext == ".docx":
            if docx is None:
                report["parse_errors"].append({"path": str(path), "reason": "docx_dependency_missing"})
                return ""
            document = docx.Document(str(path))
            return "\n".join(p.text for p in document.paragraphs)
        if ext == ".pdf":
            if PyPDF2 is None:
                report["parse_errors"].append({"path": str(path), "reason": "pdf_dependency_missing"})
                return ""
            parts: list[str] = []
            with path.open("rb") as handle:
                reader = PyPDF2.PdfReader(handle)
                for page in reader.pages:
                    parts.append(page.extract_text() or "")
            return "\n".join(parts)
        if ext in IMAGE_EXTENSIONS:
            if size > MAX_OCR_FILE_SIZE_BYTES:
                report["parse_errors"].append({"path": str(path), "reason": "image_too_large_for_ocr"})
                return ""
            if pytesseract is None or Image is None:
                report["parse_errors"].append({"path": str(path), "reason": "ocr_dependency_missing"})
                return ""
            return pytesseract.image_to_string(Image.open(str(path)))
    except Exception as exc:
        report["parse_errors"].append({"path": str(path), "reason": f"extract_error:{exc}"})
        return ""
    return ""


def chunk_text(text: str, size: int = CHUNK_SIZE_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def make_breadcrumb(path: Path, chunk: str, chunk_index: int, total_chunks: int, source_sha: str) -> dict[str, Any]:
    redacted = redact_secrets(chunk).strip()
    payload_hash = sha256_text(redacted)
    return {
        "ts": int(time.time()),
        "hg_id": f"HnG-{payload_hash[:12]}",
        "source_path": str(path),
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "parser_version": PARSER_VERSION,
        "diode_mode": "redacted_ingest_only",
        "integrity": {
            "payload_sha256": payload_hash,
            "source_sha256": source_sha,
        },
        "text": redacted,
    }


def new_report(root: Path) -> dict[str, Any]:
    return {
        "schema": "veritas_discovery_report_v1",
        "parser_version": PARSER_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root": str(root),
        "possible_kraken_exports": [],
        "possible_coinbase_exports": [],
        "possible_bot_logs": [],
        "possible_strategy_notes": [],
        "secret_risk_files": [],
        "parse_errors": [],
        "stats": {
            "files_seen": 0,
            "files_ingested": 0,
            "chunks_written": 0,
            "financial_exports_skipped": 0,
            "secret_files_skipped": 0,
        },
    }


def add_unique(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    key = (item.get("path"), item.get("source_sha256"))
    if not any((existing.get("path"), existing.get("source_sha256")) == key for existing in items):
        items.append(item)


def inspect_file(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    report["stats"]["files_seen"] += 1
    source_sha = ""
    try:
        source_sha = sha256_file(path)
        size = path.stat().st_size
    except Exception as exc:
        report["parse_errors"].append({"path": str(path), "reason": f"metadata_error:{exc}"})
        size = 0
    classification = classify_path(path)
    if path.suffix.lower() in FINANCIAL_EXTENSIONS:
        header_class = classify_csv_headers(path)
        classification["possible_kraken_export"] = classification["possible_kraken_export"] or header_class.get("possible_kraken_export", False)
        classification["possible_coinbase_export"] = classification["possible_coinbase_export"] or header_class.get("possible_coinbase_export", False)

    item = {
        "path": str(path),
        "name": path.name,
        "size_bytes": size,
        "source_sha256": source_sha,
    }
    if classification["secret_risk"]:
        add_unique(report["secret_risk_files"], {**item, "reason": "secret_risk_filename_or_extension"})
    if classification["possible_kraken_export"]:
        add_unique(report["possible_kraken_exports"], item)
    if classification["possible_coinbase_export"]:
        add_unique(report["possible_coinbase_exports"], item)
    if classification["possible_bot_log"]:
        add_unique(report["possible_bot_logs"], item)
    if classification["possible_strategy_note"]:
        add_unique(report["possible_strategy_notes"], item)
    return classification


def write_report(report: dict[str, Any]) -> None:
    ensure_output_dir()
    DISCOVERY_REPORT_FILE.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def discover_path(root: Path) -> dict[str, Any]:
    ensure_output_dir()
    report = new_report(root)
    for path in iter_input_files(root, report):
        inspect_file(path, report)
    write_report(report)
    return report


def ingest_path(root: Path) -> dict[str, Any]:
    ensure_output_dir()
    report = new_report(root)
    files = iter_input_files(root, report)
    with MEM_FILE.open("a", encoding="utf-8") as output:
        for path in files:
            classification = inspect_file(path, report)
            if classification["secret_risk"]:
                report["stats"]["secret_files_skipped"] += 1
                continue
            if classification["possible_kraken_export"] or classification["possible_coinbase_export"]:
                report["stats"]["financial_exports_skipped"] += 1
                continue
            text = extract_text(path, report)
            if not text.strip():
                continue
            redacted_text = redact_secrets(text)
            if contains_secret(text) and redacted_text == text:
                report["parse_errors"].append({"path": str(path), "reason": "secret_pattern_detected_but_not_redacted"})
                continue
            chunks = chunk_text(redacted_text)
            if not chunks:
                continue
            try:
                source_sha = sha256_file(path)
            except Exception:
                source_sha = sha256_text(str(path))
            for idx, chunk in enumerate(chunks):
                breadcrumb = make_breadcrumb(path, chunk, idx, len(chunks), source_sha)
                output.write(json.dumps(breadcrumb, ensure_ascii=False, sort_keys=True) + "\n")
                report["stats"]["chunks_written"] += 1
            report["stats"]["files_ingested"] += 1
    write_report(report)
    return report


def search_mem(keyword: str, limit: int) -> list[dict[str, Any]]:
    keyword = keyword.strip().lower()
    if not keyword or not MEM_FILE.exists():
        return []
    hits: list[dict[str, Any]] = []
    with MEM_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if keyword in json.dumps(row, ensure_ascii=False).lower():
                hits.append(row)
                if len(hits) >= limit:
                    break
    return hits


def info() -> dict[str, Any]:
    count = 0
    if MEM_FILE.exists():
        with MEM_FILE.open("r", encoding="utf-8") as handle:
            count = sum(1 for _ in handle)
    return {
        "parser": "Veritas Discovery Parser",
        "version": PARSER_VERSION,
        "output_dir": str(OUT_DIR),
        "memory_file": str(MEM_FILE),
        "discovery_report": str(DISCOVERY_REPORT_FILE),
        "chunks": count,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Veritas discovery parser. Discovery only, not trade reconstruction.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("discover", "ingest"):
        p = sub.add_parser(name)
        p.add_argument("path", type=Path)
    search = sub.add_parser("search")
    search.add_argument("keyword")
    search.add_argument("limit", nargs="?", type=int, default=20)
    sub.add_parser("info")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "discover":
            report = discover_path(args.path)
            print(json.dumps(report, indent=2, sort_keys=True))
        elif args.command == "ingest":
            report = ingest_path(args.path)
            print(json.dumps(report, indent=2, sort_keys=True))
        elif args.command == "search":
            hits = search_mem(args.keyword, args.limit)
            print(json.dumps({"matches": hits, "count": len(hits)}, indent=2, sort_keys=True))
        elif args.command == "info":
            print(json.dumps(info(), indent=2, sort_keys=True))
    except Exception as exc:
        traceback.print_exc()
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
