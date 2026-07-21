import base64
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import kraken_trade_importer as kti


class KrakenTradeImporterTests(unittest.TestCase):
    def credentials(self):
        return kti.KrakenCredentials("public-key", base64.b64encode(b"secret").decode("utf-8"), "test")

    def test_dry_run_writes_summary_without_network_call(self):
        calls = []

        def transport(url_path, headers, encoded):
            calls.append((url_path, headers, encoded))
            return {"error": [], "result": {}}

        with TemporaryDirectory() as td:
            importer = kti.KrakenTradeImporter(self.credentials(), Path(td), transport=transport)
            summary = importer.fetch(123, ["TradesHistory"], dry_run=True)
            self.assertTrue(summary.dry_run)
            self.assertEqual(calls, [])
            self.assertTrue(Path(summary.summary_file).exists())
            self.assertFalse(Path(summary.output_file).exists())

    def test_trades_history_paginates_with_offset(self):
        offsets = []

        def transport(url_path, headers, encoded):
            body = dict(pair.split("=", 1) for pair in encoded.decode("utf-8").split("&"))
            offsets.append(int(body["ofs"]))
            if len(offsets) == 1:
                return {
                    "error": [],
                    "result": {
                        "trades": {
                            "T1": {"pair": "XXBTZUSD", "time": "1", "type": "buy", "vol": "0.1", "cost": "10"},
                            "T2": {"pair": "XETHZUSD", "time": "2", "type": "sell", "vol": "1.0", "cost": "20"},
                        }
                    },
                }
            return {"error": [], "result": {"trades": {}}}

        with TemporaryDirectory() as td:
            importer = kti.KrakenTradeImporter(
                self.credentials(),
                Path(td),
                throttle_seconds=0.0,
                transport=transport,
            )
            summary = importer.fetch(123, ["TradesHistory"], dry_run=False)
            self.assertEqual(offsets, [0, 50])
            self.assertEqual(summary.counts["TradesHistory"], 2)
            rows = [json.loads(line) for line in Path(summary.output_file).read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["record_id"] for row in rows], ["T1", "T2"])

    def test_refuses_non_read_only_endpoint(self):
        with TemporaryDirectory() as td:
            importer = kti.KrakenTradeImporter(self.credentials(), Path(td))
            with self.assertRaises(kti.KrakenImporterError):
                importer.fetch(123, ["AddOrder"], dry_run=False)

    def test_redacts_secret_error_text(self):
        self.assertEqual(kti.redact("api secret is abc"), kti.REDACTION)
        self.assertEqual(kti.redact("ordinary rate limit"), "ordinary rate limit")


if __name__ == "__main__":
    unittest.main()
