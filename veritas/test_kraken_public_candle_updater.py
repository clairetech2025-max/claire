import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import kraken_public_candle_updater as updater
import veritas_paper_runtime as runtime


class KrakenPublicCandleUpdaterTests(unittest.TestCase):
    def sample_response(self):
        return {
            "error": [],
            "result": {
                "XXBTZUSD": [
                    [1718841600, "65000.0", "65100.0", "64900.0", "65050.0", "65010.0", "12.5", 100],
                    [1718841900, "65050.0", "65200.0", "65000.0", "65150.0", "65100.0", "14.0", 110],
                ],
                "last": "1718841900",
            },
        }

    def test_public_updater_calls_only_public_ohlc(self):
        urls = []

        def transport(url):
            urls.append(url)
            return self.sample_response()

        with TemporaryDirectory() as td:
            result = updater.update_public_candles("BTC/USD", interval=5, output_dir=Path(td), transport=transport)
            self.assertEqual(result.pair, "XBTUSD")
            self.assertFalse(result.live_execution)
            self.assertEqual(len(urls), 1)
            self.assertIn("/0/public/OHLC", urls[0])
            self.assertNotIn("/private/", urls[0].lower())
            self.assertNotIn("AddOrder", urls[0])
            self.assertTrue(Path(result.output_file).exists())
            with Path(result.output_file).open("r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)

    def test_forbidden_endpoint_markers_are_rejected(self):
        with self.assertRaises(updater.KrakenPublicCandleError):
            updater.assert_public_endpoint("OHLC", "https://api.kraken.com/0/private/AddOrder")
        with self.assertRaises(updater.KrakenPublicCandleError):
            updater.assert_public_endpoint("AddOrder", "https://api.kraken.com/0/public/AddOrder")

    def test_sol_pair_normalizes(self):
        self.assertEqual(updater.normalize_pair("SOL/USD"), "SOLUSD")

    def test_paper_runtime_prefers_fresh_public_candles(self):
        with TemporaryDirectory() as td:
            fresh = Path(td) / "fresh"
            old = Path(td) / "old"
            fresh.mkdir()
            old.mkdir()
            (old / "XBTUSD_1440.csv").write_text("1700000000,1,1,1,1,1,1\n", encoding="utf-8")
            (fresh / "XBTUSD_5.csv").write_text(
                "timestamp,open,high,low,close,vwap,volume,trades,pair,source\n"
                "1800000000,2,2,2,2,2,1,1,XBTUSD,kraken_public_ohlc\n",
                encoding="utf-8",
            )
            candles = runtime.load_candles("BTC/USD", [fresh, old])
            self.assertEqual(candles[-1].timestamp, 1800000000)
            self.assertEqual(candles[-1].source_file, str(fresh / "XBTUSD_5.csv"))


if __name__ == "__main__":
    unittest.main()
