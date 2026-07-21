import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

import veritas_trader_engine as v


def make_engine(tmp_path, mode="paper"):
    db = tmp_path / "ledger.db"
    engine = v.VeritasEngine(db_path=db, mode=mode)
    return engine


def make_actionable_decision(asset="XAUUSD", direction="BUY", qty=1.0, capsule_id="CAP-1"):
    return {
        "decision_id": f"DEC-{time.time_ns()}",
        "capsule_id": capsule_id,
        "timestamp_ns": time.time_ns(),
        "asset": asset,
        "direction": direction,
        "confidence": 1.0,
        "reason": "test",
        "is_actionable": True,
        "strategy_name": v.STRATEGY_NAME,
        "strategy_version": v.STRATEGY_VERSION,
        "parameters_hash": v.STRATEGY_PARAMS_HASH,
        "quantity": qty,
    }


def test_clean_signals_insert_and_hmac_verification(tmp_path):
    ledger = v.AuditLedger(tmp_path / "ledger.db")
    tracer = v.TrailLinkTracer(ledger, b"test-key")
    capsule, _ = tracer.register_raw_signal("test", "GOLD surges")
    tracer.register_clean_signal(capsule, "GOLD surges", 1.0, 1.0)
    assert tracer.verify_signal_provenance(capsule)


def test_modified_payload_fails_hmac(tmp_path):
    ledger = v.AuditLedger(tmp_path / "ledger.db")
    tracer = v.TrailLinkTracer(ledger, b"test-key")
    capsule, _ = tracer.register_raw_signal("test", "GOLD surges")
    tracer.register_clean_signal(capsule, "GOLD surges", 1.0, 1.0)
    with sqlite3.connect(ledger.db_path) as conn:
        conn.execute(
            "UPDATE clean_signals SET sanitized_payload = ? WHERE capsule_id = ?",
            ("GOLD altered", capsule),
        )
        conn.commit()
    assert not tracer.verify_signal_provenance(capsule)


def test_duplicate_capsule_cannot_trade_twice(tmp_path):
    engine = make_engine(tmp_path)
    try:
        decision = make_actionable_decision(capsule_id="CAP-DUP")
        portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
        assert engine.risk_governor.check_order_intent(decision, portfolio)["approved"]
        engine.ledger.register_signal_action("CAP-DUP", "XAUUSD", "BUY")
        assert engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "DUPLICATE_ACTION_REJECTION"
    finally:
        engine.shutdown()


def test_stale_signal_becomes_hold(tmp_path):
    engine = make_engine(tmp_path)
    try:
        old_ns = time.time_ns() - 60_000_000_000
        signal = engine.ingest_signal("test", "GOLD surges", old_ns, block=True)
        decision = engine.signal_engine.evaluate_signal(signal)
        assert decision["direction"] == "HOLD"
        assert decision["is_stale"]
    finally:
        engine.shutdown()


def test_stale_market_price_blocks_order(tmp_path):
    engine = make_engine(tmp_path)
    try:
        engine.current_market_prices["XAUUSD"] = v.market_price_record(
            2000.0, "test", timestamp_ns=time.time_ns() - 60_000_000_000, max_age_ms=10
        )
        decision = make_actionable_decision()
        portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
        assert engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "STALE_MARKET_PRICE_REJECTION"
    finally:
        engine.shutdown()


def test_max_position_blocks_order(tmp_path):
    engine = make_engine(tmp_path)
    try:
        engine.risk_governor.limits["max_position_size"] = 0.5
        decision = make_actionable_decision(qty=1.0)
        portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
        assert engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "EXCEEDED_MAX_POSITION_SIZE"
    finally:
        engine.shutdown()


def test_max_notional_exposure_blocks_order(tmp_path):
    engine = make_engine(tmp_path)
    try:
        engine.risk_governor.limits["max_notional_exposure"] = 100.0
        decision = make_actionable_decision(qty=1.0)
        portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
        assert engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "EXCEEDED_MAX_NOTIONAL_EXPOSURE"
    finally:
        engine.shutdown()


def test_max_daily_loss_blocks_order(tmp_path):
    engine = make_engine(tmp_path)
    try:
        decision = make_actionable_decision()
        portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
        portfolio["daily_loss"] = engine.risk_governor.limits["max_daily_loss"]
        assert engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "EXCEEDED_MAX_DAILY_LOSS_LIMIT"
    finally:
        engine.shutdown()


def test_max_trades_hour_blocks_order(tmp_path):
    engine = make_engine(tmp_path)
    try:
        decision = make_actionable_decision()
        portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
        portfolio["trades_last_hour"] = engine.risk_governor.limits["max_trades_per_hour"]
        assert engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "EXCEEDED_MAX_TRADES_PER_HOUR"
    finally:
        engine.shutdown()


def test_kill_switch_blocks_order(tmp_path, monkeypatch):
    kill_file = tmp_path / "VERITAS_KILL_SWITCH"
    kill_file.write_text("stop", encoding="utf-8")
    monkeypatch.setattr(v, "KILL_SWITCH_FILE", kill_file)
    engine = make_engine(tmp_path)
    try:
        decision = make_actionable_decision()
        portfolio = engine.broker.get_portfolio_state(engine.current_market_prices, 0)
        assert engine.risk_governor.check_order_intent(decision, portfolio)["reason"] == "EMERGENCY_KILL_SWITCH_ACTIVE"
    finally:
        engine.shutdown()


def test_short_selling_rejected(tmp_path):
    engine = make_engine(tmp_path)
    try:
        result = engine.broker.execute_paper_fill("ORD-1", "XAUUSD", "SELL", 1.0, engine.current_market_prices["XAUUSD"])
        assert not result["success"]
        assert result["reason"] == "SHORT_SELLING_DISABLED"
    finally:
        engine.shutdown()


def test_paper_broker_accounting(tmp_path):
    engine = make_engine(tmp_path)
    try:
        buy = engine.broker.execute_paper_fill("ORD-B", "XAUUSD", "BUY", 2.0, v.market_price_record(100.0, "test"))
        assert buy["success"]
        assert engine.broker.positions["XAUUSD"]["qty"] == pytest.approx(2.0)
        sell = engine.broker.execute_paper_fill("ORD-S", "XAUUSD", "SELL", 1.0, v.market_price_record(110.0, "test"))
        assert sell["success"]
        assert engine.broker.positions["XAUUSD"]["qty"] == pytest.approx(1.0)
        assert engine.broker.realized_pnl > 0
    finally:
        engine.shutdown()


def test_live_mode_refuses_missing_env_gates(monkeypatch):
    monkeypatch.setattr(v, "TRADING_MODE", "live")
    monkeypatch.setattr(v, "ENABLE_LIVE_TRADING", False)
    monkeypatch.setattr(v, "LIVE_PASSPHRASE_HASH", "")
    result = v.LiveTradingGate.validate(interactive=False)
    assert not result["approved"]
    assert "VERITAS_ENABLE_LIVE_TRADING" in result["reason"]


def test_live_dry_run_creates_payload_but_sends_nothing(tmp_path):
    ledger = v.AuditLedger(tmp_path / "ledger.db")
    dry = v.LiveBrokerDryRun(ledger)
    result = dry.submit_order(
        {
            "intent_id": "INT-1",
            "asset": "XAUUSD",
            "direction": "BUY",
            "quantity": 1.0,
            "price": 2000.0,
            "idempotency_key": "idem",
        }
    )
    assert result["success"]
    assert result["sent"] is False
    assert dry.sent_payloads


def test_backtest_writes_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = make_engine(tmp_path, mode="backtest")
    try:
        report = engine.run_backtest()
        assert Path(".veritas_backtest_report.json").exists()
        assert "ending_equity" in report
    finally:
        engine.shutdown()


def test_shutdown_drains_are_queue(tmp_path):
    ledger = v.AuditLedger(tmp_path / "ledger.db")
    are = v.AREStore(tmp_path / "are.jsonl", ledger)
    for i in range(10):
        are.ingest(f"CAP-{i}", "payload", {"confidence": 1.0}, "node", time.time_ns(), time.time_ns())
    are.shutdown()
    lines = (tmp_path / "are.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 10
