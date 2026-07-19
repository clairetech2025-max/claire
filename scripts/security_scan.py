from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SECRET_PATTERNS = [
    ("openai_api_key", re.compile(r"\b(?:sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,})\b")),
    ("huggingface_token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b")),
    (
        "azure_connection_string",
        re.compile(r"DefaultEndpointsProtocol=.*?(?:AccountKey|SharedAccessSignature)=", re.I),
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
]

PROHIBITED_PATH_PATTERNS = [
    ("database", re.compile(r"\.(?:db|sqlite|sqlite3)$", re.I)),
    ("private_key_file", re.compile(r"\.(?:pem|key)$", re.I)),
    ("runtime_log", re.compile(r"\.log$", re.I)),
    (
        "private_runtime_data",
        re.compile(r"(^|/)(uploads|evidence|private|matter_data|runtime_logs|indexes)(/|$)", re.I),
    ),
]

TEXT_FILE_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class Finding:
    kind: str
    path: str
    line: int | None = None

    def render(self) -> str:
        if self.line is None:
            return f"{self.kind}: {self.path}"
        return f"{self.kind}: {self.path}:{self.line}"


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [root / line for line in result.stdout.splitlines() if line.strip()]


def is_binary(path: Path) -> bool:
    try:
        return b"\0" in path.read_bytes()[:4096]
    except OSError:
        return True


def scan_file(root: Path, path: Path) -> list[Finding]:
    rel = path.relative_to(root).as_posix()
    findings: list[Finding] = []

    for kind, pattern in PROHIBITED_PATH_PATTERNS:
        if pattern.search(rel):
            findings.append(Finding(kind=kind, path=rel))

    if not path.is_file() or is_binary(path):
        return findings

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    if len(text.encode("utf-8", errors="ignore")) > TEXT_FILE_BYTES:
        return findings

    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(kind=kind, path=rel, line=line_number))
    return findings


def scan_paths(root: Path, paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if path.exists():
            findings.extend(scan_file(root, path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan tracked source for secret-shaped values and prohibited private artifacts."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional repository-relative paths. Defaults to all tracked files.",
    )
    args = parser.parse_args()

    root = Path.cwd().resolve()
    paths = [root / path for path in args.paths] if args.paths else tracked_files(root)
    findings = scan_paths(root, paths)

    if findings:
        for finding in findings:
            print(finding.render(), file=sys.stderr)
        return 1

    print(f"security scan passed: {len(paths)} tracked paths inspected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
