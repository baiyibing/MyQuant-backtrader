# -*- coding: utf-8 -*-
from __future__ import annotations

from backtest.legacy.mock_qmt_backtrader_adapter import BacktestMockQmtPipeline, BacktestOrderIntent


def test_backtest_mock_qmt_pipeline_buy_then_sell(monkeypatch):
    monkeypatch.setenv("MOCK_QMT_ENABLED", "true")
    monkeypatch.setenv("MOCK_QMT_BROKER_SYNC_COUNT", "0")
    monkeypatch.setenv("MOCK_QMT_LATENCY_ORDER_QUERY_MS", "0")

    pipeline = BacktestMockQmtPipeline(account_id="bt_mock_001", isolated_manager=True)
    pipeline._trader.seed_position("600999.SH", 100, can_use_volume=100, avg_price=9.0)

    out = pipeline.run_cycle(
        [
            BacktestOrderIntent(action="BUY", stock="600998.SH", volume=100, price=10.0),
            BacktestOrderIntent(action="SELL", stock="600999.SH", volume=100, price=10.5),
        ]
    )
    assert len(out) == 2
    assert out[0]["order_id"] > 0 and out[1]["order_id"] > 0
    assert out[0]["status"] == 56
    assert out[1]["status"] == 56
    assert out[0]["traded_volume"] == 100 and out[1]["traded_volume"] == 100
    assert out[0]["traded_price"] == 10.0
    assert out[1]["traded_price"] == 10.5
