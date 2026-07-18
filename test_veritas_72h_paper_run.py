import unittest
from types import SimpleNamespace
from unittest.mock import patch

import veritas_72h_paper_run as runner


class Veritas72hPaperRunTests(unittest.TestCase):
    def test_runner_cycle_keeps_live_execution_false(self):
        calls = {"update": 0, "observe": 0, "report": 0}

        expected_pairs = runner.CONFIGURED_PAIRS

        def fake_update(pair, interval):
            calls["update"] += 1
            self.assertIn(pair, expected_pairs)
            self.assertEqual(interval, 5)
            return SimpleNamespace(pair=pair.replace("/", ""), rows_written=10)

        def fake_observe(pair):
            calls["observe"] += 1
            self.assertIn(pair, expected_pairs)
            return {
                "pair": pair.replace("/", ""),
                "decision": "WAIT",
                "execution_result": "NO_FILL",
                "observed_price": 100.0,
                "source_file": "public.csv",
                "live_execution": False,
            }

        def fake_report():
            calls["report"] += 1
            return {"decisions": calls["observe"], "scores": 0, "equity_usd": 500.0}

        times = iter([0.0, 0.0, 1.0, 2.0])
        with patch.object(runner, "update_public_candles", side_effect=fake_update), patch.object(
            runner, "observe_once", side_effect=fake_observe
        ), patch.object(runner, "build_report", side_effect=fake_report), patch.object(
            runner.time, "time", side_effect=lambda: next(times)
        ), patch.object(
            runner.time, "sleep", return_value=None
        ):
            result = runner.run_paper_loop(expected_pairs, 5, hours=0.0001, cycle_seconds=0)

        self.assertFalse(result["live_execution"])
        self.assertEqual(calls["update"], 4)
        self.assertEqual(calls["observe"], 4)
        self.assertGreaterEqual(calls["report"], 1)

    def test_runner_raises_if_live_execution_becomes_true(self):
        with patch.object(runner, "update_public_candles", return_value=SimpleNamespace(pair="XBTUSD", rows_written=10)), patch.object(
            runner, "observe_once", return_value={"pair": "XBTUSD", "live_execution": True}
        ), patch.object(runner, "build_report", return_value={"decisions": 1, "scores": 0, "equity_usd": 500.0}), patch.object(
            runner.time, "time", side_effect=[0.0, 0.0, 1.0]
        ), patch.object(
            runner.time, "sleep", return_value=None
        ):
            with self.assertRaises(RuntimeError):
                runner.run_paper_loop(["BTC/USD"], 5, hours=0.0001, cycle_seconds=0)

    def test_runner_continues_when_one_public_candle_update_fails(self):
        calls = {"observe": 0}

        def fake_update(pair, interval):
            if pair == "ETH/USD":
                raise RuntimeError("temporary public OHLC failure")
            return SimpleNamespace(pair=pair.replace("/", ""), rows_written=10)

        def fake_observe(pair):
            calls["observe"] += 1
            return {
                "pair": pair.replace("/", ""),
                "decision": "WAIT",
                "execution_result": "NO_FILL",
                "observed_price": 100.0,
                "source_file": "public.csv",
                "live_execution": False,
            }

        with patch.object(runner, "update_public_candles", side_effect=fake_update), patch.object(
            runner, "observe_once", side_effect=fake_observe
        ), patch.object(runner, "build_report", return_value={"decisions": 2, "scores": 0, "equity_usd": 500.0}), patch.object(
            runner.time, "time", side_effect=[0.0, 0.0, 1.0, 2.0]
        ), patch.object(
            runner.time, "sleep", return_value=None
        ):
            result = runner.run_paper_loop(["BTC/USD", "ETH/USD", "SOL/USD"], 5, hours=0.0001, cycle_seconds=0)

        self.assertFalse(result["live_execution"])
        self.assertEqual(calls["observe"], 2)


if __name__ == "__main__":
    unittest.main()
