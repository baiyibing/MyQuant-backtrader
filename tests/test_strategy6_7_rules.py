# -*- coding: utf-8 -*-
"""策略 6.7：6.6 + [15%,100%] 中段保护线 max(梯子线, 峰值×0.85)。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_7_rules import (
    MID_PEAK_DD_PCT,
    PEAK_DD_PCT,
    exit_line,
    mid_peak_dd_active,
    peak_dd_active,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "line", "note"),
    [
        # <15%：与 6.6 完全一致（保底带）。
        (10.20, 10.0, 10.00, "A=2% 保本"),
        (10.30, 10.0, 10.10, "A=3% +1%"),
        (11.00, 10.0, 10.30, "band2 +3%"),
        (11.49, 10.0, 10.39, "band2 高端计算线 11.49−1.10"),
        # [15%,100%]：max(梯子线, 峰值×0.85)。
        (11.50, 10.0, 11.50 - 1.40, "A=15% 梯子线 1.01 > 0.85×1.15=0.978 → 梯子胜"),
        (12.00, 10.0, 12.00 - 1.70, "A=20% 梯子 1.03 > 1.02 → 梯子胜"),
        (12.50, 10.0, 12.50 * 0.85, "A=25% 峰值线 1.0625 > 梯子 1.05 → 绑定"),
        (15.00, 10.0, 15.00 * 0.85, "A=50%"),
        (19.99, 10.0, 19.99 * 0.85, "A=99.9%"),
        # >100%：峰值×0.80 替代。
        (20.01, 10.0, 20.01 * 0.80, "A=100.1%（边界处线回落，按已裁定 0.80）"),
        (24.088, 10.0, 24.088 * 0.80, "603629 型"),
    ],
)
def test_exit_line_three_zones(peak, cost, line, note):
    assert exit_line(cost, peak) == pytest.approx(line), note


def test_mid_zone_activation():
    assert mid_peak_dd_active(11.49, 10.0) is False
    assert mid_peak_dd_active(11.50, 10.0) is True
    assert mid_peak_dd_active(19.99, 10.0) is True
    assert mid_peak_dd_active(20.01, 10.0) is False  # >100% 走峰值×0.80
    assert peak_dd_active(19.99, 10.0) is False
    assert peak_dd_active(20.01, 10.0) is True


def test_triggers_and_reasons():
    # 中段保护线触发仍记档位 reason（跨版可比）。
    assert take_profit_reason(10.62, 10.0, 12.50, 1) == "trail:ladder:25"
    assert take_profit_reason(10.63, 10.0, 12.50, 1) is None
    # >100% 峰值线。
    assert take_profit_reason(16.00, 10.0, 20.01, 1) == "trail:peakdd20"
    # 保底带不变。
    assert take_profit_reason(9.90, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(10.10, 10.0, 10.30, 1) == "trail:ladder:0"


def test_constants_and_gates():
    assert MID_PEAK_DD_PCT == pytest.approx(0.15)
    assert PEAK_DD_PCT == pytest.approx(0.20)
    assert take_profit_reason(10.00, 10.0, 12.50, 0) is None
    assert take_profit_reason(9.90, 10.0, 10.00, 1) is None
    assert take_profit_reason(0.0, 10.0, 12.50, 1) is None
