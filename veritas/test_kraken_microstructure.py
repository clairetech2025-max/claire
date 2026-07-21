import unittest

import kraken_microstructure as km


class KrakenMicrostructureTests(unittest.TestCase):
    def transport(self, url):
        self.urls.append(url)
        if "Ticker" in url:
            return {"error": [], "result": {"XXBTZUSD": {"a": ["101.0", "1", "1"], "b": ["100.0", "1", "1"]}}}
        if "Depth" in url:
            return {
                "error": [],
                "result": {
                    "XXBTZUSD": {
                        "asks": [["101.0", "1.0", "1"], ["102.0", "1.0", "1"]],
                        "bids": [["100.0", "1.0", "1"], ["99.0", "1.0", "1"]],
                    }
                },
            }
        raise AssertionError(url)

    def test_observer_uses_public_ticker_and_depth_only(self):
        self.urls = []
        report = km.observe_pair("BTC/USD", transport=self.transport)
        self.assertFalse(report["live_execution"])
        self.assertEqual(len(self.urls), 2)
        self.assertTrue(any("/0/public/Ticker" in url for url in self.urls))
        self.assertTrue(any("/0/public/Depth" in url for url in self.urls))
        self.assertFalse(any("/private/" in url.lower() or "AddOrder" in url for url in self.urls))
        self.assertIn("estimated_slippage", report)

    def test_forbidden_urls_are_rejected(self):
        with self.assertRaises(km.MicrostructureError):
            km.assert_public_url("Ticker", "https://api.kraken.com/0/private/AddOrder")
        with self.assertRaises(km.MicrostructureError):
            km.assert_public_url("AddOrder", "https://api.kraken.com/0/public/AddOrder")


if __name__ == "__main__":
    unittest.main()
