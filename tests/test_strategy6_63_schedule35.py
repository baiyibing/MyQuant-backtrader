# -*- coding: utf-8 -*-
"""6.63：延续档前移至 +35% 起（+35%/+55%/…），建仓档 +10%/+20% 不变。"""

from __future__ import annotations

from backtest.research.csv_ledger import execute_buy, s8_policy
from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
from backtest.research.csv_strategy_books import apply_csv_strategy

CODE = "600000.SH"
BUDGET = 10_000.0
RUNG_FRAC = 42.0


def _state(book="version6_63", cash=2_000_000.0):
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


def test_hooks_schedule_shifted_to_35():
    hooks = apply_csv_strategy("version6_63")
    sched = hooks["add_schedule"]
    assert sched[:2] == [(0.10, 0.30), (0.20, 0.50)]
    assert sched[2] == (0.35, 42.0)
    assert sched[3] == (0.55, 42.0)
    assert sched[4] == (0.75, 42.0)
    assert sched[-1][0] == 10.15
    assert hooks["cont_from_rise"] == 0.35
    sibling = apply_csv_strategy("version6_55")
    assert sibling["add_schedule"][2] == (0.40, 42.0)
    assert sibling["cont_from_rise"] == 0.40


def test_cont_rung_fires_at_35_not_at_34():
    st, hooks = _state()
    group = next(iter(s8_policy(st)["groups"].values()))
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)  # +10% 建仓档
    _add(st, hooks, 2, "2025-11-05", "20251105", 12.0)  # +20% 建仓档
    assert group.executed_steps == 2
    _add(st, hooks, 3, "2025-11-06", "20251106", 13.4)  # +34% 未到 +35% 档
    assert _tranches(st, "20251106") == []
    _add(st, hooks, 4, "2025-11-07", "20251107", 13.5)  # +35% 延续档
    fills = _tranches(st, "20251107")
    assert len(fills) == 1
    assert fills[0]["shares"] == int(BUDGET * RUNG_FRAC / 13.5 / 100) * 100
    assert group.executed_steps == 3


def test_second_cont_rung_at_55():
    st, hooks = _state()
    group = next(iter(s8_policy(st)["groups"].values()))
    for i, px in enumerate((11.0, 12.0, 13.5), start=1):
        _add(st, hooks, i, f"2025-11-0{i+3}", f"2025110{i+3}", px)
    assert group.executed_steps == 3
    _add(st, hooks, 4, "2025-11-10", "20251110", 15.4)  # +54% 未到
    assert _tranches(st, "20251110") == []
    _add(st, hooks, 5, "2025-11-11", "20251111", 15.5)  # +55%
    fills = _tranches(st, "20251111")
    assert len(fills) == 1
    assert fills[0]["shares"] == int(BUDGET * RUNG_FRAC / 15.5 / 100) * 100
    assert group.executed_steps == 4


def test_records_override_schedule_stats():
    st, hooks = _state()
    assert st.stats["add_schedule_head"] == [[0.10, 0.30], [0.20, 0.50], [0.35, 42.0], [0.55, 42.0]]
    assert st.stats["cont_from_rise"] == 0.35
