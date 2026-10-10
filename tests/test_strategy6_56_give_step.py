# -*- coding: utf-8 -*-
"""6.56：give 5%+5%×档；6.55 仍是 5%+4%×档。"""

from __future__ import annotations

import pytest

from backtest.research.cash_div_events import bind_book_cash_div_economics
from backtest.research.csv_simulate_loop import extra_load_codes_for_strategy
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_55_rules import (
    GIVE_STEP as GIVE_STEP_655,
    exit_line as exit_line_655,
    take_profit_reason as take_profit_655,
)
from backtest.research.strategy6_56_rules import (
    DIV_TO_PARKING,
    GIVE_STEP,
    PARKING_SYMBOL,
    exit_line,
    take_profit_reason,
)


def test_give_step_is_five_percent_and_655_stays_four():
    assert GIVE_STEP == pytest.approx(0.05)
    assert GIVE_STEP_655 == pytest.approx(0.04)
    cost, peak = 10.0, 15.0
    assert exit_line_655(cost, peak) == pytest.approx(10.5)
    assert exit_line(cost, peak) == pytest.approx(9.5)
    px = 10.2
    assert take_profit_655(px, cost, peak, 2)
    assert take_profit_reason(px, cost, peak, 2) is None


def test_hooks_and_scope():
    assert DIV_TO_PARKING is True
    hooks56 = apply_csv_strategy("version6_56")
    hooks55 = apply_csv_strategy("version6_55")
    assert hooks56["name"] == "version6_56"
    assert hooks56["div_to_parking"] is True
    assert hooks56["index_cut"] is True
    assert extra_load_codes_for_strategy("version6_56") == {PARKING_SYMBOL}
    stats = {}
    hooks56["record_params"](type("S", (), {"stats": stats})())
    assert stats["sell_book"] == "v6_56"
    assert stats["ladder_give_step"] == pytest.approx(0.05)
    assert stats["div_to_parking"] is True
    assert hooks56["take_profit"](10.2, 10.0, 15.0, 2) is None
    assert hooks55["take_profit"](10.2, 10.0, 15.0, 2)
    assert "5%+5%" in __import__(
        "backtest.research.strategy6_56_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "已归档" in __import__(
        "backtest.research.strategy6_56_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "version6_56" in __import__(
        "backtest.research.strategy6_55_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK


def test_product_bind_includes_656(monkeypatch):
    from backtest.research import cash_div_events

    monkeypatch.setattr(
        cash_div_events, "load_cash_div_lookup", lambda *a, **k: {"ok": True}
    )
    assert bind_book_cash_div_economics("6.56", "20251023", "20260909", None) == {
        "ok": True
    }
    assert bind_book_cash_div_economics("version6_55", "20251023", "20260909", None) == {
        "ok": True
    }
    assert bind_book_cash_div_economics("version6_53", "20251023", "20260909", None) is None
