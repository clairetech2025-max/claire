import json
import os
import unittest
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import veritas_paper_runtime as p
import veritas_trader_engine as engine


class VeritasPaperRuntimeTests(unittest.TestCase):
    def patch_state_paths(self, state_dir):
        old = (p.STATE_DIR, p.ACCOUNT_STATE_FILE, p.DECISIONS_FILE, p.SCORES_FILE, p.REPORT_FILE)
        p.STATE_DIR = state_dir
        p.ACCOUNT_STATE_FILE = state_dir / "paper_account_state.json"
        p.DECISIONS_FILE = state_dir / "paper_decisions.jsonl"
        p.SCORES_FILE = state_dir / "paper_scores.jsonl"
        p.REPORT_FILE = state_dir / "paper_report.json"
        return old

    def restore_state_paths(self, old):
        p.STATE_DIR, p.ACCOUNT_STATE_FILE, p.DECISIONS_FILE, p.SCORES_FILE, p.REPORT_FILE = old

    def test_headerless_candles_load_in_paper_runtime_and_legacy_engine(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "XBTUSD_1440.csv"
            path.write_text(
                "1718841600,65000,66000,64000,65500,10.5,100\n"
                "1718928000,65500,67000,65000,66500,11.5,110\n",
                encoding="utf-8",
            )
            candles = p.load_candles("BTC/USD", [Path(td)])
            self.assertEqual(len(candles), 2)
            self.assertEqual(candles[-1].close, 66500.0)

            legacy = engine.KrakenCandleDataset(path)
            self.assertEqual(len(legacy.candles), 2)
            self.assertEqual(legacy.candles[-1]["pair"], "XBTUSD")

    def test_observe_once_persists_paper_decision_without_live_execution(self):
        with TemporaryDirectory() as td:
            state_dir = Path(td) / "state"
            candle_dir = Path(td) / "candles"
            candle_dir.mkdir()
            rows = []
            base = 1718841600
            price = 65000.0
            for idx in range(40):
                price += 20.0
                rows.append(f"{base + idx * 3600},{price-10},{price+10},{price-20},{price},1.0,{idx}\n")
            (candle_dir / "XBTUSD_60.csv").write_text("".join(rows), encoding="utf-8")

            old_state_dir = p.STATE_DIR
            old_account = p.ACCOUNT_STATE_FILE
            old_decisions = p.DECISIONS_FILE
            old_scores = p.SCORES_FILE
            old_report = p.REPORT_FILE
            old_load_candles = p.load_candles
            try:
                p.STATE_DIR = state_dir
                p.ACCOUNT_STATE_FILE = state_dir / "paper_account_state.json"
                p.DECISIONS_FILE = state_dir / "paper_decisions.jsonl"
                p.SCORES_FILE = state_dir / "paper_scores.jsonl"
                p.REPORT_FILE = state_dir / "paper_report.json"
                p.load_candles = lambda pair, search_paths=None: old_load_candles(pair, [candle_dir])
                record = p.observe_once("BTC/USD")
                self.assertIn(record["decision"], {"BUY", "SELL", "HOLD", "WAIT"})
                self.assertFalse(record["live_execution"])
                self.assertLessEqual(float(record["simulated_position_size"]), 125.0)
                self.assertTrue((state_dir / "paper_account_state.json").exists())
                self.assertTrue((state_dir / "paper_decisions.jsonl").exists())
            finally:
                p.STATE_DIR = old_state_dir
                p.ACCOUNT_STATE_FILE = old_account
                p.DECISIONS_FILE = old_decisions
                p.SCORES_FILE = old_scores
                p.REPORT_FILE = old_report
                p.load_candles = old_load_candles

    def test_readiness_reports_live_not_implemented(self):
        report = p.readiness_report()
        self.assertFalse(report["live_trading_enabled"])
        self.assertEqual(report["live_status"], "live not implemented")
        self.assertEqual(report["paper_account"]["starting_cash_usd"], 500.0)
        self.assertEqual(report["paper_account"]["max_asset_exposure_usd"], 125.0)
        self.assertIn("SOL/USD", report["configured_pairs"])

    def test_trade_and_abstention_scoring_rules(self):
        with TemporaryDirectory() as td:
            state_dir = Path(td)
            old_paths = self.patch_state_paths(state_dir)
            old_load_candles = p.load_candles
            try:
                base = 1_000_000
                candles = [
                    p.Candle(base, 100, 100, 100, 100, 1, 1, "XBTUSD", "test"),
                    p.Candle(base + 3600, 110, 110, 110, 110, 1, 1, "XBTUSD", "test"),
                ]
                p.load_candles = lambda pair, search_paths=None: candles
                decisions = [
                    {"record_id": "BUY-WIN", "pair": "XBTUSD", "decision": "BUY", "observed_ts": base, "observed_price": 100, "confidence": 0.5, "recalled_analogs": []},
                    {"record_id": "SELL-WIN", "pair": "XBTUSD", "decision": "SELL", "observed_ts": base, "observed_price": 120, "confidence": 0.5, "recalled_analogs": []},
                    {"record_id": "WAIT-NOLOSS", "pair": "XBTUSD", "decision": "WAIT", "observed_ts": base, "observed_price": 100, "confidence": 0.5, "recalled_analogs": []},
                    {"record_id": "HOLD-NOLOSS", "pair": "XBTUSD", "decision": "HOLD", "observed_ts": base, "observed_price": 100, "confidence": 0.5, "recalled_analogs": []},
                ]
                # SELL should win because future price 110 is below observed 120.
                p.DECISIONS_FILE.write_text("\n".join(json.dumps(row) for row in decisions) + "\n", encoding="utf-8")
                p.score_decisions()
                scores = [json.loads(line) for line in p.SCORES_FILE.read_text(encoding="utf-8").splitlines()]
                by_id = {row["record_id"]: row for row in scores}
                self.assertTrue(by_id["BUY-WIN"]["win"])
                self.assertTrue(by_id["SELL-WIN"]["win"])
                self.assertIsNone(by_id["WAIT-NOLOSS"]["win"])
                self.assertEqual(by_id["WAIT-NOLOSS"]["score_type"], "abstention")
                self.assertIsNone(by_id["HOLD-NOLOSS"]["win"])
                self.assertEqual(by_id["HOLD-NOLOSS"]["score_type"], "abstention")
            finally:
                p.load_candles = old_load_candles
                self.restore_state_paths(old_paths)

    def test_drawdown_uses_equity_not_cash(self):
        decisions = [
            {"current_cash": 500.0, "portfolio_equity": 500.0},
            {"current_cash": 100.0, "portfolio_equity": 499.0},
            {"current_cash": 100.0, "portfolio_equity": 495.0},
        ]
        self.assertEqual(p.estimate_max_drawdown(decisions), 0.01)

    def test_analog_similarity_does_not_saturate_on_mixed_regimes(self):
        candles = []
        base = 1_000_000
        price = 100.0
        for idx in range(90):
            if idx < 30:
                drift = 0.001
                spread = 0.002
                volume = 100 + idx
            elif idx < 60:
                drift = -0.0015
                spread = 0.006
                volume = 250 - idx
            else:
                drift = 0.004 if idx % 2 == 0 else -0.003
                spread = 0.012
                volume = 400 + (idx % 5) * 40
            open_ = price
            close = price * (1.0 + drift)
            high = max(open_, close) * (1.0 + spread)
            low = min(open_, close) * (1.0 - spread)
            candles.append(p.Candle(base + idx * 300, open_, high, low, close, volume, idx + 1, "XBTUSD", "test"))
            price = close

        analogs = p.analog_recall(candles, window=8)
        self.assertEqual(len(analogs), 3)
        similarities = [analog["similarity"] for analog in analogs]
        self.assertLess(max(similarities), 0.999)
        self.assertGreater(len({round(value, 4) for value in similarities}), 1)
        self.assertTrue(all("distance" in analog for analog in analogs))

    def test_market_truth_gate_blocks_weak_actionable_edge(self):
        gate = p.market_truth_gate("BUY", p.MIN_EXPECTED_EDGE_FRACTION - 0.0001)
        self.assertTrue(gate["blocked"])
        self.assertEqual(gate["required_edge"], round(p.MIN_EXPECTED_EDGE_FRACTION, 8))

    def test_market_truth_gate_allows_strong_actionable_edge(self):
        gate = p.market_truth_gate("SELL", p.MIN_EXPECTED_EDGE_FRACTION + 0.0001)
        self.assertFalse(gate["blocked"])

    def test_duplicate_actionable_decision_does_not_execute_twice(self):
        with TemporaryDirectory() as td:
            state_dir = Path(td) / "state"
            candle_dir = Path(td) / "candles"
            candle_dir.mkdir()
            (candle_dir / "XBTUSD_5.csv").write_text(
                "timestamp,open,high,low,close,vwap,volume,trades,pair,source\n"
                "1800000000,100,101,99,100,100,1,1,XBTUSD,test\n",
                encoding="utf-8",
            )

            old_paths = self.patch_state_paths(state_dir)
            old_load_candles = p.load_candles
            old_decide = p.decide
            try:
                p.load_candles = lambda pair, search_paths=None: old_load_candles(pair, [candle_dir])
                p.decide = lambda pair, candles, state: {
                    "decision": "BUY",
                    "confidence": 0.9,
                    "reason": "forced test buy",
                    "recalled_analogs": [],
                    "risk_notes": [],
                }

                first = p.observe_once("BTC/USD")
                second = p.observe_once("BTC/USD")
                state = p.load_account_state()

                self.assertEqual(first["execution_result"], "PAPER_BUY_FILLED")
                self.assertEqual(second["execution_result"], "DUPLICATE_DECISION_SKIPPED")
                self.assertEqual(len(state["processed_idempotency_keys"]), 1)
                self.assertAlmostEqual(float(state["cash_usd"]), 374.5)
                self.assertAlmostEqual(float(state["positions"]["XBTUSD"]["qty"]), 1.25)
            finally:
                p.load_candles = old_load_candles
                p.decide = old_decide
                self.restore_state_paths(old_paths)

    def test_money_readiness_reports_fee_survivors_and_missed_upside(self):
        decisions = [
            {
                "record_id": "SURVIVES",
                "pair": "XBTUSD",
                "observed_price": 100.0,
                "market_truth_gate": {
                    "pre_gate_decision": "BUY",
                    "blocked": False,
                    "expected_edge": p.MIN_EXPECTED_EDGE_FRACTION + 0.001,
                    "required_edge": p.MIN_EXPECTED_EDGE_FRACTION,
                },
            },
            {
                "record_id": "NEAR",
                "pair": "ETHUSD",
                "observed_price": 50.0,
                "market_truth_gate": {
                    "pre_gate_decision": "BUY",
                    "blocked": True,
                    "expected_edge": p.MIN_EXPECTED_EDGE_FRACTION - 0.0002,
                    "required_edge": p.MIN_EXPECTED_EDGE_FRACTION,
                },
            },
        ]
        scores = [
            {
                "record_id": "WAIT",
                "pair": "ETHUSD",
                "decision": "WAIT",
                "missed_upside": 0.02,
                "avoided_downside": 0.0,
            },
            {
                "record_id": "SURVIVES",
                "pair": "XBTUSD",
                "decision": "BUY",
                "directional_return": 0.03,
            },
        ]

        report = p.money_readiness_report(decisions, scores)

        self.assertEqual(report["fee_surviving_pre_gate_decisions"], 1)
        self.assertEqual(report["fee_blocked_pre_gate_decisions"], 1)
        self.assertEqual(report["top_missed_upside_pairs"][0]["pair"], "ETHUSD")
        self.assertGreater(report["estimated_average_trade_return_after_round_trip_fee"], 0)


if __name__ == "__main__":
    unittest.main()
