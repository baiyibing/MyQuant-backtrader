# -*- coding: utf-8 -*-
"""策略 8 卖点纯函数（stop10-max101-80-gap15-reserve-stale8 包）。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backtest.research.strategy8_rules import (
    ADD_STEP,
    ALLOW_ADD,
    DEFER_LIMIT_UP,
    FLOOR_MULT,
    KEEP_FRAC,
    STALE_UNARMED_ONLY,
    UNARMED_STOP_PCT,
    GIVEBACK_MULT,
    INDEX_BLOCKS_ADD,
    INDEX_GATE_ON,
    PEAK_GAP_MIN,
    RESERVE_LIMIT_UP,
    STALE_DAYS,
    STOP_PCT,
    TP_MIN_DAYS,
    allow_new_name_from_gate,
    build_sse_ma10_block_new,
    is_cyb_star_board,
    lot_budget,
    may_add,
    step_add_due,
    stop_hits,
    take_profit_reason,
    trail_line,
)

COST = 10.0


def test_book_constants():
    assert STOP_PCT == pytest.approx(0.10)
    assert FLOOR_MULT == pytest.approx(1.01)
    assert KEEP_FRAC == pytest.approx(0.80)
    assert PEAK_GAP_MIN == 15
    assert TP_MIN_DAYS == 1
    assert STALE_DAYS == 8
    assert STALE_UNARMED_ONLY is False
    assert UNARMED_STOP_PCT == pytest.approx(0.0)
    assert ALLOW_ADD is True
    assert INDEX_BLOCKS_ADD is False
    assert INDEX_GATE_ON is True
    assert GIVEBACK_MULT == pytest.approx(0.0)
    assert ADD_STEP == pytest.approx(0.20)
    assert RESERVE_LIMIT_UP is True
    assert DEFER_LIMIT_UP is False
    assert not stop_hits(9.01, 10.0)
    assert stop_hits(8.99, 10.0)


def test_stop_10_from_t1():
    assert stop_hits(8.99, COST)
    assert not stop_hits(9.01, COST)
    assert take_profit_reason(8.99, COST, 12.00, 1) is None


def test_unarmed_below_floor_does_not_trail():
    assert take_profit_reason(10.00, COST, 10.00, 0) is None
    assert take_profit_reason(10.00, COST, 10.00, 1) is None
    assert take_profit_reason(10.05, COST, 10.05, 1) is None
    assert take_profit_reason(10.09, COST, 10.09, 1) is None


def test_just_armed_at_floor_exits():
    assert take_profit_reason(10.10, COST, 10.10, 1) == "trail:max101_80"
    assert trail_line(COST, 10.10) == pytest.approx(10.10)


def test_keep80_after_runup():
    # peak 12 → line = max(10.10, 10+1.6) = 11.60
    assert trail_line(COST, 12.00) == pytest.approx(11.60)
    assert take_profit_reason(11.61, COST, 12.00, 1) is None
    assert take_profit_reason(11.60, COST, 12.00, 1) == "trail:max101_80"
    assert take_profit_reason(11.00, COST, 12.00, 1) == "trail:max101_80"


def test_stale_at_8_when_unarmed():
    assert take_profit_reason(10.05, COST, 10.05, 7) is None
    assert take_profit_reason(10.05, COST, 10.05, 8) == "force_sell:stale"


def test_trail_beats_stale():
    assert take_profit_reason(11.60, COST, 12.00, 8) == "trail:max101_80"
    assert take_profit_reason(10.10, COST, 10.10, 8) == "trail:max101_80"


def test_cyb_star_board():
    assert is_cyb_star_board("300001.SZ")
    assert is_cyb_star_board("688001.SH")
    assert not is_cyb_star_board("600000.SH")
    assert not is_cyb_star_board("002001.SZ")


def test_lot_budget_is_full_name_budget():
    assert lot_budget(1_000_000.0, []) == pytest.approx(1_000_000.0)


def test_may_add_list_even_loser():
    class _P:
        def __init__(self, cost):
            self.cost = cost

    assert not may_add([], 9.0)
    assert may_add([_P(10.0)], 9.90)
    assert may_add([_P(10.0)], 11.00)


def test_step_add_due_on_20pct():
    class _P:
        def __init__(self, cost, lot_id=0, is_step=False):
            self.cost = cost
            self.lot_id = lot_id
            self.is_step = is_step

    lot0 = _P(10.0, lot_id=0)
    assert not step_add_due([lot0], 11.99)
    assert step_add_due([lot0], 12.00)
    assert not step_add_due([lot0, _P(12.0, lot_id=1, is_step=True)], 13.99)
    assert step_add_due([lot0, _P(12.0, lot_id=1, is_step=True)], 14.00)


def test_index_gate_helper_wires_when_on():
    days = [date(2026, 8, 1) + timedelta(days=i) for i in range(15)]
    values = [100.0] * 9 + [90.0, 89.0, 120.0, 120.0, 120.0, 120.0]
    gate = build_sse_ma10_block_new(dict(zip(days, values)))
    assert gate[days[11]] is True
    fn = allow_new_name_from_gate(gate)
    assert fn is not None
    assert fn(days[11]) is False
    assert fn(days[0]) is True
    assert allow_new_name_from_gate(None) is None
