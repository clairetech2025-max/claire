from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_ROOT_FILES = {"README.md", "Dockerfile", "app.py"}
DEPENDENCY_ROOT_FILES = {"requirements.txt", "requirements-web.txt", "pyproject.toml"}

PROHIBITED_FILE_PATTERNS = [
    re.compile(r"(^|/)\.git(/|$)"),
    re.compile(r"(^|/)__pycache__(/|$)"),
    re.compile(r"(^|/)\.pytest_cache(/|$)"),
    re.compile(r"\.(db|sqlite|sqlite3|log|gguf|safetensors|pem|key)$", re.I),
    re.compile(r"(^|/)(data|memory|models|uploads|evidence|private|matter_data|runtime_logs|indexes)(/|$)", re.I),
]

SECRET_SHAPED_PATTERNS = [
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def is_binary(path: Path) -> bool:
    try:
        return b"\0" in path.read_bytes()[:4096]
    except OSError:
        return True


def validate_tree(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.exists() or not root.is_dir():
        return [f"missing deployment tree: {root}"]

    root_files = {item.name for item in root.iterdir() if item.is_file()}
    missing = sorted(REQUIRED_ROOT_FILES - root_files)
    if missing:
        errors.append(f"missing root files: {', '.join(missing)}")
    if not root_files.intersection(DEPENDENCY_ROOT_FILES):
        errors.append(
            "missing dependency manifest: expected one of "
            + ", ".join(sorted(DEPENDENCY_ROOT_FILES))
        )

    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if any(pattern.search(rel) for pattern in PROHIBITED_FILE_PATTERNS):
            errors.append(f"prohibited path: {rel}")
            continue
        if path.is_file() and not is_binary(path):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_SHAPED_PATTERNS:
                if pattern.search(text):
                    errors.append(f"secret-shaped value in: {rel}")
                    break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tree", type=Path)
    args = parser.parse_args()
    errors = validate_tree(args.tree)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated Hugging Face tree: {args.tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
