# -*- coding: utf-8 -*-
"""策略 6.1 无上限步进梯子（人裁 2026-10-02：Q1=G / Q2 允许成本下方 / Q3 无上限）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_1_rules import (
    BAND_WIDTH,
    GIVE_BASE,
    GIVE_STEP,
    PEAK_GAP_MIN,
    STOP_PCT,
    exit_line,
    give_band,
    lot_budget,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "band", "line"),
    [
        # A∈[0,5%) 档 0，B=5%。
        (10.20, 10.0, 0, 10.20 - 0.50),
        (10.4999, 10.0, 0, 10.4999 - 0.50),
        # A=5% 起档 1，B=7%（边界用 1e-12 容差归上档）。
        (10.50, 10.0, 1, 10.50 - 0.70),
        (10.99, 10.0, 1, 10.99 - 0.70),
        # A=10% 起档 2，B=9%。
        (11.00, 10.0, 2, 11.00 - 0.90),
        # A=20% 起档 4，B=13%；无上限（Q3）。
        (12.00, 10.0, 4, 12.00 - 1.30),
        # A=100% 档 20，B=45%。
        (20.00, 10.0, 20, 20.00 - 4.50),
    ],
)
def test_ladder_bands_and_exit_line(peak, cost, band, line):
    assert give_band(peak, cost) == band
    assert exit_line(cost, peak) == pytest.approx(line)


def test_take_profit_uses_ladder_line():
    # 触线用 <=；上浮 1 分钱不触发。
    assert take_profit_reason(9.70, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(9.71, 10.0, 10.20, 1) is None
    assert take_profit_reason(10.10, 10.0, 11.00, 1) == "trail:ladder:10"
    assert take_profit_reason(10.11, 10.0, 11.00, 1) is None


def test_take_profit_below_cost_is_allowed():
    # Q2：首档离场线 = 峰值 − 成本×5% < 成本时仍然触发（小赚也护）。
    assert take_profit_reason(9.50, 10.0, 10.05, 1) == "trail:ladder:0"


def test_take_profit_t0_not_evaluated_and_bad_inputs():
    assert take_profit_reason(9.70, 10.0, 10.20, 0) is None
    assert take_profit_reason(9.70, 10.0, 10.20, -1) is None
    assert take_profit_reason(0.0, 10.0, 10.20, 1) is None
    assert take_profit_reason(9.70, 0.0, 10.20, 1) is None
    assert take_profit_reason(9.70, 10.0, 0.0, 1) is None
    # 峰值 ≤ 成本不评止盈（交给 −5% 止损）。
    assert take_profit_reason(9.60, 10.0, 10.00, 1) is None
    assert take_profit_reason(9.60, 10.0, 9.90, 1) is None


def test_give_band_rejects_non_positive_gain():
    with pytest.raises(ValueError):
        give_band(10.0, 10.0)
    with pytest.raises(ValueError):
        give_band(9.9, 10.0)
    with pytest.raises(ValueError):
        give_band(10.5, 0.0)


def test_book_constants_and_lot_budget():
    assert STOP_PCT == pytest.approx(0.05)
    assert BAND_WIDTH == pytest.approx(0.05)
    assert GIVE_BASE == pytest.approx(0.05)
    assert GIVE_STEP == pytest.approx(0.02)
    assert PEAK_GAP_MIN == 15
    # 每笔整基：新组 / step / 再现组同口径。
    assert lot_budget(1_000_000.0, None) == pytest.approx(1_000_000.0)


def test_step_lots_do_not_enter_exit_cost_basis():
    """人裁纠偏 2026-10-02：step 加仓仅同进同出，退出成本基数锚首仓买入价。

    v8 系保持加权均价（weighted 锚）不变。
    """
    from backtest.research.csv_ledger import configure_s8, execute_buy, exit_positions
    from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
    from backtest.research.csv_strategy_books import apply_csv_strategy

    def _group_cost(strategy: str) -> float:
        hooks = apply_csv_strategy(strategy)
        st = init_sim_state(hooks, total_cash=5_000_000, bars_loaded=1, pool_days={})[0]
        configure_s8(st, hooks)
        execute_buy(st, "600000.SH", 10.0, 1_000_000, 0, "2025-11-03")
        run_step_adds_day(
            st, day_i=1, day="2025-11-04", ds="20251104", names={},
            buy_quote_for=lambda _c: (12.0, [12.0]), sizing="per_name",
            name_budget=1_000_000,
        )
        (view,) = exit_positions(st, "600000.SH")
        return view.cost

    # 6.1：step @12 不进基数 → 退出成本仍是首仓 10.0。
    assert _group_cost("version6_1") == pytest.approx(10.0)
    # v8：仍是组内加权均价（(10.0 + 12.0) / 2 股价加权 ≈ 10.9x）。
    assert _group_cost("version8") == pytest.approx(10.9, abs=0.1)
