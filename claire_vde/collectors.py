from __future__ import annotations

from abc import ABC, abstractmethod
import json
from dataclasses import dataclass, field
from pathlib import Path

from claire_vde.evidence import EvidenceDraft


COLLECTOR_NAMES = [
    "sec_edgar",
    "sec",
    "uspto_patents",
    "google_patents",
    "patents",
    "arxiv",
    "semantic_scholar",
    "pubmed",
    "crunchbase",
    "funding_announcements",
    "acquisitions",
    "venture_news",
    "government_grants",
    "government_contracts",
    "sbir",
    "nsf",
    "nih",
    "job_postings",
    "hiring",
    "github_trends",
    "github",
    "hacker_news",
    "reddit",
    "regulatory_announcements",
    "regulatory_agencies",
    "standards_bodies",
    "earnings_calls",
    "company_blogs",
    "technical_conferences",
    "vc_funding",
    "federal_register",
]


@dataclass(frozen=True)
class CollectorRun:
    collector: str
    evidence: list[EvidenceDraft]
    errors: list[str]
    next_cursor: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    error_details: list[dict[str, object]] = field(default_factory=list)


class EvidenceCollector(ABC):
    """Collectors normalize public source records. They never reason."""

    name: str

    @abstractmethod
    def collect(self) -> CollectorRun:
        raise NotImplementedError


class NotConfiguredCollector(EvidenceCollector):
    """External collector placeholder that fails honestly until configured."""

    def __init__(self, name: str, reason: str = "collector_not_configured") -> None:
        if name not in COLLECTOR_NAMES:
            raise ValueError(f"unknown collector: {name}")
        self.name = name
        self.reason = reason

    def collect(self) -> CollectorRun:
        return CollectorRun(
            collector=self.name,
            evidence=[],
            errors=[self.reason],
            metadata={"status": "not_configured"},
            error_details=[{"code": self.reason, "message": "collector not configured"}],
        )


class StaticEvidenceCollector(EvidenceCollector):
    """Test/demo collector for already-normalized public-source evidence."""

    def __init__(self, name: str, evidence: list[EvidenceDraft]) -> None:
        if name not in COLLECTOR_NAMES and not name.startswith("test_"):
            raise ValueError(f"unknown collector: {name}")
        self.name = name
        self._evidence = list(evidence)

    def collect(self) -> CollectorRun:
        return CollectorRun(
            collector=self.name,
            evidence=list(self._evidence),
            errors=[],
            next_cursor=str(len(self._evidence)),
            metadata={"source": "static"},
        )


class JsonlEvidenceCollector(EvidenceCollector):
    """
    Incremental local collector for normalized public evidence JSONL.

    Each line must contain fields accepted by EvidenceDraft. Network collectors
    should normalize into this shape before admission.
    """

    def __init__(self, name: str, path: str | Path, *, cursor: str | None = None) -> None:
        if name not in COLLECTOR_NAMES and not name.startswith("test_"):
            raise ValueError(f"unknown collector: {name}")
        self.name = name
        self.path = Path(path)
        self.cursor = int(cursor or 0)

    def collect(self) -> CollectorRun:
        if not self.path.exists():
            return CollectorRun(
                collector=self.name,
                evidence=[],
                errors=[f"missing_source_file:{self.path}"],
                next_cursor=str(self.cursor),
                metadata={"source": str(self.path), "mode": "jsonl"},
                error_details=[{"code": "missing_source_file", "path": str(self.path)}],
            )
        evidence: list[EvidenceDraft] = []
        errors: list[str] = []
        next_cursor = self.cursor
        for line_no, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if line_no <= self.cursor:
                continue
            next_cursor = line_no
            if not line.strip():
                continue
            try:
                evidence.append(EvidenceDraft(**json.loads(line)))
            except Exception as exc:
                errors.append(f"line_{line_no}:{exc}")
        return CollectorRun(
            collector=self.name,
            evidence=evidence,
            errors=errors,
            next_cursor=str(next_cursor),
            metadata={"source": str(self.path), "mode": "jsonl"},
            error_details=[{"code": "jsonl_parse_error", "message": err} for err in errors],
        )


def collector_registry() -> dict[str, str]:
    registry = {name: "not_configured" for name in COLLECTOR_NAMES}
    registry["federal_register"] = "implemented"
    return registry
