# -*- coding: utf-8 -*-
"""策略 6.5：6.4 + 峰值>100% 回撤15%落袋 + band0 保本（人裁 2026-10-02）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_5_rules import (
    FLOOR_BANDS,
    PEAK_DD_PCT,
    STOP_PCT,
    STEP_CAP_PER_CODE,
    exit_line,
    give_band,
    lot_budget,
    peak_dd_active,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "line", "note"),
    [
        # band0 保本：离散线被抬到成本。
        (10.20, 10.0, 10.00, "band0 max(9.70, 成本)"),
        (10.4999, 10.0, 10.00, "band0 高端仍保本"),
        # band1 / band2 保底 +1% / +3% 不变。
        (10.50, 10.0, 10.10, "band1 保底"),
        (11.00, 10.0, 10.30, "band2 保底"),
        (11.45, 10.0, 10.35, "band2 高端计算线"),
        # 档 ≥3、峰值 ≤ 2×成本：无保底，计算线原样。
        (11.50, 10.0, 11.50 - 1.40, "band3"),
        (19.99, 10.0, 19.99 - 10.0 * 0.62, "band19（A=99.9%，未过 100%）"),
        # 峰值涨幅 > 100%：离场线 = 峰值×0.85（替代梯子）。
        (20.01, 10.0, 20.01 * 0.85, "刚过 100%"),
        (21.00, 10.0, 21.00 * 0.85, "A=110%"),
        (24.088, 10.0, 24.088 * 0.85, "603629 型：锁峰值 85%"),
    ],
)
def test_exit_line(peak, cost, line, note):
    assert exit_line(cost, peak) == pytest.approx(line), note


def test_peak_dd_trigger_and_boundary_discontinuity():
    # A=99.9%：梯子线 13.79；A=100.1%：跳到峰值×0.85 = 17.02（人裁指定的边界）。
    assert exit_line(10.0, 19.99) == pytest.approx(19.99 - 6.2)
    assert peak_dd_active(19.99, 10.0) is False
    assert peak_dd_active(20.01, 10.0) is True
    # 触发语义与 reason。
    assert take_profit_reason(17.00, 10.0, 21.00, 1) == "trail:peakdd15"
    assert take_profit_reason(17.86, 10.0, 21.00, 1) is None
    # band0 保本触发：跌回成本即走（含击穿后的实际 close）。
    assert take_profit_reason(10.00, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(9.90, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(10.01, 10.0, 10.20, 1) is None


def test_gates_and_constants():
    assert take_profit_reason(10.00, 10.0, 10.20, 0) is None
    assert take_profit_reason(9.90, 10.0, 10.00, 1) is None
    assert take_profit_reason(0.0, 10.0, 10.20, 1) is None
    with pytest.raises(ValueError):
        give_band(10.0, 10.0)
    assert FLOOR_BANDS == {0: 0.00, 1: 0.01, 2: 0.03}
    assert PEAK_DD_PCT == pytest.approx(0.15)
    assert STOP_PCT == pytest.approx(0.05)
    assert STEP_CAP_PER_CODE == 4
    assert lot_budget(1_000_000.0, None) == pytest.approx(1_000_000.0)
