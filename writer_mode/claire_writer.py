#!/usr/bin/env python3
"""Claire Writer Mode.

Append-only local writing workspace for transcripts, drafts, briefs, and PDFs.
This module is intentionally isolated from the Claire runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STORY_INDEX = ROOT / "story_index.json"
WRITER_CONFIG = ROOT / "writer_config.json"
LOG_FILE = ROOT / "logs" / "writer_log.jsonl"

FOLDERS = [
    "inbox",
    "transcripts",
    "drafts",
    "pdfs",
    "chapters",
    "briefs",
    "prompts",
    "approved",
    "rejected",
    "logs",
    "templates",
    "indexes",
]

DEFAULT_LANES = [
    "horses",
    "seahorse_business",
    "state_parks_conflict",
    "network_engineer_foundation",
    "t1_lines_osi_packets",
    "linux_kali_termux_origin",
    "claire_origin",
    "shipping_container_build",
    "are_gyro_diode_sentinel",
    "lycanthrope_trailink_recognition_rail",
    "gauss_geomagnetic_navigation",
    "claire_code_academy",
    "openai_partner_pitch",
    "air_force_partner_pitch",
    "gumroad_indie_hackers_marketing",
]

STYLE_RULES = [
    "Do not invent facts.",
    "Do not add people, dates, places, or events unless present in source material.",
    "Preserve Steve's voice: direct, plainspoken, gritty, honest.",
    "Clean grammar without making it sound corporate.",
    "Keep raw transcript separate from edited draft.",
    "Every draft must say \"Draft for human review.\"",
    "Nothing is published, emailed, or uploaded automatically.",
    "PDFs are local files only.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def slugify(value: str, fallback: str = "untitled") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return slug[:80] or fallback


def ensure_folders() -> list[str]:
    created = []
    for name in FOLDERS:
        path = ROOT / name
        if not path.exists():
            path.mkdir(parents=True, exist_ok=False)
            created.append(str(path))
    return created


def default_index() -> dict:
    return {
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "lanes": {lane: {"description": "", "items": []} for lane in DEFAULT_LANES},
    }


def default_config() -> dict:
    return {
        "created_at": utc_now(),
        "writer_mode": os.getenv("CLAIRE_WRITER_MODE", "local_scaffold"),
        "llm_url_env": "CLAIRE_WRITER_LLM_URL",
        "model_env": "CLAIRE_WRITER_MODEL",
        "api_key_env": "CLAIRE_WRITER_API_KEY",
        "default_output": "markdown",
        "style_rules": STYLE_RULES,
    }


def read_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else fallback
    except Exception:
        return fallback


def write_json_new(path: Path, data: dict) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return True


def write_json_replace(path: Path, data: dict) -> None:
    """Update Writer Mode index/config files only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def log_action(action: str, payload: dict | None = None) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": utc_now(), "action": action, "payload": payload or {}}
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def init_writer_mode(_args: argparse.Namespace | None = None) -> int:
    created_folders = ensure_folders()
    index_created = write_json_new(STORY_INDEX, default_index())
    config_created = write_json_new(WRITER_CONFIG, default_config())
    log_action(
        "init",
        {
            "created_folders": created_folders,
            "story_index_created": index_created,
            "writer_config_created": config_created,
        },
    )
    print("Claire Writer Mode initialized.")
    print(f"Root: {ROOT}")
    print(f"Created folders: {len(created_folders)}")
    print(f"story_index.json created: {index_created}")
    print(f"writer_config.json created: {config_created}")
    return 0


def load_index() -> dict:
    init_missing_quiet()
    index = read_json(STORY_INDEX, default_index())
    lanes = index.setdefault("lanes", {})
    changed = False
    for lane in DEFAULT_LANES:
        if lane not in lanes:
            lanes[lane] = {"description": "", "items": []}
            changed = True
        else:
            lanes[lane].setdefault("description", "")
            lanes[lane].setdefault("items", [])
    if changed:
        index["updated_at"] = utc_now()
        write_json_replace(STORY_INDEX, index)
    return index


def init_missing_quiet() -> None:
    ensure_folders()
    write_json_new(STORY_INDEX, default_index())
    write_json_new(WRITER_CONFIG, default_config())


def require_lane(lane: str) -> None:
    if lane not in DEFAULT_LANES:
        raise SystemExit(f"Unknown lane: {lane}\nRun: python writer_mode/claire_writer.py lanes")


def unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        alternate = directory / f"{stem}_{counter}{suffix}"
        if not alternate.exists():
            return alternate
        counter += 1


def append_index_item(lane: str, item: dict) -> None:
    index = load_index()
    lanes = index.setdefault("lanes", {})
    lane_obj = lanes.setdefault(lane, {"description": "", "items": []})
    lane_obj.setdefault("items", []).append(item)
    index["updated_at"] = utc_now()
    write_json_replace(STORY_INDEX, index)


def import_text(args: argparse.Namespace) -> int:
    require_lane(args.lane)
    source = Path(args.file).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"Source file not found: {source}")
    target_name = f"{stamp()}_{args.lane}_{slugify(source.stem)}{source.suffix or '.txt'}"
    target = unique_path(ROOT / "transcripts", target_name)
    shutil.copy2(source, target)
    metadata = {
        "type": "transcript",
        "lane": args.lane,
        "created_at": utc_now(),
        "source_path": str(source),
        "writer_path": str(target.relative_to(ROOT)),
        "bytes": target.stat().st_size,
        "method": "import-text",
    }
    append_index_item(args.lane, metadata)
    log_action("import-text", metadata)
    print(f"Imported transcript: {target}")
    return 0


def capture(args: argparse.Namespace) -> int:
    require_lane(args.lane)
    print("Paste or type text. Finish with ENDCAPTURE on its own line.")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "ENDCAPTURE":
            break
        lines.append(line)
    text = "\n".join(lines).rstrip() + "\n"
    target = unique_path(ROOT / "transcripts", f"{stamp()}_{args.lane}_capture.txt")
    target.write_text(text, encoding="utf-8")
    metadata = {
        "type": "transcript",
        "lane": args.lane,
        "created_at": utc_now(),
        "writer_path": str(target.relative_to(ROOT)),
        "bytes": target.stat().st_size,
        "method": "capture",
    }
    append_index_item(args.lane, metadata)
    log_action("capture", metadata)
    print(f"Captured transcript: {target}")
    return 0


def lane_transcripts(lane: str) -> list[Path]:
    index = load_index()
    items = index.get("lanes", {}).get(lane, {}).get("items", [])
    paths = []
    for item in items:
        if item.get("type") != "transcript":
            continue
        rel = item.get("writer_path")
        if not rel:
            continue
        path = ROOT / rel
        if path.exists() and path.is_file():
            paths.append(path)
    return paths


def read_sources(paths: list[Path], limit_chars: int = 60000) -> str:
    chunks = []
    used = 0
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        remaining = max(0, limit_chars - used)
        if remaining <= 0:
            break
        text = text[:remaining]
        used += len(text)
        chunks.append(f"--- SOURCE: {path.name} ---\n{text.strip()}\n")
    return "\n".join(chunks).strip()


def writer_prompt(kind: str, title: str, lane_or_topic: str, source_text: str) -> str:
    return textwrap.dedent(
        f"""
        You are Claire Writer Mode. Produce markdown only.
        Kind: {kind}
        Title: {title}
        Lane/topic: {lane_or_topic}

        Rules:
        - Do not invent facts.
        - Preserve Steve's direct, plainspoken, gritty, honest voice.
        - Mark uncertain areas as [NEEDS REVIEW].
        - Include "Draft for human review".
        - Do not publish, upload, email, or claim final approval.

        Source material:
        {source_text}
        """
    ).strip()


def call_optional_llm(prompt: str) -> str:
    mode = os.getenv("CLAIRE_WRITER_MODE", "local_scaffold").strip() or "local_scaffold"
    if mode == "local_scaffold":
        return ""
    url = os.getenv("CLAIRE_WRITER_LLM_URL", "").strip()
    if not url:
        print("Claire Writer LLM unavailable. Continuing with local scaffold mode.")
        return ""
    payload = {
        "prompt": prompt,
        "model": os.getenv("CLAIRE_WRITER_MODEL", "").strip(),
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("CLAIRE_WRITER_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
            for key in ("response", "output", "text", "answer", "result"):
                if data.get(key):
                    return str(data[key]).strip()
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                return str(message.get("content") or choices[0].get("text") or "").strip()
        except Exception:
            return raw.strip()
    except (urllib.error.URLError, TimeoutError, Exception):
        print("Claire Writer LLM unavailable. Continuing with local scaffold mode.")
        return ""
    return ""


def markdown_header(title: str, lane: str, doc_type: str) -> str:
    return textwrap.dedent(
        f"""\
        ---
        title: "{title}"
        source_lane: "{lane}"
        document_type: "{doc_type}"
        created_at: "{utc_now()}"
        status: "Draft for human review"
        ---

        # {title}

        **Draft for human review.**
        **Source lane:** {lane}

        """
    )


def scaffold_draft(title: str, lane: str, sources: list[Path], source_text: str) -> str:
    source_notes = "\n".join(f"- {path.name}" for path in sources) or "- No transcripts found."
    excerpt = source_text.strip() if source_text.strip() else "[NEEDS REVIEW] No source transcript material found for this lane."
    return (
        markdown_header(title, lane, "chapter_draft")
        + textwrap.dedent(
            f"""\
            ## Working Opening

            [NEEDS REVIEW] Shape the opening from Steve's own transcript material. Do not add dates, names, places, or events that are not in the sources.

            ## Source Notes

            {source_notes}

            ## Raw Material To Shape

            {excerpt}

            ## Chapter Structure

            1. Where this part of the story starts. [NEEDS REVIEW]
            2. What Steve was learning or fighting through. [NEEDS REVIEW]
            3. What changed because of it. [NEEDS REVIEW]
            4. How this connects to Claire. [NEEDS REVIEW]

            ## Review Checklist

            - Confirm facts, names, places, dates, and sequence.
            - Remove anything that sounds invented or too corporate.
            - Preserve the direct voice.
            - Approve, reject, or revise before PDF export.
            """
        )
    )


def draft(args: argparse.Namespace) -> int:
    require_lane(args.lane)
    sources = lane_transcripts(args.lane)
    source_text = read_sources(sources)
    prompt = writer_prompt("chapter", args.title, args.lane, source_text)
    generated = call_optional_llm(prompt)
    if generated:
        content = markdown_header(args.title, args.lane, "chapter_draft") + generated.strip() + "\n"
        if "Draft for human review" not in content:
            content += "\n\n**Draft for human review.**\n"
    else:
        content = scaffold_draft(args.title, args.lane, sources, source_text)
    target = unique_path(ROOT / "drafts", f"{stamp()}_{slugify(args.title)}.md")
    target.write_text(content, encoding="utf-8")
    metadata = {
        "type": "draft",
        "lane": args.lane,
        "title": args.title,
        "created_at": utc_now(),
        "writer_path": str(target.relative_to(ROOT)),
        "source_count": len(sources),
    }
    append_index_item(args.lane, metadata)
    log_action("draft", metadata)
    print(f"Draft created: {target}")
    return 0


def scaffold_brief(title: str, topic: str) -> str:
    return (
        markdown_header(title, "briefs", "technical_brief")
        + textwrap.dedent(
            f"""\
            ## Plain-English Explanation

            This brief explains {topic} in practical terms for a partner or buyer.

            The purpose is decision support: show what the system does, what problem it reduces, and what evidence or controls make the claim reviewable.

            ## Named Architecture

            - ARE: governed recall support.
            - Gyro: orientation and context stabilization.
            - Diode: controlled trace or lineage boundary.
            - Sentinel: policy validation and escalation.

            ## Partner Value

            - Keeps memory separate from raw model context.
            - Makes important outputs easier to inspect.
            - Supports review before action.
            - Preserves a local artifact for human approval.

            ## Boundaries

            - No confidential source code is included.
            - No patent claim over-disclosure is included.
            - No hype-only claims.
            - No publishing, emailing, or uploading is performed.

            ## Review Notes

            [NEEDS REVIEW] Add only verified examples, approved diagrams, and cleared terminology before external use.
            """
        )
    )


def brief(args: argparse.Namespace) -> int:
    prompt = writer_prompt("technical brief", args.title, args.topic, "")
    generated = call_optional_llm(prompt)
    content = markdown_header(args.title, "briefs", "technical_brief")
    content += generated.strip() + "\n" if generated else scaffold_brief(args.title, args.topic).split("\n\n", 3)[-1]
    if "Draft for human review" not in content:
        content += "\n\n**Draft for human review.**\n"
    target = unique_path(ROOT / "briefs", f"{stamp()}_{slugify(args.title)}.md")
    target.write_text(content, encoding="utf-8")
    metadata = {
        "type": "brief",
        "lane": "briefs",
        "topic": args.topic,
        "title": args.title,
        "created_at": utc_now(),
        "writer_path": str(target.relative_to(ROOT)),
    }
    log_action("brief", metadata)
    print(f"Brief created: {target}")
    return 0


def parse_markdown_meta(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = {"title": path.stem.replace("_", " "), "source_lane": "unknown", "body": text}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            header = parts[1]
            meta["body"] = parts[2].strip()
            for line in header.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"')
                if key in {"title", "source_lane", "created_at"}:
                    meta[key] = value
    title_match = re.search(r"^#\s+(.+)$", meta["body"], flags=re.M)
    if title_match:
        meta["title"] = title_match.group(1).strip()
    return meta


def export_pdf(args: argparse.Namespace) -> int:
    source = Path(args.file).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"Markdown file not found: {source}")
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        print("reportlab is not installed.")
        print("Install with:")
        print("python -m pip install -r writer_mode/requirements_writer_mode.txt")
        return 2

    meta = parse_markdown_meta(source)
    target = unique_path(ROOT / "pdfs", f"{source.stem}.pdf")
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(target), pagesize=letter, title=meta["title"])
    story = [
        Paragraph(str(meta["title"]), styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Date created: {meta.get('created_at', utc_now())}", styles["Normal"]),
        Paragraph(f"Source lane: {meta.get('source_lane', 'unknown')}", styles["Normal"]),
        Spacer(1, 16),
    ]
    body = meta["body"]
    body = re.sub(r"^# .+$", "", body, flags=re.M).strip()
    body += "\n\nGenerated by Claire Writer Mode — Draft for human review"
    for block in re.split(r"\n\s*\n", body):
        clean = block.strip()
        if not clean:
            continue
        clean = clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(clean.replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 8))
    doc.build(story)
    metadata = {
        "type": "pdf",
        "created_at": utc_now(),
        "source_path": str(source),
        "writer_path": str(target.relative_to(ROOT)),
    }
    log_action("pdf", metadata)
    print(f"PDF created: {target}")
    return 0


def status(_args: argparse.Namespace) -> int:
    init_missing_quiet()
    index = load_index()
    transcript_count = 0
    draft_count = len(list((ROOT / "drafts").glob("*.md")))
    brief_count = len(list((ROOT / "briefs").glob("*.md")))
    pdf_count = len(list((ROOT / "pdfs").glob("*.pdf")))
    for lane in index.get("lanes", {}).values():
        for item in lane.get("items", []):
            if item.get("type") == "transcript":
                transcript_count += 1
    print("Claire Writer Mode status")
    print(f"Root: {ROOT}")
    print(f"Mode: {os.getenv('CLAIRE_WRITER_MODE', 'local_scaffold')}")
    print(f"Lanes: {len(index.get('lanes', {}))}")
    print(f"Transcripts indexed: {transcript_count}")
    print(f"Draft files: {draft_count}")
    print(f"Brief files: {brief_count}")
    print(f"PDF files: {pdf_count}")
    return 0


def lanes(_args: argparse.Namespace) -> int:
    index = load_index()
    for lane in index.get("lanes", {}):
        print(lane)
    return 0


def list_files(label: str, directory: Path, suffix: str) -> int:
    init_missing_quiet()
    print(label)
    files = sorted(directory.glob(f"*{suffix}"))
    if not files:
        print("(none)")
        return 0
    for path in files:
        print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claire Writer Mode")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init").set_defaults(func=init_writer_mode)
    sub.add_parser("status").set_defaults(func=status)
    sub.add_parser("lanes").set_defaults(func=lanes)
    sub.add_parser("list-drafts").set_defaults(func=lambda args: list_files("Drafts", ROOT / "drafts", ".md"))
    sub.add_parser("list-pdfs").set_defaults(func=lambda args: list_files("PDFs", ROOT / "pdfs", ".pdf"))

    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--lane", required=True)
    capture_parser.set_defaults(func=capture)

    import_parser = sub.add_parser("import-text")
    import_parser.add_argument("file")
    import_parser.add_argument("--lane", required=True)
    import_parser.set_defaults(func=import_text)

    draft_parser = sub.add_parser("draft")
    draft_parser.add_argument("--lane", required=True)
    draft_parser.add_argument("--title", required=True)
    draft_parser.set_defaults(func=draft)

    brief_parser = sub.add_parser("brief")
    brief_parser.add_argument("--topic", required=True)
    brief_parser.add_argument("--title", required=True)
    brief_parser.set_defaults(func=brief)

    pdf_parser = sub.add_parser("pdf")
    pdf_parser.add_argument("file")
    pdf_parser.set_defaults(func=export_pdf)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\nCapture interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
