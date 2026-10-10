# -*- coding: utf-8 -*-
"""6.56：建仓档 −10%、延续档 +40% 起 42 万且与试错仓同进同出；6.55 官方减仓仍是 +5%/5%。"""

from __future__ import annotations

import pytest

from backtest.research.csv_ledger import (
    _sell,
    configure_s8,
    execute_buy,
    exit_positions,
    live_cont_count,
)
from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.minute_cash_order import step_stop_exits
from backtest.research.strategy6_56_rules import CONT_STEP_STOP_PCT, STEP_STOP_PCT

CODE = "600000.SH"
BUDGET = 10_000.0


def _state(book="version6_56", cash=2_000_000.0):
    hooks = apply_csv_strategy(book, name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, CODE, 10.0, 2_000.0, 0, "2025-11-03")
    group = next(iter(st.book_state["s8_independent"]["groups"].values()))
    return st, hooks, group


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


def test_build_lot_still_stops_at_minus_10():
    st, hooks, group = _state()
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    build = next(lot for lot in st.positions[CODE] if lot.is_step)
    assert group.executed_steps == 1
    assert build.lot_id not in group.cont_open
    (pos,) = exit_positions(st, CODE, 2)
    assert (
        step_stop_exits(
            st,
            CODE,
            pos,
            9.91,
            "2025-11-05",
            2,
            (100.0, 5.0),
            step_stop_pct=STEP_STOP_PCT,
            cont_step_stop_pct=CONT_STEP_STOP_PCT,
            hm=600,
        )
        == 0
    )
    assert build.shares > 0
    assert (
        step_stop_exits(
            st,
            CODE,
            pos,
            9.90,
            "2025-11-05",
            2,
            (100.0, 5.0),
            step_stop_pct=STEP_STOP_PCT,
            cont_step_stop_pct=CONT_STEP_STOP_PCT,
            hm=601,
        )
        == 1
    )
    assert build.shares == 0
    assert st.stats.get("arm_cont_rebuy", 0) == 0


def test_plus_20_build_is_not_a_continuation_rung():
    st, hooks, group = _state()
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    _add(st, hooks, 2, "2025-11-05", "20251105", 12.0)
    assert group.executed_steps == 2
    assert group.cont_open == {}
    _add(st, hooks, 3, "2025-11-06", "20251106", 12.0)
    assert group.executed_steps == 2
    assert group.cont_open == {}
    _add(st, hooks, 4, "2025-11-07", "20251107", 14.0)
    assert group.executed_steps == 3
    assert group.cont_open


def test_cont_lot_does_not_stop_alone():
    st, hooks, group = _state()
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    _add(st, hooks, 2, "2025-11-05", "20251105", 12.0)
    _add(st, hooks, 3, "2025-11-06", "20251106", 16.0)
    cont = next(lot for lot in st.positions[CODE] if lot.lot_id in group.cont_open)
    assert cont.cost == pytest.approx(16.0)
    assert cont.is_step is False
    (pos,) = exit_positions(st, CODE, 4)
    assert (
        step_stop_exits(
            st,
            CODE,
            pos,
            14.40,
            "2025-11-07",
            4,
            (100.0, 5.0),
            step_stop_pct=STEP_STOP_PCT,
            cont_step_stop_pct=CONT_STEP_STOP_PCT,
            hm=600,
        )
        == 0
    )
    assert cont.shares > 0
    assert group.cont_rebuy_armed == []
    trial = group.first_lot
    assert trial.shares > 0
    sold = _sell(st, CODE, pos, 9.0, "2025-11-07", "stop_loss", day_i=4)
    assert sold > 0
    assert CODE not in st.positions
    assert trial.shares == 0
    assert cont.shares == 0


def test_version6_55_keeps_five_percent_scale_and_shared_step_stop():
    hooks55 = apply_csv_strategy("version6_55")
    hooks56 = apply_csv_strategy("version6_56")
    assert hooks55["scale_out_step"] == hooks55["scale_out_frac"] == pytest.approx(0.05)
    assert hooks55["step_stop_pct"] == pytest.approx(0.10)
    assert hooks55.get("cont_step_stop_pct") in (None, False, 0, 0.0)
    assert hooks56["scale_out_step"] is None
    assert hooks56["scale_out_frac"] is None
    assert hooks56["cont_step_stop_pct"] in (None, False, 0, 0.0)
    assert hooks56["cont_ride_trial"] is True
    assert hooks56.get("cont_live_max") in (None, False, 0)
    assert hooks55.get("cont_live_max") in (None, False, 0)


def _tranches(st):
    return [t for t in st.trades if t["side"] == "BUY" and t["reason"] == "add:tranche"]


def test_eleventh_live_cont_still_opens():
    st, hooks, group = _state(cash=8_000_000.0)
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    _add(st, hooks, 2, "2025-11-05", "20251105", 12.0)
    for i in range(10):
        px = 14.0 + 2.0 * i
        day_n = 6 + i
        _add(st, hooks, day_n, f"2025-11-{day_n:02d}", f"202511{day_n:02d}", px)
    assert live_cont_count(st, CODE, group) == 10
    assert group.executed_steps == 12
    _add(st, hooks, 16, "2025-11-16", "20251116", 34.0)
    assert live_cont_count(st, CODE, group) == 11
    assert group.executed_steps == 13
    assert st.stats.get("skip_cont_live_max", 0) == 0
    later = [t for t in _tranches(st) if t["date"] == "20251116"]
    assert len(later) == 1
    assert later[0]["shares"] == int(BUDGET * 42.0 / 34.0 / 100) * 100


def test_version6_55_still_opens_past_ten_continuation_rungs():
    st, hooks, group = _state("version6_55")
    group.executed_steps = 12
    _add(st, hooks, 1, "2025-11-04", "20251104", 34.0)
    later = _tranches(st)
    assert len(later) == 1
    assert later[0]["shares"] == int(BUDGET * 42.0 / 34.0 / 100) * 100
    assert group.executed_steps == 13
