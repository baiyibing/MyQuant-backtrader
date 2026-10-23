# -*- coding: utf-8 -*-
"""策略14：大资金宽基书（20 亿 / 底仓 100 万 / +15% 加仓 / 180 天 / 25% 峰撤 / 10% 减仓）。"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.csv_ledger import execute_buy, s8_policy
from backtest.research.csv_minute_backtest import _atr_group_stops  # noqa: F401
from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
from backtest.research.csv_strategy_books import apply_csv_strategy

CODE = "600000.SH"
BUDGET = 10_000.0


def _state(book="version14", cash=3_000_000.0):
    hooks = apply_csv_strategy(book, name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})[0]
    assert execute_buy(st, CODE, 10.0, BUDGET, 0, "2025-11-03")
    return st, hooks


def _add(st, hooks, day_i, day, ds, px):
    run_step_adds_day(
        st,
        day_i=day_i,
        day=day,
        ds=ds,
        names={},
        buy_quote_for=lambda _c: (px, [px]),
        sizing="per_name",
        name_budget=BUDGET,
    )


def test_hooks_carry_v14_spec():
    hooks = apply_csv_strategy("version14", name_budget=BUDGET)
    assert hooks["stop_pct"] == pytest.approx(0.10)
    assert hooks["step_stop_pct"] == pytest.approx(0.10)
    assert hooks["open_frac"] == pytest.approx(1.0)
    sched = hooks["add_schedule"]
    assert sched[:3] == [(0.15, 42.0), (0.35, 42.0), (0.55, 42.0)]
    assert len(sched) == 66 and sched[-1][0] == 13.15
    assert hooks["add_step"] == pytest.approx(99.0)  # 通用步进梯禁用
    assert hooks["give_base"] == pytest.approx(99.0)  # 梯子禁用
    assert hooks["scale_out_step"] == pytest.approx(0.10)
    assert hooks["scale_out_frac"] == pytest.approx(0.10)
    assert hooks["scale_out_anchor"] == "weighted"
    assert hooks["peak_dd_exit"] == pytest.approx(0.25)
    assert hooks["peak_dd_exit2"] == pytest.approx(0.15)
    assert hooks["peak_dd_sessions"] == 1
    assert hooks["peak_dd_min_rise"] == pytest.approx(1.0)
    assert hooks["max_hold_sessions"] == 180
    assert hooks["max_live_add_lots"] == 10
    assert hooks["cont_stop_rebuy"] is False
    assert hooks["div_to_parking"] is True
    assert hooks["parking_frac"] == pytest.approx(0.95)
    assert hooks["parking_buffer"] == pytest.approx(2_000_000.0)
    assert hooks["profit_skim_step"] == pytest.approx(0.10)
    assert hooks["profit_skim_frac"] == pytest.approx(1.0)
    assert hooks["profit_skim_to_parking"] is True
    assert hooks["index_cut"] is True
    assert hooks.get("index_cut2_blocked_day") is None  # 单段闸
    assert hooks.get("atr_stop_anchor") is None
    for sibling in ("version6_55", "version6_65"):
        assert apply_csv_strategy(sibling).get("max_hold_sessions") is None


def test_first_lot_is_full_budget_and_add_at_15pct():
    st, hooks = _state()
    group = next(iter(s8_policy(st)["groups"].values()))
    assert st.trades[0]["notional"] == pytest.approx(BUDGET)  # 底仓=全额预算
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.4)  # +14% 未到 15%
    assert [t for t in st.trades if t["reason"] == "add:tranche"] == []
    _add(st, hooks, 2, "2025-11-05", "20251105", 11.5)  # +15%
    (fill,) = [t for t in st.trades if t["reason"] == "add:tranche"]
    assert fill["shares"] == int(BUDGET * 42 / 11.5 / 100) * 100  # 42 万固定档（百股取整）
    assert group.executed_steps == 1


def test_records_override_stats():
    st, _hooks = _state()
    assert st.stats["sell_book"] == "v14"
    assert st.stats["stop_pct"] == pytest.approx(0.10)
    assert st.stats["ladder_give_base"] == pytest.approx(99.0)
    assert st.stats["max_hold_sessions"] == 180
    assert st.stats["max_live_add_lots"] == 10
    assert st.stats["parking_buffer"] == pytest.approx(2_000_000.0)
    assert st.stats["div_to_parking"] is True
    assert st.stats["peak_dd_min_rise"] == pytest.approx(1.0)
    assert st.stats["peak_dd_exit2"] == pytest.approx(0.15)
