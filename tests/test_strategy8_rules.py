# -*- coding: utf-8 -*-
"""策略 8 卖点纯函数。"""

from __future__ import annotations

import pytest

from backtest.research.strategy8_rules import (
    band_floor,
    peak_drawdown_hits,
    stop_hits,
    take_profit_reason,
)


def test_band_floor_boundaries():
    assert band_floor(0.0) is None
    assert band_floor(0.01) is None
    assert band_floor(0.059) is None
    assert band_floor(0.06) == pytest.approx(0.02)
    assert band_floor(0.15) == pytest.approx(0.02)
    assert band_floor(0.1501) == pytest.approx(0.15)
    assert band_floor(0.40) == pytest.approx(0.15)
    assert band_floor(0.4001) == pytest.approx(0.30)
    assert band_floor(0.60) == pytest.approx(0.30)
    assert band_floor(0.6001) == pytest.approx(0.50)
    assert band_floor(0.80) == pytest.approx(0.50)
    assert band_floor(0.8001) == pytest.approx(0.70)
    assert band_floor(1.00) == pytest.approx(0.70)
    assert band_floor(1.0001) == pytest.approx(0.90)
    assert band_floor(1.20) == pytest.approx(0.90)
    assert band_floor(1.2001) is None
    assert band_floor(3.00) is None


def test_stop_hits_20pct():
    assert not stop_hits(8.011, 10.0)
    assert stop_hits(7.989, 10.0)
    assert not stop_hits(7.989, 10.0, stop_pct=0.21)


def test_take_profit_first_band():
    assert take_profit_reason(11.511, 10.0, 13.0) is None
    assert take_profit_reason(11.489, 10.0, 13.0) == "trail:band:15"


def test_take_profit_mid_bands():
    assert take_profit_reason(13.011, 10.0, 14.1) is None
    assert take_profit_reason(12.989, 10.0, 14.1) == "trail:band:30"
    assert take_profit_reason(15.011, 10.0, 16.1) is None
    assert take_profit_reason(14.989, 10.0, 16.1) == "trail:band:50"


def test_take_profit_small_band_to_plus_2pct():
    assert take_profit_reason(10.05, 10.0, 10.10) is None  # 峰值 +1%，未到 +6%
    assert take_profit_reason(10.10, 10.0, 10.50) is None  # 峰值 +5%，未到 +6%
    assert take_profit_reason(10.201, 10.0, 10.60) is None
    assert take_profit_reason(10.20, 10.0, 10.60) == "trail:band:2"
    assert take_profit_reason(10.20, 10.0, 11.0) == "trail:band:2"
    assert take_profit_reason(10.199, 10.0, 10.0) is None


def test_take_profit_small_band_still_above_floor():
    assert take_profit_reason(11.40, 10.0, 11.50) is None


def test_take_profit_below_cost_is_none():
    assert take_profit_reason(9.95, 10.0, 13.0) is None


def test_peak_dd_armed_only_above_120pct():
    assert not peak_drawdown_hits(12.00, 10.0, 15.01)  # +50% 不再武装
    assert not peak_drawdown_hits(17.60, 10.0, 22.0)  # +120% 不含
    assert peak_drawdown_hits(17.60, 10.0, 22.01)  # 22.01*0.80=17.608
    assert not peak_drawdown_hits(17.62, 10.0, 22.01)


def test_take_profit_peak_dd_replaces_last_band():
    # 峰值 30（+200%）：无分档地板，最高价×80%=24
    assert take_profit_reason(24.10, 10.0, 30.0) is None
    assert take_profit_reason(23.90, 10.0, 30.0) == "trail:peak_dd"
    assert take_profit_reason(20.90, 10.0, 30.0) == "trail:peak_dd"
    assert take_profit_reason(20.90, 10.0, 30.0) != "trail:band:110"
