from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AREConfig:
    root: Path
    hmac_key: bytes
    max_segment_records: int = 1000
    recall_scan_limit: int = 500

    @classmethod
    def from_env(cls) -> "AREConfig":
        root = Path(os.environ.get("CLAIRE_ARE_ROOT", "data/claire_are")).resolve()
        key = os.environ.get("CLAIRE_ARE_HMAC_KEY", "local-dev-claire-are-key")
        max_segment_records = int(os.environ.get("CLAIRE_ARE_MAX_SEGMENT_RECORDS", "1000"))
        recall_scan_limit = int(os.environ.get("CLAIRE_ARE_RECALL_SCAN_LIMIT", "500"))
        return cls(
            root=root,
            hmac_key=key.encode("utf-8"),
            max_segment_records=max(1, max_segment_records),
            recall_scan_limit=max(1, recall_scan_limit),
        )
