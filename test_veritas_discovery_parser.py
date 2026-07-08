import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import veritas_discovery_parser as parser


class VeritasDiscoveryParserTests(unittest.TestCase):
    def patch_paths(self, root: Path):
        old = (
            parser.ROOT_DIR,
            parser.OUT_DIR,
            parser.MEM_FILE,
            parser.LOG_FILE,
            parser.DISCOVERY_REPORT_FILE,
            parser.TMP_ZIP_DIR,
        )
        parser.ROOT_DIR = root
        parser.OUT_DIR = root / "veritas_discovery_data"
        parser.MEM_FILE = parser.OUT_DIR / "veritas_mem.jsonl"
        parser.LOG_FILE = parser.OUT_DIR / "parser_log.txt"
        parser.DISCOVERY_REPORT_FILE = parser.OUT_DIR / "discovery_report.json"
        parser.TMP_ZIP_DIR = parser.OUT_DIR / "tmp_zip"
        return old

    def restore_paths(self, old):
        (
            parser.ROOT_DIR,
            parser.OUT_DIR,
            parser.MEM_FILE,
            parser.LOG_FILE,
            parser.DISCOVERY_REPORT_FILE,
            parser.TMP_ZIP_DIR,
        ) = old

    def test_redacts_secret_before_memory_write(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            old = self.patch_paths(root)
            try:
                source = root / "notes"
                source.mkdir()
                (source / "strategy.md").write_text(
                    "momentum note\napi_key = ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n",
                    encoding="utf-8",
                )
                report = parser.ingest_path(source)
                self.assertEqual(report["stats"]["chunks_written"], 1)
                memory = parser.MEM_FILE.read_text(encoding="utf-8")
                self.assertIn(parser.REDACTION, memory)
                self.assertNotIn("ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", memory)
            finally:
                self.restore_paths(old)

    def test_secret_file_is_reported_and_not_ingested(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            old = self.patch_paths(root)
            try:
                source = root / "inbox"
                source.mkdir()
                (source / ".env").write_text("KRAKEN_API_SECRET=should-not-ingest\n", encoding="utf-8")
                report = parser.ingest_path(source)
                self.assertEqual(report["stats"]["secret_files_skipped"], 1)
                self.assertEqual(report["stats"]["chunks_written"], 0)
                self.assertEqual(len(report["secret_risk_files"]), 1)
                self.assertFalse(parser.MEM_FILE.exists() and parser.MEM_FILE.read_text(encoding="utf-8").strip())
            finally:
                self.restore_paths(old)

    def test_unsafe_zip_paths_are_blocked(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            old = self.patch_paths(root)
            try:
                archive = root / "bad.zip"
                with zipfile.ZipFile(archive, "w") as z:
                    z.writestr("../escape.txt", "bad")
                    z.writestr("safe/strategy.txt", "arbitrage spread note")
                report = parser.ingest_path(archive)
                reasons = [row["reason"] for row in report["parse_errors"]]
                self.assertIn("unsafe_zip_path_blocked", reasons)
                self.assertEqual(report["stats"]["chunks_written"], 1)
                self.assertFalse((root / "escape.txt").exists())
            finally:
                self.restore_paths(old)

    def test_financial_exports_are_discovered_not_chunked(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            old = self.patch_paths(root)
            try:
                source = root / "exports"
                source.mkdir()
                (source / "kraken_tradeshistory.csv").write_text(
                    "txid,ordertxid,pair,time,type,ordertype,price,cost,fee,vol\n"
                    "T1,O1,XBTUSD,2024-01-01,buy,market,100,100,0.4,1\n",
                    encoding="utf-8",
                )
                report = parser.ingest_path(source)
                self.assertEqual(len(report["possible_kraken_exports"]), 1)
                self.assertEqual(report["stats"]["financial_exports_skipped"], 1)
                self.assertEqual(report["stats"]["chunks_written"], 0)
            finally:
                self.restore_paths(old)

    def test_discover_categorizes_coinbase_and_bot_notes(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            old = self.patch_paths(root)
            try:
                source = root / "pile"
                source.mkdir()
                (source / "coinbase_fills.csv").write_text(
                    "trade id,order id,product,side,size,price,fee\n1,2,BTC-USD,BUY,0.1,100,0.1\n",
                    encoding="utf-8",
                )
                (source / "veritas_strategy_notes.md").write_text("spread arbitrage strategy note", encoding="utf-8")
                report = parser.discover_path(source)
                self.assertEqual(len(report["possible_coinbase_exports"]), 1)
                self.assertEqual(len(report["possible_bot_logs"]), 1)
                self.assertEqual(len(report["possible_strategy_notes"]), 1)
                saved = json.loads(parser.DISCOVERY_REPORT_FILE.read_text(encoding="utf-8"))
                self.assertEqual(saved["schema"], "veritas_discovery_report_v1")
            finally:
                self.restore_paths(old)


if __name__ == "__main__":
    unittest.main()
