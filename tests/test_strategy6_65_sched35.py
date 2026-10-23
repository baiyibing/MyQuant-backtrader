# -*- coding: utf-8 -*-
"""6.65：6.55 栈 + 延续档前移 +35% 起；单段闸门，其余同 6.55。"""

from __future__ import annotations

from backtest.research.csv_ledger import execute_buy, s8_policy
from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day, run_index_gate_cut_day
from backtest.research.csv_strategy_books import apply_csv_strategy

CODE = "600000.SH"
BUDGET = 10_000.0
RUNG_FRAC = 42.0


def _state(book="version6_65", cash=2_000_000.0):
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


def test_hooks_schedule_and_single_stage_gate():
    hooks = apply_csv_strategy("version6_65")
    sched = hooks["add_schedule"]
    assert sched[:2] == [(0.10, 0.30), (0.20, 0.50)]
    assert sched[2] == (0.35, 42.0)
    assert sched[3] == (0.55, 42.0)
    assert sched[-1][0] == 10.15
    assert hooks["cont_from_rise"] == 0.35
    assert hooks["index_cut"] is True
    assert hooks["index_cut_frac"] == 0.50
    assert hooks.get("index_cut2_blocked_day") is None  # 单段闸门，同 6.55
    assert hooks["div_to_parking"] is True
    sibling = apply_csv_strategy("version6_55")
    assert sibling["add_schedule"][2] == (0.40, 42.0)


def test_cont_rung_fires_at_35():
    st, hooks = _state()
    group = next(iter(s8_policy(st)["groups"].values()))
    for i, px in enumerate((11.0, 12.0, 13.4), start=1):
        _add(st, hooks, i, f"2025-11-0{i+3}", f"2025110{i+3}", px)
    assert group.executed_steps == 2
    _add(st, hooks, 4, "2025-11-10", "20251110", 13.5)
    fills = _tranches(st, "20251110")
    assert len(fills) == 1
    assert fills[0]["shares"] == int(BUDGET * RUNG_FRAC / 13.5 / 100) * 100
    assert group.executed_steps == 3


def test_index_gate_cuts_once_only():
    """单段闸门：连续 blocked 只切一次（无第二段），与 6.55 一致。"""
    import pandas as pd

    st, hooks = _state(cash=2_000_000.0)
    assert execute_buy(st, CODE, 10.0, 2_000.0, 0, "2025-11-03") or True
    bars = {
        CODE: pd.DataFrame(
            {"open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 1_000_000},
            index=pd.to_datetime(["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"]),
        )
    }
    for day, ds in (("2025-11-04", "20251104"), ("2025-11-05", "20251105"), ("2025-11-06", "20251106")):
        hooks["allow_new_name"] = (lambda _d: False)
        run_index_gate_cut_day(
            st, hooks, day_i=int(ds[-2:]) - 3, day=pd.Timestamp(day), ds=ds,
            names={}, daily_bars=bars, qlib_limit_pct=0.50,
        )
    cuts = [t for t in st.trades if t["reason"] == "index_cut"]
    assert len(cuts) == 1
    assert st.stats.get("index_cut2_shares", 0) == 0


def test_records_override_schedule_stats():
    st, _hooks = _state()
    assert st.stats["sell_book"] == "v6_65"
    assert st.stats["add_schedule_head"] == [[0.10, 0.30], [0.20, 0.50], [0.35, 42.0], [0.55, 42.0]]
    assert st.stats["cont_from_rise"] == 0.35
