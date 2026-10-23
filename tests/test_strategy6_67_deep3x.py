# -*- coding: utf-8 -*-
"""6.67：6.65 栈 + 深档三倍（≥+115% 延续档 42→126 万）。"""

from __future__ import annotations

import pytest

from backtest.research.csv_ledger import execute_buy, s8_policy
from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
from backtest.research.csv_strategy_books import apply_csv_strategy

CODE = "600000.SH"
BUDGET = 10_000.0


def _state(book="version6_67", cash=5_000_000.0):  # 深档 126 万需充足现金
    hooks = apply_csv_strategy(book, name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})[0]
    assert execute_buy(st, CODE, 10.0, 2_000.0, 0, "2025-11-03")
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


def _tranches(st, ds):
    return [
        t for t in st.trades
        if t["side"] == "BUY" and t["reason"] == "add:tranche" and t["date"] == ds
    ]


def test_hooks_deep3x_schedule():
    hooks = apply_csv_strategy("version6_67", name_budget=BUDGET)
    sched = hooks["add_schedule"]
    assert sched[:2] == [(0.10, 0.30), (0.20, 0.50)]
    assert sched[2] == (0.35, 42.0)
    assert [s for s in sched if s[0] < 1.0][-1] == (0.95, 42.0)
    assert [s for s in sched if s[0] >= 1.0][0] == (1.15, 126.0)
    assert [s for s in sched if s[0] >= 1.0][1] == (1.35, 126.0)
    assert len(sched) == 52 and sched[-1][0] == 10.15
    assert hooks["cont_from_rise"] == 0.35
    assert hooks["div_to_parking"] is True
    sibling = apply_csv_strategy("version6_65")
    assert [s for s in sibling["add_schedule"] if s[0] >= 1.0][0] == (1.15, 42.0)


def test_deep_rung_fills_triple_notional():
    st, hooks = _state()
    group = next(iter(s8_policy(st)["groups"].values()))
    for i, px in enumerate((11.0, 12.0, 13.5), start=1):  # +10/+20/+35 浅档
        _add(st, hooks, i, f"2025-11-0{i+3}", f"2025110{i+3}", px)
    assert group.executed_steps == 3  # 三个 schedule 档（0.10/0.20/0.35）
    # 每日一档顺序追赶：0.55 → 0.75 → 0.95 → 1.15（首个深档）
    for i, px in enumerate((15.5, 17.5, 19.5), start=4):
        _add(st, hooks, i, f"2025-11-{i+6}", f"202511{i+6}", px)
        assert group.executed_steps == i
    _add(st, hooks, 7, "2025-11-14", "20251114", 21.5)  # +115% 深档
    (fill,) = _tranches(st, "20251114")
    assert fill["shares"] == int(BUDGET * 126.0 / 21.5 / 100) * 100  # 三倍档
    assert group.executed_steps == 7


def test_records_deep_rung_stats():
    st, _hooks = _state()
    assert st.stats["sell_book"] == "v6_67"
    assert st.stats["add_schedule_head"][2] == [0.35, 42.0]
    assert st.stats["deep_rung_mult"] == 3.0
    assert st.stats["deep_rung_from_rise"] == 1.0
