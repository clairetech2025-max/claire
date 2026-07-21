#!/usr/bin/env python3
"""
Read-only Kraken account history importer for Veritas.

This module pulls private Kraken history for analysis only. It does not place
orders, cancel orders, transfer funds, or call any order-capable endpoint.

Required Kraken API permission:
  Orders and trades -> Query closed orders & trades

Recommended permissions for fuller reconciliation:
  Ledger entries -> Query ledger entries
  Funds -> Query funds

Output files contain private account history and must not be committed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


API_BASE = "https://api.kraken.com"
PRIVATE_API_VERSION = "0"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "account_history"
REDACTION = "[REDACTED_BY_VERITAS]"
READ_ONLY_ENDPOINTS = {"TradesHistory", "ClosedOrders", "Ledgers", "Balance"}
PAGED_ENDPOINTS = {"TradesHistory", "ClosedOrders", "Ledgers"}


class KrakenImporterError(RuntimeError):
    pass


@dataclass
class KrakenCredentials:
    api_key: str
    api_secret: str
    source: str


@dataclass
class FetchSummary:
    output_file: str
    summary_file: str
    started_at: str
    completed_at: str
    start_unix: int
    endpoints: list[str]
    counts: dict[str, int]
    pages: dict[str, int]
    dry_run: bool
    throttle_seconds: float


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def two_years_ago_unix(now: float | None = None) -> int:
    return int(now if now is not None else time.time()) - (2 * 365 * 24 * 60 * 60)


def redact(text: Any) -> str:
    value = str(text)
    lowered = value.lower()
    secret_markers = (
        "api-key",
        "api key",
        "api_secret",
        "api secret",
        "password",
        "passphrase",
        "token",
        "signature",
        "authorization",
        "secret",
    )
    if any(marker in lowered for marker in secret_markers):
        return REDACTION
    return value


def load_credentials(key_file: Path | None = None) -> KrakenCredentials:
    env_key = os.environ.get("KRAKEN_API_KEY", "").strip()
    env_secret = os.environ.get("KRAKEN_API_SECRET", "").strip()
    if env_key and env_secret:
        return KrakenCredentials(env_key, env_secret, "environment")

    if key_file:
        lines = [line.strip() for line in key_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) < 2:
            raise KrakenImporterError("Kraken key file must contain API key and secret on separate lines.")
        return KrakenCredentials(lines[0], lines[1], f"file:{key_file}")

    raise KrakenImporterError("Missing Kraken credentials. Set KRAKEN_API_KEY/KRAKEN_API_SECRET or pass --key-file.")


def kraken_signature(api_secret: str, url_path: str, data: dict[str, Any]) -> str:
    encoded = urllib.parse.urlencode(data)
    message = (str(data["nonce"]) + encoded).encode("utf-8")
    sha256_digest = hashlib.sha256(message).digest()
    mac = hmac.new(base64.b64decode(api_secret), url_path.encode("utf-8") + sha256_digest, hashlib.sha512)
    return base64.b64encode(mac.digest()).decode("utf-8")


def query_private(
    credentials: KrakenCredentials,
    endpoint: str,
    payload: dict[str, Any],
    transport: Callable[[str, dict[str, str], bytes], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if endpoint not in READ_ONLY_ENDPOINTS:
        raise KrakenImporterError(f"Endpoint is not approved for read-only import: {endpoint}")

    url_path = f"/{PRIVATE_API_VERSION}/private/{endpoint}"
    data = dict(payload)
    data["nonce"] = int(time.time() * 1000)
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    headers = {
        "API-Key": credentials.api_key,
        "API-Sign": kraken_signature(credentials.api_secret, url_path, data),
        "User-Agent": "VeritasKrakenHistoryImporter/1.0",
    }

    if transport:
        return transport(url_path, headers, encoded)

    request = urllib.request.Request(API_BASE + url_path, data=encoded, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise KrakenImporterError(f"Kraken HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise KrakenImporterError(f"Kraken network error: {redact(exc)}") from exc


class KrakenTradeImporter:
    def __init__(
        self,
        credentials: KrakenCredentials,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        throttle_seconds: float = 3.0,
        page_size: int = 50,
        transport: Callable[[str, dict[str, str], bytes], dict[str, Any]] | None = None,
    ):
        self.credentials = credentials
        self.output_dir = Path(output_dir)
        self.throttle_seconds = float(throttle_seconds)
        self.page_size = int(page_size)
        self.transport = transport

    def _paged_fetch(self, endpoint: str, start_unix: int, writer: Any, max_pages: int | None) -> tuple[int, int]:
        offset = 0
        pages = 0
        count = 0
        while True:
            response = query_private(
                self.credentials,
                endpoint,
                {"ofs": offset, "start": start_unix, "without_count": True},
                transport=self.transport,
            )
            errors = response.get("error") or []
            if errors:
                raise KrakenImporterError(f"Kraken {endpoint} error: {redact(errors)}")

            result = response.get("result") or {}
            records = result.get("trades") or result.get("closed") or result.get("ledger") or {}
            if not records:
                break

            fetched_at = utc_now_iso()
            for record_id, record in records.items():
                writer.write(
                    json.dumps(
                        {
                            "endpoint": endpoint,
                            "record_id": record_id,
                            "fetched_at": fetched_at,
                            "start_unix": start_unix,
                            "record": record,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                count += 1

            pages += 1
            offset += self.page_size
            if max_pages is not None and pages >= max_pages:
                break
            time.sleep(self.throttle_seconds)
        return count, pages

    def _single_fetch(self, endpoint: str, writer: Any) -> tuple[int, int]:
        response = query_private(self.credentials, endpoint, {}, transport=self.transport)
        errors = response.get("error") or []
        if errors:
            raise KrakenImporterError(f"Kraken {endpoint} error: {redact(errors)}")

        result = response.get("result") or {}
        writer.write(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "record_id": "snapshot",
                    "fetched_at": utc_now_iso(),
                    "record": result,
                },
                sort_keys=True,
            )
            + "\n"
        )
        return 1, 1

    def fetch(
        self,
        start_unix: int,
        endpoints: list[str],
        dry_run: bool = True,
        max_pages: int | None = None,
    ) -> FetchSummary:
        bad = sorted(set(endpoints) - READ_ONLY_ENDPOINTS)
        if bad:
            raise KrakenImporterError(f"Refusing non-read-only endpoints: {bad}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"kraken_account_history_{stamp}.jsonl"
        summary_file = self.output_dir / f"kraken_account_history_{stamp}_summary.json"
        started_at = utc_now_iso()

        counts = {endpoint: 0 for endpoint in endpoints}
        pages = {endpoint: 0 for endpoint in endpoints}

        if dry_run:
            completed_at = utc_now_iso()
            summary = FetchSummary(
                output_file=str(output_file),
                summary_file=str(summary_file),
                started_at=started_at,
                completed_at=completed_at,
                start_unix=start_unix,
                endpoints=endpoints,
                counts=counts,
                pages=pages,
                dry_run=True,
                throttle_seconds=self.throttle_seconds,
            )
            summary_file.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True), encoding="utf-8")
            return summary

        with output_file.open("a", encoding="utf-8") as writer:
            for endpoint in endpoints:
                if endpoint in PAGED_ENDPOINTS:
                    count, page_count = self._paged_fetch(endpoint, start_unix, writer, max_pages=max_pages)
                else:
                    count, page_count = self._single_fetch(endpoint, writer)
                counts[endpoint] = count
                pages[endpoint] = page_count

        completed_at = utc_now_iso()
        summary = FetchSummary(
            output_file=str(output_file),
            summary_file=str(summary_file),
            started_at=started_at,
            completed_at=completed_at,
            start_unix=start_unix,
            endpoints=endpoints,
            counts=counts,
            pages=pages,
            dry_run=False,
            throttle_seconds=self.throttle_seconds,
        )
        summary_file.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True), encoding="utf-8")
        return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Kraken account history importer for Veritas.")
    parser.add_argument("--execute", action="store_true", help="Call Kraken and write private account history.")
    parser.add_argument("--key-file", type=Path, help="Optional kraken.key file with API key and secret.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-unix", type=int, default=two_years_ago_unix())
    parser.add_argument("--throttle-seconds", type=float, default=3.0)
    parser.add_argument("--max-pages", type=int, help="Optional cap for test pulls.")
    parser.add_argument(
        "--endpoints",
        nargs="+",
        default=["TradesHistory", "ClosedOrders", "Ledgers", "Balance"],
        choices=sorted(READ_ONLY_ENDPOINTS),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        credentials = load_credentials(args.key_file)
        importer = KrakenTradeImporter(
            credentials=credentials,
            output_dir=args.output_dir,
            throttle_seconds=args.throttle_seconds,
        )
        summary = importer.fetch(
            start_unix=args.start_unix,
            endpoints=args.endpoints,
            dry_run=not args.execute,
            max_pages=args.max_pages,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": redact(exc)}, indent=2, sort_keys=True))
        return 1

    printable = asdict(summary)
    printable["credential_source"] = credentials.source
    printable["credential_values"] = REDACTION
    print(json.dumps({"ok": True, "summary": printable}, indent=2, sort_keys=True))
    if not args.execute:
        print("Dry run only. Add --execute to call Kraken read-only history endpoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
