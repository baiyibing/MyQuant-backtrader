# -*- coding: utf-8 -*-
"""策略 8 卖点纯函数（规则 v2）。向量表见 arch zcode-arch §边界测试向量表。"""

from __future__ import annotations

import pytest

from backtest.research.strategy8_rules import (
    band_of,
    stop_hits,
    take_profit_reason,
    trigger_line,
)

COST = 10.0


def _tp(px: float, peak: float, n_days: int = 2):
    return take_profit_reason(px, COST, peak, n_days)


def test_stop_hits_30pct():
    assert not stop_hits(7.011, 10.0)
    assert stop_hits(6.989, 10.0)
    assert not stop_hits(6.989, 10.0, stop_pct=0.31)


def test_band_of_price_compare_boundaries():
    # plan §1 开闭 + 价格比较（#6/#10/#14/#16）
    assert band_of(COST, 10.00) is None
    assert band_of(COST, 10.05) == 1
    assert band_of(COST, 10.59) == 1
    assert band_of(COST, 10.60) == 1  # #6 价式：10.6 < 10*1.06
    assert band_of(COST, 10.599) == 1
    assert band_of(COST, 10.601) == 2
    assert band_of(COST, 11.499) == 2
    assert band_of(COST, 11.50) == 3  # plan [15%,50%]；arch #10 标二档为笔误
    assert band_of(COST, 11.500001) == 3
    assert band_of(COST, 15.00) == 3  # #14 50%→三档
    assert band_of(COST, 15.01) == 4
    assert band_of(COST, 20.00) == 4  # #16 100%→四档
    assert band_of(COST, 20.01) == 5


def test_vector_1_g_le_0_and_below_cost():
    assert _tp(10.50, 10.00) is None
    assert _tp(9.50, 10.00) is None


def test_vector_3_4_band1_line_and_breakeven():
    # peak=10.05 → line = 10 + 0.30*0.05 = 10.015
    assert _tp(10.015, 10.05) == "trail:band:1"
    assert _tp(10.016, 10.05) is None
    assert _tp(10.00, 10.05) == "trail:band:1"  # px=cost 保本/微亏


def test_vector_5_band1_near_6pct():
    # peak=10.59 → line ≈ 10.177
    assert _tp(10.18, 10.59) is None
    assert _tp(10.17, 10.59) == "trail:band:1"


def test_vector_6_float_6pct_price_compare_band1():
    # #6：价式落一档；线=10.18。arch 写 px=10.19 触发与线不符 → 按 plan 线断言。
    assert band_of(COST, 10.60) == 1
    assert trigger_line(COST, 10.60, 1) == pytest.approx(10.18)
    assert _tp(10.18, 10.60) == "trail:band:1"
    assert _tp(10.19, 10.60) is None


def test_vector_7_cross_6pct_continuity():
    # peak=10.599 → band1, line≈10.1797
    assert _tp(10.17, 10.599) == "trail:band:1"
    assert _tp(10.19, 10.599) is None
    # peak=10.601 → band2, line=10.2；px=10.19 触发
    assert band_of(COST, 10.601) == 2
    assert _tp(10.19, 10.601) == "trail:band:2"
    assert _tp(10.21, 10.601) is None


def test_vector_9_band2_plus_2pct():
    assert _tp(10.21, 11.499) is None
    assert _tp(10.19, 11.499) == "trail:band:2"


def test_vector_10_11_15pct_boundary():
    # #10：plan 价式 11.50→三档线 11.5；px=11.49 触发（arch「二档 None」与 plan 冲突）
    assert band_of(COST, 11.50) == 3
    assert trigger_line(COST, 11.50, 3) == pytest.approx(11.5)
    assert _tp(11.49, 11.50) == "trail:band:3"
    assert _tp(11.51, 11.50) is None
    # #11 ε
    assert band_of(COST, 11.500001) == 3
    assert _tp(11.50, 11.500001) == "trail:band:3"
    assert _tp(11.51, 11.500001) is None


def test_vector_12_band3_kink_at_25pct():
    # peak=12.5 → max(11.5, 10+0.6*2.5=11.5)=11.5
    assert _tp(11.50, 12.50) == "trail:band:3"
    assert _tp(11.51, 12.50) is None


def test_vector_14_50pct_stays_band3():
    # #14
    assert band_of(COST, 15.00) == 3
    assert trigger_line(COST, 15.00, 3) == pytest.approx(13.0)
    assert _tp(13.005, 15.00) is None
    assert _tp(13.00, 15.00) == "trail:band:3"


def test_vector_15_just_over_50pct_band4():
    # peak=15.01 → 0.7g = 13.507
    assert band_of(COST, 15.01) == 4
    assert _tp(13.51, 15.01) is None
    assert _tp(13.50, 15.01) == "trail:band:4"


def test_vector_16_100pct_stays_band4():
    # #16
    assert band_of(COST, 20.00) == 4
    assert trigger_line(COST, 20.00, 4) == pytest.approx(17.0)
    assert _tp(17.005, 20.00) is None
    assert _tp(17.00, 20.00) == "trail:band:4"


def test_vector_17_18_band5():
    assert band_of(COST, 20.01) == 5
    assert _tp(18.01, 20.01) is None
    assert _tp(18.00, 20.01) == "trail:band:5"
    # #18 peak=30 → line=10+0.8*20=26
    assert _tp(26.01, 30.00) is None
    assert _tp(25.99, 30.00) == "trail:band:5"


def test_vector_19_below_cost_guard_across_bands():
    assert _tp(9.90, 11.50) is None


def test_vector_20_t1_exemption_gate():
    # #20：默认 n_days=1 与三参调用全 None
    assert take_profit_reason(10.0, COST, 30.0) is None
    assert take_profit_reason(9.0, COST, 30.0, 1) is None
    assert take_profit_reason(25.0, COST, 30.0, 1) is None
    assert take_profit_reason(25.0, COST, 30.0, 0) is None
    assert take_profit_reason(25.99, COST, 30.0, 2) == "trail:band:5"


def test_vector_21_unit_peak_cross_15pct_tightens_line():
    # 反弹抬 peak：g 14.9%→15.1%（peak 11.49→15.1）后按 +15% 全局底评（引擎级另见 B）
    assert band_of(COST, 11.49) == 2
    assert trigger_line(COST, 11.49, 2) == pytest.approx(10.2)
    assert _tp(11.40, 11.49) is None  # 仍高于 +2%
    peak_hi = 11.51  # g=15.1%
    assert band_of(COST, peak_hi) == 3
    assert trigger_line(COST, peak_hi, 3) == pytest.approx(11.5)
    assert _tp(11.40, peak_hi) == "trail:band:3"


def test_vector_22_equality_triggers():
    # #22：一档等号线（peak=10.60 价式一档 → 线 10.18，非旧 +2%）
    assert _tp(10.18, 10.60) == "trail:band:1"
    # 二档等号
    assert _tp(10.20, 10.601) == "trail:band:2"


def test_take_profit_below_cost_is_none():
    assert _tp(9.95, 13.0) is None
