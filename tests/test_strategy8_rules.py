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
    assert band_floor(0.20) is None
    assert band_floor(0.2001) == pytest.approx(0.20)
    assert band_floor(0.40) == pytest.approx(0.20)
    assert band_floor(0.4001) == pytest.approx(0.30)
    assert band_floor(0.60) == pytest.approx(0.30)
    assert band_floor(0.6001) == pytest.approx(0.50)
    assert band_floor(0.80) == pytest.approx(0.50)
    assert band_floor(0.8001) == pytest.approx(0.70)
    assert band_floor(1.00) == pytest.approx(0.70)
    assert band_floor(1.0001) == pytest.approx(0.90)
    assert band_floor(1.20) == pytest.approx(0.90)
    assert band_floor(1.2001) == pytest.approx(1.10)
    assert band_floor(3.00) == pytest.approx(1.10)


def test_stop_hits_15pct():
    assert not stop_hits(8.611, 10.0)
    assert stop_hits(8.489, 10.0)
    assert not stop_hits(8.489, 10.0, stop_pct=0.16)


def test_take_profit_first_band():
    assert take_profit_reason(12.011, 10.0, 13.0) is None
    assert take_profit_reason(11.989, 10.0, 13.0) == "trail:band:20"


def test_take_profit_mid_bands():
    assert take_profit_reason(13.011, 10.0, 14.1) is None
    assert take_profit_reason(12.989, 10.0, 14.1) == "trail:band:30"
    assert take_profit_reason(15.011, 10.0, 16.1) is None
    assert take_profit_reason(14.989, 10.0, 16.1) == "trail:band:50"


def test_take_profit_no_peak_below_base():
    assert take_profit_reason(11.50, 10.0, 11.99) is None


def test_take_profit_below_cost_is_none():
    assert take_profit_reason(9.95, 10.0, 13.0) is None


def test_peak_dd_armed_above_50pct():
    assert not peak_drawdown_hits(11.99, 10.0, 15.0)  # +50% 不含
    assert peak_drawdown_hits(12.00, 10.0, 15.01)  # 15.01*0.80=12.008
    assert not peak_drawdown_hits(12.02, 10.0, 15.01)


def test_take_profit_peak_dd_when_tighter_than_last_band():
    # 峰值 30（+200%）：分档地板 21，最高价×80%=24
    assert take_profit_reason(24.10, 10.0, 30.0) is None
    assert take_profit_reason(23.90, 10.0, 30.0) == "trail:peak_dd"
    assert take_profit_reason(20.90, 10.0, 30.0) == "trail:band:110"
