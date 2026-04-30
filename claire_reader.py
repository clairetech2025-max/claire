#!/usr/bin/env python3
"""
Claire Reader
-------------
Reading-ingest lane for literature, essays, and style/depth material.

This intentionally labels records as style/literature so novels can deepen
Claire's voice without becoming legal authority or operational truth.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests

from claire_parser import ClaireParser, ensure_dir, safe_slug


BASE_DIR = Path("/home/LuciusPrime/claire")
DATA_DIR = BASE_DIR / "data"
STYLE_VAULT = DATA_DIR / "reading_style_vault.jsonl"
DEFAULT_PARSED = DATA_DIR / "reader_output.jsonl"
DEFAULT_TEMP = DATA_DIR / "reader_temp"
INGEST_URL = "http://127.0.0.1:8081/parser/push"


def _load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []

    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _style_record(chunk: Dict[str, Any], author: str, collection: str) -> Dict[str, Any]:
    title = chunk.get("title") or Path(chunk.get("source_path", "reading")).stem
    text = str(chunk.get("text") or "").strip()
    source_path = str(chunk.get("source_path") or "")
    chunk_id = chunk.get("chunk_id") or safe_slug(f"{title}_{time.time()}")

    return {
        "id": f"style_{chunk_id}",
        "text": (
            "Claire reading note. Use as style influence only, not factual/legal authority.\n"
            f"Title: {title}\n"
            f"Author: {author or 'unknown'}\n"
            f"Collection: {collection or 'reading'}\n"
            "Retain for: voice, emotional range, prose rhythm, observation, moral texture.\n\n"
            f"{text}"
        ),
        "source": "claire_reader",
        "source_path": source_path,
        "domain": "style",
        "doc_type": "literature",
        "metadata": {
            "lane": "reading_style",
            "authority": "style_only",
            "not_legal_authority": True,
            "not_factual_memory": True,
            "title": title,
            "author": author,
            "collection": collection,
            "source_path": source_path,
            "source_type": chunk.get("source_type"),
            "chunk_id": chunk_id,
            "sha256": chunk.get("sha256"),
            "file_sha256": chunk.get("file_sha256"),
        },
    }


def ingest_records(records: Iterable[Dict[str, Any]], push_are: bool) -> Dict[str, int]:
    kept = 0
    pushed = 0
    failed = 0

    for record in records:
        _append_jsonl(STYLE_VAULT, record)
        kept += 1

        if not push_are:
            continue

        try:
            response = requests.post(INGEST_URL, json=record, timeout=15)
            if response.status_code < 400:
                pushed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return {"kept": kept, "pushed": pushed, "failed": failed}


def read_path(args: argparse.Namespace) -> int:
    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.exists():
        print(f"missing input: {input_path}")
        return 1

    output_path = Path(args.output_jsonl).expanduser().resolve()
    temp_root = Path(args.temp_root).expanduser().resolve()
    if args.clear_output and output_path.exists():
        output_path.unlink()

    parser = ClaireParser(
        output_jsonl=output_path,
        temp_root=temp_root,
        chunk_words=args.chunk_words,
        overlap_words=args.overlap_words,
        enable_ocr=not args.disable_ocr,
        enable_media=not args.disable_media,
    )

    before = output_path.stat().st_size if output_path.exists() else 0
    parsed_units = parser.parse_tree(input_path)
    chunks = list(_load_jsonl(output_path))

    # Only ingest chunks from this run when appending to an existing parser output.
    if before and output_path.exists():
        with output_path.open("r", encoding="utf-8", errors="ignore") as f:
            f.seek(before)
            chunks = [json.loads(line) for line in f if line.strip()]

    style_records = [
        _style_record(chunk, author=args.author, collection=args.collection)
        for chunk in chunks
        if str(chunk.get("text") or "").strip()
    ]
    result = ingest_records(style_records, push_are=not args.no_are)

    print(f"parsed_units: {parsed_units}")
    print(f"style_chunks_retained: {result['kept']}")
    print(f"sent_to_sentinel_are: {result['pushed']}")
    print(f"send_failures: {result['failed']}")
    print(f"style_vault: {STYLE_VAULT}")
    return 0 if result["failed"] == 0 else 2


def status(_: argparse.Namespace) -> int:
    count = 0
    titles = {}
    for record in _load_jsonl(STYLE_VAULT):
        count += 1
        meta = record.get("metadata") or {}
        title = meta.get("title") or "unknown"
        titles[title] = titles.get(title, 0) + 1

    print(f"style_chunks: {count}")
    print(f"style_vault: {STYLE_VAULT}")
    for title, n in sorted(titles.items())[:25]:
        print(f"- {title}: {n}")
    if len(titles) > 25:
        print(f"... {len(titles) - 25} more titles")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claire reading/style ingest lane")
    sub = parser.add_subparsers(dest="command", required=True)

    read = sub.add_parser("read", help="Read a file/folder and retain style chunks")
    read.add_argument("input_path", help="Book, document, or folder to read")
    read.add_argument("--author", default="", help="Author name")
    read.add_argument("--collection", default="literary_depth", help="Collection label")
    read.add_argument("--output-jsonl", default=str(DEFAULT_PARSED))
    read.add_argument("--temp-root", default=str(DEFAULT_TEMP))
    read.add_argument("--chunk-words", type=int, default=260)
    read.add_argument("--overlap-words", type=int, default=35)
    read.add_argument("--disable-ocr", action="store_true")
    read.add_argument("--disable-media", action="store_true")
    read.add_argument("--clear-output", action="store_true")
    read.add_argument("--no-are", action="store_true", help="Retain only in style vault")
    read.set_defaults(func=read_path)

    stat = sub.add_parser("status", help="Show retained reading/style memory")
    stat.set_defaults(func=status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
