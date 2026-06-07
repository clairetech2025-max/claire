from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import lmdb
from pybloom_live import BloomFilter


class LMDBCapsuleStore:
    """
    Fast deterministic capsule store for CLAIRE ARE.

    This is not the full recall engine. It is a storage backend intended to sit
    after lane classification and recall eligibility.
    """

    def __init__(
        self,
        db_path: str | Path = "are_lmdb",
        map_size: int = 1024 * 1024 * 1024,
        capacity: int = 1_000_000,
        error_rate: float = 0.001,
        rebuild_bloom_on_start: bool = True,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        self.env = lmdb.open(
            str(self.db_path),
            map_size=map_size,
            max_dbs=2,
            lock=True,
            readahead=False,
            meminit=False,
        )

        self.capsules_db = self.env.open_db(b"capsules")
        self.index_db = self.env.open_db(b"index")
        self.bloom = BloomFilter(capacity=capacity, error_rate=error_rate)

        if rebuild_bloom_on_start:
            self._rebuild_bloom()

    def close(self) -> None:
        self.env.close()

    def _hash_payload(self, payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _now(self) -> float:
        return time.time()

    def _rebuild_bloom(self) -> None:
        """
        Rebuild Bloom filter from LMDB keys.

        This avoids the restart bug where capsules exist in LMDB but are
        invisible because the Bloom filter is empty.
        """
        with self.env.begin(db=self.capsules_db) as txn:
            for key, _ in txn.cursor():
                self.bloom.add(key.decode("utf-8"))

    def store_capsule(
        self,
        key: str,
        payload: str,
        lane: str,
        source: str = "unknown",
        tags: list[str] | None = None,
        trust_level: str = "unverified",
    ) -> dict[str, Any]:
        key = str(key or "").strip()
        payload = str(payload or "")
        lane = str(lane or "").strip()
        source = str(source or "unknown").strip() or "unknown"

        if not key:
            raise ValueError("capsule key cannot be empty")
        if not payload.strip():
            raise ValueError("capsule payload cannot be empty")
        if not lane:
            raise ValueError("capsule lane cannot be empty")

        payload_hash = self._hash_payload(payload)
        capsule = {
            "key": key,
            "payload": payload,
            "payload_hash": payload_hash,
            "lane": lane,
            "source": source,
            "tags": tags or [],
            "trust_level": trust_level,
            "created_at": self._now(),
            "version": 1,
        }

        encoded = json.dumps(capsule, ensure_ascii=False, sort_keys=True).encode("utf-8")
        index_record = {
            "lane": lane,
            "source": source,
            "tags": tags or [],
            "trust_level": trust_level,
            "created_at": capsule["created_at"],
            "payload_hash": payload_hash,
        }

        with self.env.begin(write=True) as txn:
            txn.put(key.encode("utf-8"), encoded, db=self.capsules_db)
            txn.put(
                key.encode("utf-8"),
                json.dumps(index_record, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                db=self.index_db,
            )

        self.bloom.add(key)
        return {
            "stored": True,
            "key": key,
            "payload_hash": payload_hash,
            "lane": lane,
        }

    def recall_capsule(self, key: str, required_lane: str | None = None) -> dict[str, Any] | None:
        """
        Exact-key recall with Bloom precheck, hash verification, and optional lane gate.
        """
        key = str(key or "").strip()
        if not key or key not in self.bloom:
            return None

        with self.env.begin(db=self.capsules_db) as txn:
            raw = txn.get(key.encode("utf-8"))

        if raw is None:
            return None

        capsule = json.loads(raw.decode("utf-8"))

        if required_lane and capsule.get("lane") != required_lane:
            return {
                "allowed": False,
                "reason": "lane_mismatch",
                "key": key,
                "capsule_lane": capsule.get("lane"),
                "required_lane": required_lane,
            }

        expected_hash = capsule.get("payload_hash")
        actual_hash = self._hash_payload(capsule.get("payload", ""))

        if expected_hash != actual_hash:
            return {
                "allowed": False,
                "reason": "hash_verification_failed",
                "key": key,
            }

        return {
            "allowed": True,
            "key": key,
            "payload": capsule["payload"],
            "metadata": {
                "lane": capsule["lane"],
                "source": capsule["source"],
                "tags": capsule["tags"],
                "trust_level": capsule["trust_level"],
                "created_at": capsule["created_at"],
                "payload_hash": capsule["payload_hash"],
                "version": capsule["version"],
            },
        }

