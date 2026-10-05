# -*- coding: utf-8 -*-
"""策略 6.3：6.1 之上仅改 B 步进 2%→3%（人裁 2026-10-02）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_3_rules import (
    ADD_STEP,
    GIVE_BASE,
    GIVE_STEP,
    PEAK_GAP_MIN,
    STOP_PCT,
    STEP_FRAC,
    exit_line,
    give_band,
    lot_budget,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "band", "give", "line"),
    [
        (10.20, 10.0, 0, 0.05, 10.20 - 0.50),  # 首档不变
        (10.4999, 10.0, 0, 0.05, 10.4999 - 0.50),
        (10.50, 10.0, 1, 0.08, 10.50 - 0.80),  # 档 1：B=8%（6.1 为 7%）
        (10.99, 10.0, 1, 0.08, 10.99 - 0.80),
        (11.00, 10.0, 2, 0.11, 11.00 - 1.10),  # 档 2：B=11%
        (12.00, 10.0, 4, 0.17, 12.00 - 1.70),  # 档 4：B=17%
        (20.00, 10.0, 20, 0.65, 20.00 - 6.50),  # 档 20（A=100%）：B=65%，无上限
    ],
)
def test_ladder_give_is_3pct_per_band(peak, cost, band, give, line):
    assert give_band(peak, cost) == band
    assert exit_line(cost, peak) == pytest.approx(line)
    band_i = give_band(peak, cost)
    assert GIVE_BASE + GIVE_STEP * band_i == pytest.approx(give)


def test_take_profit_triggers_and_boundaries():
    # A=10%（档 2，B=11%）：线 = 11 − 1.10 = 9.90。
    assert take_profit_reason(9.90, 10.0, 11.00, 1) == "trail:ladder:10"
    assert take_profit_reason(9.91, 10.0, 11.00, 1) is None
    # Q2 沿用 6.1：首档离场线在成本下方仍触发。
    assert take_profit_reason(9.70, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(9.71, 10.0, 10.20, 1) is None


def test_gates_and_constants():
    assert take_profit_reason(9.70, 10.0, 10.20, 0) is None
    assert take_profit_reason(9.90, 10.0, 10.00, 1) is None
    assert take_profit_reason(9.60, 10.0, 9.80, 1) is None
    assert take_profit_reason(0.0, 10.0, 10.20, 1) is None
    with pytest.raises(ValueError):
        give_band(10.0, 10.0)
    assert STOP_PCT == pytest.approx(0.05)  # 止损维持 5%（6.1 基线）
    assert ADD_STEP == pytest.approx(0.20)  # step 维持 +20% 整基
    assert STEP_FRAC == pytest.approx(1.0)
    assert PEAK_GAP_MIN == 15
    assert lot_budget(1_000_000.0, None) == pytest.approx(1_000_000.0)
