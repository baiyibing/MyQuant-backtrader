# -*- coding: utf-8 -*-
"""策略 8 卖点纯函数。"""

from __future__ import annotations

import pytest

from datetime import date, timedelta

from backtest.research.strategy8_rules import (
    BAND1_MIN_MULT,
    BAND_TRAIL_MIN_MULT,
    GIVEBACK_MULT,
    PEAK_GAP_MIN,
    STALE_DAYS,
    STOP_PCT,
    allow_new_name_from_gate,
    band_of,
    build_sse_ma10_block_new,
    lot_budget,
    may_add,
    never_armed,
    stop_hits,
    take_profit_reason,
    trigger_line,
)

COST = 10.0


def _tp(px: float, peak: float, n_days: int = 2):
    return take_profit_reason(px, COST, peak, n_days)


def test_stop_hits_10pct():
    assert STOP_PCT == pytest.approx(0.10)
    assert PEAK_GAP_MIN == 15
    assert BAND_TRAIL_MIN_MULT == pytest.approx(1.06)
    assert BAND1_MIN_MULT == pytest.approx(0.0)
    assert GIVEBACK_MULT == pytest.approx(0.0)
    assert STALE_DAYS == 8
    assert not stop_hits(9.011, 10.0)
    assert stop_hits(8.989, 10.0)
    assert not stop_hits(8.989, 10.0, stop_pct=0.11)


def test_band_of_price_compare_boundaries():
    assert band_of(COST, 10.00) is None
    assert band_of(COST, 10.59) == 1
    assert band_of(COST, 10.61) == 2
    assert band_of(COST, 11.49) == 2
    assert band_of(COST, 11.50) == 3
    assert band_of(COST, 14.99) == 3
    assert band_of(COST, 15.00) == 4
    assert band_of(COST, 19.99) == 4
    assert band_of(COST, 20.00) == 5
    assert band_of(COST, 30.00) == 5


def test_vector_1_g_le_0_and_below_cost():
    assert _tp(10.50, 10.00) is None
    assert _tp(9.50, 10.00) is None


def test_vector_0_6pct_no_band_trail():
    assert _tp(10.09, 10.30) is None
    assert _tp(10.20, 10.59) is None
    assert _tp(10.00, 10.60) is None
    assert band_of(COST, 10.59) == 1


def test_vector_7_cross_6pct_to_band2_floor_2pct():
    assert band_of(COST, 10.61) == 2
    assert trigger_line(COST, 10.61, 2) == pytest.approx(10.20)
    assert _tp(10.19, 10.61) == "trail:band:2"
    assert _tp(10.21, 10.61) is None


def test_vector_9_band2_plus_2pct():
    assert trigger_line(COST, 10.80, 2) == pytest.approx(10.20)
    assert trigger_line(COST, 11.49, 2) == pytest.approx(10.20)
    assert _tp(10.21, 11.49) is None
    assert _tp(10.20, 11.49) == "trail:band:2"


def test_vector_10_band3_global_15_keep60():
    assert band_of(COST, 11.50) == 3
    assert trigger_line(COST, 11.50, 3) == pytest.approx(11.50)
    assert _tp(11.50, 11.50) == "trail:band:3"
    assert _tp(11.51, 11.50) is None
    assert trigger_line(COST, 12.00, 3) == pytest.approx(11.50)
    assert trigger_line(COST, 13.00, 3) == pytest.approx(11.80)
    assert _tp(11.80, 13.00) == "trail:band:3"
    assert _tp(11.81, 13.00) is None


def test_vector_14_band4_keep70():
    assert band_of(COST, 15.00) == 4
    assert trigger_line(COST, 15.00, 4) == pytest.approx(13.50)
    assert _tp(13.50, 15.00) == "trail:band:4"
    assert _tp(13.51, 15.00) is None
    assert trigger_line(COST, 16.00, 4) == pytest.approx(14.20)


def test_vector_16_band5_keep80():
    assert band_of(COST, 20.00) == 5
    assert trigger_line(COST, 20.00, 5) == pytest.approx(18.00)
    assert _tp(18.00, 20.00) == "trail:band:5"
    assert _tp(18.01, 20.00) is None


def test_vector_19_below_cost_guard_across_bands():
    assert _tp(9.90, 12.00) is None


def test_vector_20_t0_blocked_t1_trails():
    assert take_profit_reason(25.0, COST, 30.0, 0) is None
    assert take_profit_reason(26.00, COST, 30.0, 1) == "trail:band:5"
    assert take_profit_reason(26.01, COST, 30.0, 1) is None


def test_vector_21_unit_peak_cross_15pct():
    assert band_of(COST, 11.49) == 2
    assert trigger_line(COST, 11.49, 2) == pytest.approx(10.20)
    assert band_of(COST, 11.50) == 3
    assert trigger_line(COST, 11.50, 3) == pytest.approx(11.50)
    assert _tp(11.49, 11.50) == "trail:band:3"


def test_take_profit_below_cost_is_none():
    assert _tp(9.95, 13.0) is None
    assert _tp(8.00, 10.00) is None


def test_stale_8_never_armed():
    assert never_armed(COST, 10.59)
    assert not never_armed(COST, 10.61)
    assert take_profit_reason(10.26, COST, 10.50, 7) is None
    assert take_profit_reason(10.26, COST, 10.50, 8) == "force_sell:stale"
    assert take_profit_reason(10.21, COST, 10.61, 8) is None


def test_lot_budget_probe_then_add():
    assert lot_budget(1_000_000.0, []) == pytest.approx(500_000.0)
    assert lot_budget(1_000_000.0, [object()]) == pytest.approx(500_000.0)


def test_may_add_only_winners_after_plus_3pct():
    class _P:
        def __init__(self, cost, peak=None):
            self.cost = cost
            self.peak = cost if peak is None else peak

    assert may_add([], 9.0)
    assert not may_add([_P(10.0)], 10.5)
    assert may_add([_P(10.0, 10.30)], 10.5)
    assert not may_add([_P(10.0, 10.30)], 9.9)
    assert not may_add([_P(10.0, 10.30), _P(11.0, 11.40)], 10.5)


def test_sse_ma10_gate_is_lagged_and_allow_new_name_maps_it():
    days = [date(2026, 8, 1) + timedelta(days=i) for i in range(15)]
    values = [100.0] * 9 + [90.0, 89.0, 120.0, 120.0, 120.0, 120.0]
    gate = build_sse_ma10_block_new(dict(zip(days, values)))
    assert gate[days[11]] is True
    assert gate[days[12]] is False
    allow = allow_new_name_from_gate(gate)
    assert allow(days[11]) is False
    assert allow("20260813") is True
    assert allow_new_name_from_gate(None) is None
    assert allow_new_name_from_gate({})(days[0]) is True
