# -*- coding: utf-8 -*-
"""策略 6.2：band0 保本锚（D）+ 止损 10% + +10% 半基 step（人裁 2026-10-02）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_2_rules import (
    ADD_STEP,
    BAND0_FLOOR_COST,
    PEAK_GAP_MIN,
    STOP_PCT,
    STEP_FRAC,
    exit_line,
    give_band,
    lot_budget,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "band", "line"),
    [
        # band0：D 方案保本锚 —— 离散线被抬到成本。
        (10.20, 10.0, 0, 10.00),  # 原线 9.70 → max(9.70, 10.0)
        (10.4999, 10.0, 0, 10.00),  # 原线 9.9999 → 仍抬到成本
        # band≥1 不变：离场价 = 峰值 − 成本×B。
        (10.50, 10.0, 1, 10.50 - 0.70),
        (11.00, 10.0, 2, 11.00 - 0.90),
        (12.00, 10.0, 4, 12.00 - 1.30),
        (20.00, 10.0, 20, 20.00 - 4.50),
    ],
)
def test_band_lines(peak, cost, band, line):
    assert give_band(peak, cost) == band
    assert exit_line(cost, peak) == pytest.approx(line)


def test_band0_breakeven_trigger_semantics():
    # 跌回成本价即走：px ≤ 成本 触发；成本上方不触发。
    assert take_profit_reason(10.00, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(10.01, 10.0, 10.20, 1) is None
    # band1 无保本锚：A∈[5%,7%) 离场线仍在成本下方（沿用 6.1 语义）。
    assert take_profit_reason(9.80, 10.0, 10.50, 1) == "trail:ladder:5"  # 线 = 10.50 − 0.70


def test_take_profit_gates():
    assert take_profit_reason(10.00, 10.0, 10.20, 0) is None
    assert take_profit_reason(0.0, 10.0, 10.20, 1) is None
    assert take_profit_reason(10.00, 0.0, 10.20, 1) is None
    assert take_profit_reason(9.90, 10.0, 10.00, 1) is None
    assert take_profit_reason(9.90, 10.0, 9.80, 1) is None


def test_book_constants():
    assert STOP_PCT == pytest.approx(0.10)
    assert BAND0_FLOOR_COST is True
    assert ADD_STEP == pytest.approx(0.10)
    assert STEP_FRAC == pytest.approx(0.5)
    assert PEAK_GAP_MIN == 15
    assert lot_budget(1_000_000.0, None) == pytest.approx(1_000_000.0)


def test_engine_step_add_fires_at_10pct_with_half_base():
    """s8 独立组路径：+10% 触发、每笔 50 万；+9% 不触发。"""
    from backtest.research.csv_ledger import configure_s8, execute_buy
    from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
    from backtest.research.csv_strategy_books import apply_csv_strategy

    def _day(st, px):
        run_step_adds_day(
            st,
            day_i=1,
            day="2025-11-04",
            ds="20251104",
            names={},
            buy_quote_for=lambda _c: (px, [px]),
            sizing="per_name",
            name_budget=1_000_000,
        )

    hooks = apply_csv_strategy("version6_2")
    st = init_sim_state(hooks, total_cash=5_000_000, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, "600000.SH", 10.0, 1_000_000, 0, "2025-11-03")
    _day(st, 10.9)  # +9%：不到 +10% 档
    assert not [t for t in st.trades if t.get("reason") == "add:step20"]
    _day(st, 11.0)  # +10%：加一笔半基
    adds = [t for t in st.trades if t.get("reason") == "add:step20"]
    assert len(adds) == 1
    assert adds[0]["shares"] == 45_400  # 50 万预算整百向下
    assert adds[0]["notional"] == pytest.approx(499_400)
