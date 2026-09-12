from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from backtest.research import strategy2_rules as rules


def test_contract_and_signature():
    assert rules.BOOK_TAG == "v2"
    assert rules.ALLOW_ADD is False
    assert rules.PEAK_GAP_MIN == 0
    assert rules.STOP_PCT == pytest.approx(0.02)
    assert len(inspect.signature(rules.take_profit_reason).parameters) == 4


def test_t_plus_thresholds_differ_and_missing_key_uses_t5():
    # A 20% profit drawdown is below T+1's 50%, but reaches T+5's 10%.
    assert rules.take_profit_reason(10.8, 10.0, 11.0, 1) is None
    assert rules.take_profit_reason(10.8, 10.0, 11.0, 5) == "profit_take:drawdown:T+5"
    assert rules.take_profit_reason(10.8, 10.0, 11.0, 99) == "profit_take:drawdown:T+99"


def test_buy_day_and_profit_gates():
    assert rules.take_profit_reason(10.0, 10.0, 11.0, 0) is None
    assert rules.take_profit_reason(9.9, 10.0, 11.0, 5) is None
    assert rules.take_profit_reason(10.0, 10.0, 10.0, 5) is None


def test_record_params():
    st = SimpleNamespace(stats={})
    rules.record_strategy2_params(st, stop_pct=0.03)
    assert st.stats["sell_book"] == "v2"
    assert st.stats["stop_pct"] == pytest.approx(0.03)
    assert [st.stats[f"drawdown_t{i}"] for i in range(1, 6)] == [
        0.50,
        0.40,
        0.30,
        0.20,
        0.10,
    ]
