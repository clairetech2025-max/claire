from __future__ import annotations

import os
import time
from pathlib import Path

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde.collectors import JsonlEvidenceCollector, NotConfiguredCollector
from claire_vde.federal_register import FederalRegisterCollector, FederalRegisterCollectorConfig
from claire_vde.pipeline import VentureDiscoveryEngine
from claire_vde.storage import VentureRepository


def run_once() -> dict:
    """
    Background-worker entrypoint.

    Local-first mode supports normalized JSONL files. Source-specific network
    collectors intentionally fail closed until credentials and adapters are
    configured.
    """

    store = AREStore(AREConfig.from_env())
    repo = VentureRepository()
    engine = VentureDiscoveryEngine(store, repository=repo)
    collector_name = os.environ.get("CLAIRE_VDE_COLLECTOR", "sec")
    jsonl_path = os.environ.get("CLAIRE_VDE_JSONL_SOURCE")
    try:
        if collector_name == "federal_register":
            config = FederalRegisterCollectorConfig(
                query=os.environ.get("CLAIRE_VDE_FR_QUERY", FederalRegisterCollectorConfig().query),
                cutoff_date=os.environ.get("CLAIRE_VDE_FR_CUTOFF", FederalRegisterCollectorConfig().cutoff_date),
                max_pages=int(os.environ.get("CLAIRE_VDE_FR_MAX_PAGES", "1")),
            )
            collector = FederalRegisterCollector(repository=repo, config=config, cursor=repo.get_collector_cursor("federal_register"))
            return engine.ingest_collector(collector)
        if jsonl_path:
            cursor = repo.get_collector_cursor(collector_name)
            collector = JsonlEvidenceCollector(collector_name, Path(jsonl_path), cursor=cursor)
        else:
            collector = NotConfiguredCollector(collector_name)
        return engine.ingest_collector(collector)
    finally:
        store.stop()


def main() -> None:
    interval = float(os.environ.get("CLAIRE_VDE_WORKER_INTERVAL_SECONDS", "0"))
    while True:
        result = run_once()
        print(result, flush=True)
        if interval <= 0:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
