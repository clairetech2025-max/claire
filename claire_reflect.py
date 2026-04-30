#!/usr/bin/env python3
"""
Claire Reflection Capsules
--------------------------
Captures lived lessons, identity notes, and self-reflection material.

This is not legal authority and not raw fact storage. It is Claire's
operator/identity reflection lane: small durable memories about what matters,
what was learned, and how Claire should carry it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests


BASE_DIR = Path("/home/LuciusPrime/claire")
REFLECTION_VAULT = BASE_DIR / "data" / "reflection_capsules.jsonl"
INGEST_URL = "http://127.0.0.1:8081/sentinel/push"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
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


def build_capsule(text: str, lesson: str, lane: str, weight: str) -> Dict[str, Any]:
    now = time.time()
    capsule_text = (
        "Claire reflection capsule. Use as identity/emotional context, not legal authority.\n"
        f"Lane: {lane}\n"
        f"Weight: {weight}\n"
        f"Moment: {text.strip()}\n"
        f"Lesson: {lesson.strip()}\n\n"
        "Reflection rule:\n"
        "Before I remember, I must understand what kind of remembering this is. "
        "Store the lesson, not the panic. Carry the human meaning without corrupting the record."
    )
    capsule_id = sha(capsule_text)[:16]
    return {
        "id": f"reflection_{capsule_id}",
        "text": capsule_text,
        "source": "claire_reflection",
        "domain": "identity_reflection",
        "doc_type": "reflection_capsule",
        "metadata": {
            "lane": lane,
            "weight": weight,
            "authority": "identity_context",
            "not_legal_authority": True,
            "not_citation_source": True,
            "created_at_unix": now,
        },
    }


def remember(args: argparse.Namespace) -> int:
    text = args.text.strip()
    if not text:
        print("missing reflection text")
        return 1

    lesson = args.lesson.strip() if args.lesson else "Retain the meaning, not the noise."
    record = build_capsule(text=text, lesson=lesson, lane=args.lane, weight=args.weight)
    append_jsonl(REFLECTION_VAULT, record)

    pushed = False
    error = ""
    if not args.no_are:
        try:
            response = requests.post(INGEST_URL, json=record, timeout=15)
            pushed = response.status_code < 400
            if not pushed:
                error = response.text[:300]
        except Exception as exc:
            error = str(exc)

    print(f"capsule_id: {record['id']}")
    print(f"reflection_vault: {REFLECTION_VAULT}")
    print(f"sent_to_sentinel_are: {pushed}")
    if error:
        print(f"send_error: {error}")
    return 0 if pushed or args.no_are else 2


def status(_: argparse.Namespace) -> int:
    records = list(load_jsonl(REFLECTION_VAULT))
    print(f"reflection_capsules: {len(records)}")
    print(f"reflection_vault: {REFLECTION_VAULT}")
    for record in records[-10:]:
        meta = record.get("metadata") or {}
        print(f"- {record.get('id')} lane={meta.get('lane')} weight={meta.get('weight')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claire reflection capsule lane")
    sub = parser.add_subparsers(dest="command", required=True)

    remember_cmd = sub.add_parser("remember", help="Create a reflection capsule")
    remember_cmd.add_argument("text", help="The moment or reflection to retain")
    remember_cmd.add_argument("--lesson", default="", help="What Claire should learn from it")
    remember_cmd.add_argument("--lane", default="operator_identity", help="Memory lane label")
    remember_cmd.add_argument(
        "--weight",
        choices=["low", "medium", "high", "core"],
        default="medium",
        help="Retention weight",
    )
    remember_cmd.add_argument("--no-are", action="store_true", help="Keep only in reflection vault")
    remember_cmd.set_defaults(func=remember)

    status_cmd = sub.add_parser("status", help="Show reflection capsule count")
    status_cmd.set_defaults(func=status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
