from __future__ import annotations

from typing import Any

import requests


class ClaireAREClient:
    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def ingest(self, *, text: str, lane: str = "general", source: str = "sdk", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._post("/v1/memory/ingest", {"text": text, "lane": lane, "source": source, "metadata": metadata or {}})

    def recall(self, *, query: str, lane: str = "general", limit: int = 8) -> list[dict[str, Any]]:
        return self._post("/v1/memory/recall", {"query": query, "lane": lane, "limit": limit})["memories"]

    def complete(self, *, prompt: str, lane: str = "general", model: str = "local/stub", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._post("/v1/llm/complete", {"prompt": prompt, "lane": lane, "model": model, "metadata": metadata or {}})

    def verify(self) -> dict[str, Any]:
        return self._get("/v1/memory/verify")

    def audit_recent(self, *, limit: int = 25) -> list[dict[str, Any]]:
        return self._get(f"/v1/audit/recent?limit={limit}")["events"]

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _get(self, path: str) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}{path}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()
