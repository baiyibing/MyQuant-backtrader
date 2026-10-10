# -*- coding: utf-8 -*-
"""6.55：give 5%+4%×档；6.54 仍是 5%+3%×档。"""

from __future__ import annotations

import pytest

from backtest.research.cash_div_events import bind_book_cash_div_economics
from backtest.research.csv_simulate_loop import extra_load_codes_for_strategy
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_54_rules import (
    GIVE_STEP as GIVE_STEP_654,
    exit_line as exit_line_654,
    take_profit_reason as take_profit_654,
)
from backtest.research.strategy6_55_rules import (
    DIV_TO_PARKING,
    GIVE_STEP,
    PARKING_SYMBOL,
    exit_line,
    take_profit_reason,
)


def test_give_step_is_four_percent_and_654_stays_three():
    assert GIVE_STEP == pytest.approx(0.04)
    assert GIVE_STEP_654 == pytest.approx(0.03)
    cost, peak = 10.0, 15.0
    assert exit_line_654(cost, peak) == pytest.approx(11.5)
    assert exit_line(cost, peak) == pytest.approx(10.5)
    px = 11.2
    assert take_profit_654(px, cost, peak, 2)
    assert take_profit_reason(px, cost, peak, 2) is None


def test_hooks_and_scope():
    assert DIV_TO_PARKING is True
    hooks55 = apply_csv_strategy("version6_55")
    hooks54 = apply_csv_strategy("version6_54")
    assert hooks55["name"] == "version6_55"
    assert hooks55["div_to_parking"] is True
    assert hooks55["index_cut"] is True
    assert hooks54["div_to_parking"] is True
    assert extra_load_codes_for_strategy("version6_55") == {PARKING_SYMBOL}
    stats = {}
    hooks55["record_params"](type("S", (), {"stats": stats})())
    assert stats["sell_book"] == "v6_55"
    assert stats["ladder_give_step"] == pytest.approx(0.04)
    assert stats["div_to_parking"] is True
    assert hooks55["take_profit"](11.2, 10.0, 15.0, 2) is None
    assert hooks54["take_profit"](11.2, 10.0, 15.0, 2)
    assert "5%+4%" in __import__(
        "backtest.research.strategy6_55_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "已归档" in __import__(
        "backtest.research.strategy6_55_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "version6_55" in __import__(
        "backtest.research.strategy6_54_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK


def test_product_bind_includes_655(monkeypatch):
    from backtest.research import cash_div_events

    monkeypatch.setattr(
        cash_div_events, "load_cash_div_lookup", lambda *a, **k: {"ok": True}
    )
    assert bind_book_cash_div_economics("6.55", "20251023", "20260909", None) == {
        "ok": True
    }
    assert bind_book_cash_div_economics("version6_54", "20251023", "20260909", None) == {
        "ok": True
    }
    assert bind_book_cash_div_economics("version6_53", "20251023", "20260909", None) is None
    assert bind_book_cash_div_economics("version6_55", "20251023", "20260909", {"keep": 1}) == {
        "keep": 1
    }
