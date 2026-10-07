# -*- coding: utf-8 -*-
"""6.48/6.49 入册守卫：能力集、指数闸前缀、峰值触发加仓档只给 6.49。"""

from __future__ import annotations

import pytest

from backtest.research import book_capabilities as caps
from backtest.research import csv_ledger, strategy_book_helpers
from backtest.research.csv_strategy_books import BOOKS, apply_csv_strategy

GATE_BOOKS = ("version6_45", "version6_46", "version6_47", "version6_48", "version6_49")
NO_GATE_BOOKS = ("version6_4", "version6_40", "version6_41", "version6_42",
                 "version6_43", "version6_44")


@pytest.mark.parametrize("name", ["version6_48", "version6_49"])
def test_new_books_are_explicitly_classified(name):
    assert name in BOOKS
    assert name in caps.PRICE_ADD_ELIGIBLE_BOOKS
    assert name in caps.S8_INDEPENDENT_BOOKS
    assert caps.allows_price_add(name, "per_name")
    assert caps.uses_s8_independent(name, "per_name")
    assert not caps.allows_price_add(name, "daily_quota")


@pytest.mark.parametrize("book", NO_GATE_BOOKS)
def test_index_gate_skips_books_below_6_45(book, monkeypatch):
    # The loader must not even be reached for 6.4 / 6.40-6.44.
    from backtest.research import strategy6_45_rules

    monkeypatch.setattr(strategy6_45_rules, "load_sse_ma10_block_new",
                        lambda *a, **k: pytest.fail(f"{book} loaded the 6.45 gate"))
    assert strategy_book_helpers.load_book_index_gate(book, "20240101", "20241231") is None


@pytest.mark.parametrize("book", GATE_BOOKS)
def test_index_gate_covers_6_45_and_later(book, monkeypatch):
    from backtest.research import strategy6_45_rules

    sentinel = {"20240101": True}
    monkeypatch.setattr(strategy6_45_rules, "INDEX_GATE_ON", True)
    monkeypatch.setattr(strategy6_45_rules, "load_sse_ma10_block_new",
                        lambda start, end: sentinel)
    assert strategy_book_helpers.load_book_index_gate(book, "20240101", "20241231") is sentinel


def test_peak_trigger_is_scoped_to_version6_49():
    # topk books fail closed without scores; they carry no add_schedule either.
    hooks = {name: apply_csv_strategy(name)
             for name in BOOKS if not name.startswith("topk_")}
    peak_books = {name for name, h in hooks.items()
                  if h.get("add_schedule_trigger") == "peak"}
    assert peak_books == {"version6_49"}
    scheduled = {name for name, h in hooks.items() if h.get("add_schedule")}
    assert len(scheduled) > 1 and peak_books < scheduled


def test_peak_trigger_reaches_the_s8_policy():
    state = type("S", (), {"book_state": {}})()
    csv_ledger._configure_s8(state, apply_csv_strategy("version6_49"))
    assert csv_ledger.s8_policy(state)["add_schedule_trigger"] == "peak"
    other = type("S", (), {"book_state": {}})()
    csv_ledger._configure_s8(other, apply_csv_strategy("version6_47"))
    assert csv_ledger.s8_policy(other)["add_schedule_trigger"] is None


def test_version6_48_stop_pct_matches_its_help():
    from backtest.research import strategy6_48_rules

    assert strategy6_48_rules.STOP_PCT == 0.10
    assert "止损 10 个点" in strategy6_48_rules.HELP_LOCK
    assert "止损 5 个点" not in strategy6_48_rules.HELP_LOCK
    assert apply_csv_strategy("version6_48")["stop_pct"] == 0.10


def test_version6_49_take_profit_passes_through_the_6_46_chain():
    from backtest.research import strategy6_46_rules, strategy6_49_rules

    hooks = apply_csv_strategy("version6_49")
    # 6.49 的 25% 回吐上限只有在透传不被 6.46 本地 _tp 吞掉时才生效。
    cost, peak = 10.0, 30.0
    px = peak * (1.0 - strategy6_49_rules.GIVE_MAX) + 0.01
    assert strategy6_46_rules.take_profit_reason(px, cost, peak) is None
    assert hooks["take_profit"](px, cost, peak, 2) is None
    px_hit = peak * (1.0 - strategy6_49_rules.GIVE_MAX) - 0.01
    assert strategy6_46_rules.take_profit_reason(px_hit, cost, peak) is None
    assert hooks["take_profit"](px_hit, cost, peak, 2)
