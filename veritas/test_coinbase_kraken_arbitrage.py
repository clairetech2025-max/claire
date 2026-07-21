import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import coinbase_kraken_arbitrage as arb


class CoinbaseKrakenArbitrageTests(unittest.TestCase):
    def sample_transport(self, url):
        if "api.kraken.com/0/public/Ticker" in url:
            return {
                "error": [],
                "result": {
                    "XXBTZUSD": {
                        "a": ["100.00", "1", "1"],
                        "b": ["99.00", "1", "1"],
                        "c": ["99.50", "1"],
                        "v": ["10", "20"],
                    }
                },
            }
        if "api.exchange.coinbase.com/products/BTC-USD/ticker" in url:
            return {"ask": "101.00", "bid": "100.50", "price": "100.75", "volume": "1000"}
        raise AssertionError(f"unexpected url: {url}")

    def test_observer_uses_public_market_data_only(self):
        seen = []

        def transport(url):
            seen.append(url)
            return self.sample_transport(url)

        with TemporaryDirectory() as td:
            old_state = arb.STATE_DIR
            old_report = arb.ARBITRAGE_REPORT_FILE
            try:
                arb.STATE_DIR = Path(td)
                arb.ARBITRAGE_REPORT_FILE = Path(td) / "veritas_arbitrage_report.json"
                report = arb.build_arbitrage_report(["BTC/USD"], transport=transport)
            finally:
                arb.STATE_DIR = old_state
                arb.ARBITRAGE_REPORT_FILE = old_report

        self.assertFalse(report["live_execution"])
        self.assertFalse(report["private_keys_required"])
        self.assertFalse(report["order_endpoints_used"])
        self.assertEqual(len(seen), 2)
        self.assertTrue(any("/0/public/Ticker" in url for url in seen))
        self.assertTrue(any("/products/BTC-USD/ticker" in url for url in seen))
        self.assertFalse(any("/private/" in url.lower() for url in seen))
        self.assertFalse(any("orders" in url.lower() for url in seen))

    def test_forbidden_urls_are_rejected(self):
        with self.assertRaises(arb.ArbitrageObserverError):
            arb.assert_public_url("https://api.kraken.com/0/private/AddOrder")
        with self.assertRaises(arb.ArbitrageObserverError):
            arb.assert_public_url("https://api.exchange.coinbase.com/accounts")
        with self.assertRaises(arb.ArbitrageObserverError):
            arb.assert_public_url("https://api.exchange.coinbase.com/orders")

    def test_net_spread_subtracts_fees_and_safety_margin(self):
        buy = {"exchange": "kraken", "ask": 100.0, "bid": 99.0}
        sell = {"exchange": "coinbase", "ask": 101.0, "bid": 101.5}
        direction = arb.estimate_direction("BTC/USD", buy, sell)
        self.assertGreater(direction["gross_spread_pct"], 0)
        self.assertLess(direction["estimated_net_spread_pct"], direction["gross_spread_pct"])


if __name__ == "__main__":
    unittest.main()
