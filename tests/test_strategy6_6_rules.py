# -*- coding: utf-8 -*-
"""策略 6.6：6.5 + 峰值×0.80 + step +10%×8 笔 + 低档保底细化（人裁 2026-10-02）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_6_rules import (
    ADD_STEP,
    PEAK_DD_PCT,
    STOP_PCT,
    STEP_CAP_PER_CODE,
    exit_line,
    floor_gain,
    give_band,
    lot_budget,
    peak_dd_active,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "line", "note"),
    [
        # [0,3%)：保底成本价。
        (10.20, 10.0, 10.00, "A=2% → max(9.70, 成本)"),
        (10.299, 10.0, 10.00, "A=2.99% 仍保本"),
        # [3,5%)：保底 +1%。
        (10.30, 10.0, 10.10, "A=3.0% → max(9.80, +1%)"),
        (10.49, 10.0, 10.10, "A=4.9%"),
        # band1（[5,10%)）保底 +1% 维持。
        (10.50, 10.0, 10.10, "band1"),
        (10.99, 10.0, 10.19, "band1 高端计算线"),
        # band2（[10,15%)）保底 +3% 维持。
        (11.00, 10.0, 10.30, "band2"),
        (11.45, 10.0, 10.35, "band2 高端计算线"),
        # ≥15%：无保底。
        (11.50, 10.0, 11.50 - 1.40, "band3"),
        # 峰值 > 100%：峰值×0.80。
        (20.01, 10.0, 20.01 * 0.80, "刚过 100%"),
        (24.088, 10.0, 24.088 * 0.80, "603629 型"),
    ],
)
def test_exit_line(peak, cost, line, note):
    assert exit_line(cost, peak) == pytest.approx(line), note


def test_floor_gain_ladder():
    assert floor_gain(10.20, 10.0) == pytest.approx(0.00)
    assert floor_gain(10.299, 10.0) == pytest.approx(0.00)
    assert floor_gain(10.30, 10.0) == pytest.approx(0.01)
    assert floor_gain(10.49, 10.0) == pytest.approx(0.01)
    assert floor_gain(10.50, 10.0) == pytest.approx(0.01)  # band1 维持 +1%
    assert floor_gain(11.00, 10.0) == pytest.approx(0.03)  # band2 维持 +3%
    assert floor_gain(11.49, 10.0) == pytest.approx(0.03)
    assert floor_gain(11.50, 10.0) is None  # ≥15% 无保底


def test_triggers_and_reasons():
    # 峰值回撤 20%：reason trail:peakdd20。
    assert take_profit_reason(16.00, 10.0, 20.01, 1) == "trail:peakdd20"
    assert take_profit_reason(16.02, 10.0, 20.01, 1) is None
    # [3,5%) 保底 +1%：px ≤ 10.10 触发。
    assert take_profit_reason(10.10, 10.0, 10.30, 1) == "trail:ladder:0"
    assert take_profit_reason(10.11, 10.0, 10.30, 1) is None
    # [0,3%) 保本：跌回成本即走（含击穿后的实际 close）。
    assert take_profit_reason(9.90, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(10.01, 10.0, 10.20, 1) is None


def test_gates_and_constants():
    assert take_profit_reason(9.90, 10.0, 10.20, 0) is None
    assert take_profit_reason(9.90, 10.0, 10.00, 1) is None
    with pytest.raises(ValueError):
        give_band(10.0, 10.0)
    assert PEAK_DD_PCT == pytest.approx(0.20)
    assert ADD_STEP == pytest.approx(0.10)
    assert STEP_CAP_PER_CODE == 8
    assert STOP_PCT == pytest.approx(0.05)
    assert lot_budget(1_000_000.0, None) == pytest.approx(1_000_000.0)
    assert peak_dd_active(20.01, 10.0) is True
    assert peak_dd_active(19.99, 10.0) is False


def test_step_add_at_10pct_and_cap_8():
    """+10% 首档触发、每笔整基、第 9 次触档被票级 8 笔上限拦下。"""
    from backtest.research.csv_ledger import configure_s8, execute_buy
    from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
    from backtest.research.csv_strategy_books import apply_csv_strategy

    hooks = apply_csv_strategy("version6_6")
    st = init_sim_state(hooks, total_cash=20_000_000, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, "600000.SH", 10.0, 1_000_000, 0, "2025-11-03")
    # +9% 不触发；+10% 触发一笔整基。
    run_step_adds_day(
        st,
        day_i=1,
        day="2025-11-04",
        ds="20251104",
        names={},
        buy_quote_for=lambda _c: (10.9, [10.9]),
        sizing="per_name",
        name_budget=1_000_000,
    )
    assert not [t for t in st.trades if t.get("reason") == "add:step20"]
    run_step_adds_day(
        st,
        day_i=2,
        day="2025-11-05",
        ds="20251105",
        names={},
        buy_quote_for=lambda _c: (11.0, [11.0]),
        sizing="per_name",
        name_budget=1_000_000,
    )
    adds = [t for t in st.trades if t.get("reason") == "add:step20"]
    assert len(adds) == 1
    assert adds[0]["notional"] == pytest.approx(1_000_000, rel=1e-3)
    # 连续拉到 +100%：每日最多一笔，8 笔封顶。
    for day_i, px in enumerate((12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 20.0), start=4):
        run_step_adds_day(
            st,
            day_i=day_i,
            day=f"2025-11-{day_i + 2:02d}",
            ds=f"202511{day_i + 2:02d}",
            names={},
            buy_quote_for=lambda _c, px=px: (px, [px]),
            sizing="per_name",
            name_budget=1_000_000,
        )
    total = [t for t in st.trades if t.get("reason") == "add:step20"]
    assert len(total) == 8
    assert st.stats.get("skip_step_cap", 0) >= 1
