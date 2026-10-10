# -*- coding: utf-8 -*-
"""6.56：清仓后回到清仓前延续档再买回；试错清仓不复活；上证闸挡住。"""

from __future__ import annotations

import pytest

from backtest.research.csv_ledger import (
    _sell,
    configure_s8,
    execute_buy,
    s8_policy,
)
from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_56_rules import CONT_FRAC, OPEN_FRAC

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


def _buys(st, reason=None):
    return [
        t for t in st.trades if t["side"] == "BUY" and (reason is None or t["reason"] == reason)
    ]


def _close_group(st, group, day="2025-11-04", day_i=1, px=9.8):
    lots = list(st.positions.get(CODE, []))
    for lot in lots:
        sold = _sell(st, CODE, lot, px, day, "trail:ladder:0", day_i=day_i)
        assert sold > 0
    group.first_lot.pending_exit = "trail:ladder:0"
    assert group.closed
    assert CODE not in st.positions
    return group


def _open_through_cont(st, hooks, group, *, through_rise=None):
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    _add(st, hooks, 2, "2025-11-05", "20251105", 12.0)
    if hooks.get("name") == "version6_55":
        _add(st, hooks, 3, "2025-11-06", "20251106", 14.0)
        if through_rise is not None and through_rise >= 0.60 - 1e-12:
            _add(st, hooks, 4, "2025-11-07", "20251107", 16.0)
            assert group.executed_steps == 4
            return 5, "2025-11-08"
        assert group.executed_steps == 3
        return 4, "2025-11-07"
    _add(st, hooks, 3, "2025-11-06", "20251106", 14.0)
    assert group.executed_steps == 3
    assert group.cont_open
    if through_rise is None or through_rise < 0.60 - 1e-12:
        return 4, "2025-11-07"
    _add(st, hooks, 4, "2025-11-07", "20251107", 16.0)
    if through_rise < 0.80 - 1e-12:
        assert group.executed_steps == 4
        return 5, "2025-11-08"
    _add(st, hooks, 5, "2025-11-08", "20251108", 18.0)
    assert group.executed_steps == 5
    return 6, "2025-11-10"


def test_trial_only_close_does_not_resurrect():
    st, hooks, group = _state()
    _close_group(st, group)
    assert group.post_exit_cont_rise is None
    _add(st, hooks, 2, "2025-11-05", "20251105", 16.0)
    _add(st, hooks, 3, "2025-11-06", "20251106", 20.0)
    assert _buys(st, "add:tranche") == []
    assert group.closed
    assert CODE not in st.positions
    assert st.stats.get("add_post_exit_cont", 0) == 0


def test_build_only_close_does_not_resurrect():
    st, hooks, group = _state()
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    _add(st, hooks, 2, "2025-11-05", "20251105", 12.0)
    assert group.executed_steps == 2
    _close_group(st, group, day="2025-11-06", day_i=3)
    assert group.post_exit_cont_rise is None
    _add(st, hooks, 4, "2025-11-07", "20251107", 16.0)
    assert [t for t in _buys(st, "add:tranche") if t["date"] == "20251107"] == []
    assert group.closed
    assert st.stats.get("add_post_exit_cont", 0) == 0


def test_post_exit_cont_rebuy_at_remembered_plus_40():
    st, hooks, group = _state()
    position_id = group.first_lot.position_id
    close_i, close_day = _open_through_cont(st, hooks, group)
    _close_group(st, group, day=close_day, day_i=close_i)
    assert group.post_exit_cont_rise == pytest.approx(0.40)

    _add(st, hooks, close_i + 1, "2025-11-10", "20251110", 13.9)
    assert [t for t in _buys(st, "add:tranche") if t["date"] == "20251110"] == []
    assert group.closed

    _add(st, hooks, close_i + 2, "2025-11-11", "20251111", 14.0)
    opens = [t for t in _buys(st, "add:cont_rebuy_open") if t["date"] == "20251111"]
    assert len(opens) == 1
    assert opens[0]["shares"] == int(BUDGET * OPEN_FRAC / 14.0 / 100) * 100
    tranches = [t for t in _buys(st, "add:tranche") if t["date"] == "20251111"]
    assert len(tranches) == 1
    assert tranches[0]["price"] == pytest.approx(14.0)
    assert tranches[0]["shares"] == int(BUDGET * CONT_FRAC / 14.0 / 100) * 100
    assert tranches[0]["position_id"] == position_id
    assert group.closed is False
    assert group.first_lot.pending_exit == ""
    assert group.first_lot.cost == pytest.approx(10.0)
    assert group.executed_steps == 3
    assert group.cont_open
    assert st.stats.get("add_post_exit_cont") == 1
    assert st.stats.get("add_cont_rebuy_open") == 1
    assert len(_buys(st, "pool")) == 1


def test_post_exit_cont_skips_trial_and_build_rungs():
    st, hooks, group = _state()
    close_i, close_day = _open_through_cont(st, hooks, group)
    _close_group(st, group, day=close_day, day_i=close_i)
    _add(st, hooks, close_i + 2, "2025-11-11", "20251111", 14.0)
    (tranche,) = [t for t in _buys(st, "add:tranche") if t["date"] == "20251111"]
    build_30 = int(BUDGET * 0.30 / 14.0 / 100) * 100
    build_50 = int(BUDGET * 0.50 / 14.0 / 100) * 100
    trial = int(BUDGET * OPEN_FRAC / 14.0 / 100) * 100
    assert tranche["shares"] != build_30
    assert tranche["shares"] != build_50
    assert tranche["shares"] != trial
    assert tranche["shares"] == int(BUDGET * CONT_FRAC / 14.0 / 100) * 100


def test_close_after_plus_80_rebuy_at_plus_80_not_plus_60():
    st, hooks, group = _state()
    close_i, close_day = _open_through_cont(st, hooks, group, through_rise=0.80)
    _close_group(st, group, day=close_day, day_i=close_i)
    assert group.post_exit_cont_rise == pytest.approx(0.80)

    _add(st, hooks, close_i + 1, "2025-11-12", "20251112", 16.0)
    assert [t for t in _buys(st, "add:tranche") if t["date"] == "20251112"] == []
    assert group.closed

    _add(st, hooks, close_i + 2, "2025-11-13", "20251113", 18.0)
    later = [t for t in _buys(st, "add:tranche") if t["date"] == "20251113"]
    assert len(later) == 1
    assert later[0]["shares"] == int(BUDGET * CONT_FRAC / 18.0 / 100) * 100
    assert group.executed_steps == 5
    assert group.closed is False


def test_post_exit_cont_then_later_schedule_rung():
    st, hooks, group = _state()
    close_i, close_day = _open_through_cont(st, hooks, group)
    _close_group(st, group, day=close_day, day_i=close_i)
    _add(st, hooks, close_i + 2, "2025-11-11", "20251111", 14.0)
    _add(st, hooks, close_i + 3, "2025-11-12", "20251112", 16.0)
    later = [t for t in _buys(st, "add:tranche") if t["date"] == "20251112"]
    assert len(later) == 1
    assert later[0]["shares"] == int(BUDGET * CONT_FRAC / 16.0 / 100) * 100
    assert group.executed_steps == 4
    assert not group.closed


def test_open_group_still_fires_first_build_rung():
    st, hooks, group = _state()
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    (tranche,) = _buys(st, "add:tranche")
    assert group.executed_steps == 1
    assert tranche["shares"] == int(BUDGET * 0.30 / 11.0 / 100) * 100
    assert st.stats.get("add_post_exit_cont", 0) == 0


def test_idle_group_without_closed_flag_still_resurrects():
    st, hooks, group = _state()
    close_i, close_day = _open_through_cont(st, hooks, group)
    lots = list(st.positions.get(CODE, []))
    for lot in lots:
        _sell(st, CODE, lot, 9.8, close_day, "trail:ladder:0", day_i=close_i)
    group.closed = False
    group.first_lot.pending_exit = "trail:ladder:0"
    assert CODE not in st.positions
    assert group.post_exit_cont_rise == pytest.approx(0.40)
    _add(st, hooks, close_i + 2, "2025-11-11", "20251111", 14.0)
    later = [t for t in _buys(st, "add:tranche") if t["date"] == "20251111"]
    assert len(later) == 1
    assert later[0]["shares"] == int(BUDGET * CONT_FRAC / 14.0 / 100) * 100
    assert group.first_lot.pending_exit == ""
    assert st.stats.get("add_post_exit_cont") == 1


def test_index_gate_blocks_post_exit_cont():
    st, hooks, group = _state()
    policy = s8_policy(st)
    close_i, close_day = _open_through_cont(st, hooks, group)
    policy["index_blocks_s8_add"] = True
    policy["allow_new_name"] = lambda _day: False
    _close_group(st, group, day=close_day, day_i=close_i)
    _add(st, hooks, close_i + 2, "2025-11-11", "20251111", 14.0)
    assert [t for t in _buys(st, "add:tranche") if t["date"] == "20251111"] == []
    assert group.closed
    assert st.stats.get("add_post_exit_cont", 0) == 0


def test_index_gate_still_blocks_live_adds():
    st, hooks, group = _state()
    policy = s8_policy(st)
    policy["index_blocks_s8_add"] = True
    policy["allow_new_name"] = lambda _day: False
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    assert _buys(st, "add:tranche") == []
    assert group.executed_steps == 0


def test_version6_55_does_not_resurrect_closed_group():
    st, hooks, group = _state("version6_55")
    close_i, close_day = _open_through_cont(st, hooks, group)
    _close_group(st, group, day=close_day, day_i=close_i)
    _add(st, hooks, close_i + 2, "2025-11-11", "20251111", 14.0)
    _add(st, hooks, close_i + 3, "2025-11-12", "20251112", 20.0)
    assert [t for t in _buys(st, "add:tranche") if t["date"] in {"20251111", "20251112"}] == []
    assert group.closed
    assert CODE not in st.positions
    assert st.stats.get("add_post_exit_cont", 0) == 0
    assert s8_policy(st).get("post_exit_cont") is not True


def test_version6_55_index_gate_still_blocks_closed_group():
    st, hooks, group = _state("version6_55")
    policy = s8_policy(st)
    policy["index_blocks_s8_add"] = True
    policy["allow_new_name"] = lambda _day: False
    _close_group(st, group)
    _add(st, hooks, 3, "2025-11-06", "20251106", 16.0)
    assert _buys(st, "add:tranche") == []
    assert st.stats.get("add_post_exit_cont", 0) == 0
