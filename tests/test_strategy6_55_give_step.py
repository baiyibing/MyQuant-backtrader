# -*- coding: utf-8 -*-
"""6.55：give 5%+4%×档；官方 `_industry` 减仓仍是 +5%/5%；6.54 仍是 5%+3%×档。"""

from __future__ import annotations

import pytest

from backtest.research.cash_div_events import bind_book_cash_div_economics
from backtest.research.csv_simulate_loop import extra_load_codes_for_strategy
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_54_rules import (
    GIVE_STEP as GIVE_STEP_654,
    PEAK_DD_EXIT as PEAK_DD_654,
    PROFIT_SKIM_FRAC as SKIM_FRAC_654,
    PROFIT_SKIM_STEP as SKIM_STEP_654,
    SCALE_OUT_FRAC as SCALE_FRAC_654,
    SCALE_OUT_STEP as SCALE_STEP_654,
    exit_line as exit_line_654,
    take_profit_reason as take_profit_654,
)
from backtest.research.strategy6_55_rules import (
    DIV_TO_PARKING,
    GIVE_STEP,
    PARKING_SYMBOL,
    PEAK_DD_EXIT,
    PROFIT_SKIM_FRAC,
    PROFIT_SKIM_STEP,
    SCALE_OUT_FRAC,
    SCALE_OUT_STEP,
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
    assert SCALE_OUT_STEP == SCALE_OUT_FRAC == pytest.approx(0.05)
    assert SCALE_STEP_654 == SCALE_FRAC_654 == pytest.approx(0.05)
    assert PROFIT_SKIM_STEP == PROFIT_SKIM_FRAC == pytest.approx(0.20)
    assert SKIM_STEP_654 == SKIM_FRAC_654 == pytest.approx(0.20)
    assert PEAK_DD_EXIT == PEAK_DD_654 == pytest.approx(0.15)


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
    assert hooks55["scale_out_step"] == hooks55["scale_out_frac"] == pytest.approx(0.05)
    assert hooks54["scale_out_step"] == hooks54["scale_out_frac"] == pytest.approx(0.05)
    assert hooks55["profit_skim_step"] == hooks55["profit_skim_frac"] == pytest.approx(0.20)
    assert hooks54["profit_skim_step"] == hooks54["profit_skim_frac"] == pytest.approx(0.20)
    assert hooks55["peak_dd_exit"] == hooks54["peak_dd_exit"] == pytest.approx(0.15)
    assert hooks55.get("peak_dd_min_rise") in (None, False, 0, 0.0)
    assert hooks55["take_profit"](11.2, 10.0, 15.0, 2) is None
    assert hooks54["take_profit"](11.2, 10.0, 15.0, 2)
    lock55 = __import__(
        "backtest.research.strategy6_55_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "5%+4%" in lock55
    assert "每 +5% 减 5%" in lock55
    assert "每 +10% 减 10%" not in lock55
    assert "_industry" in lock55
    assert "已归档" in lock55
    assert "当前书" not in lock55
    assert "version6_56" not in lock55
    assert "version6_55" in __import__(
        "backtest.research.strategy6_54_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "已归档" in __import__(
        "backtest.research.strategy6_56_rules", fromlist=["HELP_LOCK"]
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


def test_peak_dd_arms_anytime_at_fifteen_percent():
    from backtest.research.csv_ledger import configure_s8, execute_buy, exit_positions
    from backtest.research.csv_simulate_loop import init_sim_state
    from backtest.research.minute_cash_order import peak_dd_clear_exits

    hooks = apply_csv_strategy("version6_55", name_budget=10_000.0)
    assert hooks["peak_dd_exit"] == pytest.approx(0.15)
    assert hooks.get("peak_dd_min_rise") in (None, False, 0, 0.0)
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, "600000.SH", 10.0, 2_000.0, 0, "2025-11-03")
    (pos,) = exit_positions(st, "600000.SH", 2)
    limits = (100.0, 5.0)
    pos.peak = 11.0
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            9.89,
            "2025-11-05",
            2,
            limits,
            peak_dd_exit=hooks["peak_dd_exit"],
            peak_dd_sessions=15,
            peak_dd_min_rise=hooks.get("peak_dd_min_rise") or 0.0,
        )
        == 0
    )
    assert pos.group.peak_dd_start is None
    pos.peak = 12.0
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            10.19,
            "2025-11-05",
            2,
            limits,
            peak_dd_exit=hooks["peak_dd_exit"],
            peak_dd_sessions=15,
            peak_dd_min_rise=hooks.get("peak_dd_min_rise") or 0.0,
        )
        == 0
    )
    assert pos.group.peak_dd_start == 2
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            10.19,
            "2025-11-20",
            17,
            limits,
            peak_dd_exit=hooks["peak_dd_exit"],
            peak_dd_sessions=15,
            peak_dd_min_rise=hooks.get("peak_dd_min_rise") or 0.0,
        )
        == 1
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells
    assert all(t["reason"] == "peak_dd_clear" for t in sells)
    assert not st.positions.get("600000.SH")
