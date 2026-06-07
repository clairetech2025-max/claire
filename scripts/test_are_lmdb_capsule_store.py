from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from are_lmdb_capsule_store import LMDBCapsuleStore


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="claire_are_lmdb_"))
    try:
        store = LMDBCapsuleStore(db_path=root, map_size=32 * 1024 * 1024, capacity=1000)
        result = store.store_capsule(
            key="capsule:one",
            payload="CLAIRE core thesis: orient before generate.",
            lane="architecture",
            source="test",
            tags=["claire", "are"],
            trust_level="verified",
        )
        assert result["stored"] is True

        recalled = store.recall_capsule("capsule:one", required_lane="architecture")
        assert recalled and recalled["allowed"] is True
        assert recalled["payload"] == "CLAIRE core thesis: orient before generate."
        assert recalled["metadata"]["lane"] == "architecture"

        mismatch = store.recall_capsule("capsule:one", required_lane="legal")
        assert mismatch and mismatch["allowed"] is False
        assert mismatch["reason"] == "lane_mismatch"

        assert store.recall_capsule("missing") is None
        store.close()

        restarted = LMDBCapsuleStore(db_path=root, map_size=32 * 1024 * 1024, capacity=1000)
        recalled_after_restart = restarted.recall_capsule("capsule:one")
        assert recalled_after_restart and recalled_after_restart["allowed"] is True

        with restarted.env.begin(write=True, db=restarted.capsules_db) as txn:
            raw = txn.get(b"capsule:one")
            capsule = json.loads(raw.decode("utf-8"))
            capsule["payload"] = "tampered payload"
            txn.put(b"capsule:one", json.dumps(capsule).encode("utf-8"))

        tampered = restarted.recall_capsule("capsule:one")
        assert tampered and tampered["allowed"] is False
        assert tampered["reason"] == "hash_verification_failed"
        restarted.close()

        print("ARE LMDB capsule store checks passed.")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
