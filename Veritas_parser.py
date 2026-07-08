#!/usr/bin/env python3
"""
Veritas Parser compatibility wrapper.

This file keeps the old `Veritas_parser.py ingest ...` command working, but it
routes ingestion through the hardened Claire parser and Veritas Legal evidence
engine instead of writing raw whole-file dumps.

Authority model:
- claire_parser produces source-linked parser chunks.
- EvidenceEngine converts those chunks into chronological ARE legal events.
- Governed metadata references matter_id, source_doc_id, source_hash, and ARE sha.
- Search/FAISS remains relevance-only and is not used as evidence authority here.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

from veritas_legal import EvidenceEngine, claire_explains_summary, safe_id

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_ROOT = BASE_DIR / "data" / "veritas_parser"


def load_hardened_parser() -> Any:
    parser_path = BASE_DIR / "claire_parser"
    if not parser_path.exists():
        parser_path = BASE_DIR / "claire_parser.py"
    if not parser_path.exists():
        raise FileNotFoundError("Could not find claire_parser or claire_parser.py")

    loader = importlib.machinery.SourceFileLoader("claire_parser_runtime", str(parser_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"Could not load parser spec from {parser_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def ingest(target_path: Path, matter_id: str, state_root: Path, enable_ocr: bool, enable_media: bool) -> dict[str, Any]:
    target_path = target_path.expanduser().resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {target_path}")

    matter_slug = safe_id(matter_id)
    run_id = f"run_{int(time.time())}"
    run_dir = state_root.expanduser().resolve() / matter_slug / run_id
    parser_output = run_dir / "parser_output.jsonl"
    parser_temp = run_dir / "parser_temp"
    legal_state = run_dir / "legal_state"

    claire_parser = load_hardened_parser()
    parser = claire_parser.ClaireParser(
        output_jsonl=parser_output,
        temp_root=parser_temp,
        enable_ocr=enable_ocr,
        enable_media=enable_media,
    )
    parsed_units = parser.parse_tree(target_path)

    engine = EvidenceEngine(legal_state, matter_id=matter_slug)
    records = engine.ingest_parser_jsonl(parser_output) if parser_output.exists() else []
    summary = engine.summary()
    summary.update(
        {
            "target_path": str(target_path),
            "parser_output": str(parser_output),
            "parser_temp": str(parser_temp),
            "legal_state": str(legal_state),
            "parsed_units": parsed_units,
            "legal_records_created": len(records),
            "parser_first": True,
            "authority_model": "source documents + ARE events are authority; search is relevance only",
        }
    )
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Veritas Legal parser-first ingest wrapper")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest", help="Parse a file/folder/zip and create Veritas Legal ARE-linked records")
    ingest_parser.add_argument("path", help="File, folder, or ZIP to ingest")
    ingest_parser.add_argument("--matter-id", default="matter_default", help="Matter/case identifier")
    ingest_parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT), help="Local state root")
    ingest_parser.add_argument("--disable-ocr", action="store_true", help="Disable OCR for images/image PDFs")
    ingest_parser.add_argument("--disable-media", action="store_true", help="Disable audio/video transcription")
    ingest_parser.add_argument("--claire-explains", action="store_true", help="Print Claire's plain-English legal boundary summary")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.command == "ingest":
        summary = ingest(
            Path(args.path),
            matter_id=args.matter_id,
            state_root=Path(args.state_root),
            enable_ocr=not args.disable_ocr,
            enable_media=not args.disable_media,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        if args.claire_explains:
            print("\n" + claire_explains_summary(summary))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
