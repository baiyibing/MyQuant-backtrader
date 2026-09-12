from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from backtest.research import strategy1_rules as rules


def test_contract_and_signature():
    assert rules.BOOK_TAG == "v1"
    assert rules.ALLOW_ADD is False
    assert rules.PEAK_GAP_MIN == 0
    assert rules.STOP_PCT == pytest.approx(0.02)
    assert len(inspect.signature(rules.take_profit_reason).parameters) == 4


def test_profit_drawdown_gate_and_threshold():
    assert rules.take_profit_reason(10.5, 10.0, 11.0, 1) == "profit_take:drawdown:50"
    assert rules.take_profit_reason(10.51, 10.0, 11.0, 1) is None
    assert rules.take_profit_reason(9.9, 10.0, 11.0, 1) is None
    assert rules.take_profit_reason(10.0, 10.0, 10.0, 1) is None


def test_record_params():
    st = SimpleNamespace(stats={})
    rules.record_strategy1_params(st, stop_pct=0.03)
    assert st.stats == {
        "sell_book": "v1",
        "stop_pct": 0.03,
        "profit_drawdown_pct": 0.50,
    }
