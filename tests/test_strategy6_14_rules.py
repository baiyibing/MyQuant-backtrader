# -*- coding: utf-8 -*-
"""策略 6.14：6.13 + 减仓改每+10%卖10% + 峰值回撤>15% 15交易日未收复清仓。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_14_rules import (
    GIVE_STEP,
    SCALE_OUT_FRAC,
    SCALE_OUT_STEP,
    STEP_STOP_PCT,
    STOP_PCT,
    exit_line,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "line"),
    [
        (10.20, 10.0, 10.20 - 0.50),  # 档0 B=5%
        (10.50, 10.0, 10.50 - 0.80),  # 档1 B=8%
        (11.00, 10.0, 11.00 - 1.10),  # 档2 B=11%
        (12.00, 10.0, 12.00 - 1.70),  # 档4 B=17%
    ],
)
def test_b_step_3pct(peak, cost, line):
    assert exit_line(cost, peak) == pytest.approx(line)
    assert GIVE_STEP == pytest.approx(0.03)


def test_constants_and_gates():
    assert STOP_PCT == pytest.approx(0.05)  # 组级止损维持 6.1 的 5%
    assert STEP_STOP_PCT == pytest.approx(0.10)
    assert SCALE_OUT_STEP == pytest.approx(0.10)
    assert SCALE_OUT_FRAC == pytest.approx(0.10)
    from backtest.research.strategy6_14_rules import PEAK_DD_EXIT, PEAK_DD_SESSIONS

    assert PEAK_DD_EXIT == pytest.approx(0.15)
    assert PEAK_DD_SESSIONS == 15
    assert take_profit_reason(9.90, 10.0, 11.00, 1) == "trail:ladder:10"
    assert take_profit_reason(9.70, 10.0, 10.20, 1) == "trail:ladder:0"  # 允许成本下方
    assert take_profit_reason(9.90, 10.0, 11.00, 0) is None


def _group_with_two_lots():
    from backtest.research.csv_ledger import configure_s8, execute_buy
    from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
    from backtest.research.csv_strategy_books import apply_csv_strategy

    hooks = apply_csv_strategy("version6_14")
    st = init_sim_state(hooks, total_cash=10_000_000, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, "600000.SH", 10.0, 1_000_000, 0, "2025-11-03")
    run_step_adds_day(
        st,
        day_i=1,
        day="2025-11-04",
        ds="20251104",
        names={},
        buy_quote_for=lambda _c: (12.0, [12.0]),
        sizing="per_name",
        name_budget=1_000_000,
    )
    return st


def test_scale_out_sells_5pct_of_holdings_per_band():
    from backtest.research.csv_ledger import exit_positions
    from backtest.research.minute_cash_order import scale_out_exits

    st = _group_with_two_lots()
    lots = st.positions["600000.SH"]
    assert len(lots) == 2
    (pos,) = exit_positions(st, "600000.SH", 2)
    limits = (100.0, 5.0)
    total0 = sum(l.shares for l in lots)

    # 未及 +10%：不卖。
    assert (
        scale_out_exits(
            st, "600000.SH", pos, 10.5, "2025-11-05", 2, limits, scale_step=0.10, scale_frac=0.10
        )
        == 0
    )
    # +10%：卖当时持仓的 10%（整百向下）。
    sold = scale_out_exits(
        st, "600000.SH", pos, 11.0, "2025-11-05", 2, limits, scale_step=0.10, scale_frac=0.10
    )
    expect = int(total0 * 0.10 // 100) * 100
    assert sold == expect
    # 同档不重复。
    assert (
        scale_out_exits(
            st, "600000.SH", pos, 11.5, "2025-11-05", 2, limits, scale_step=0.10, scale_frac=0.10
        )
        == 0
    )
    remaining = sum(l.shares for l in st.positions["600000.SH"])
    sold2 = scale_out_exits(
        st, "600000.SH", pos, 12.0, "2025-11-06", 3, limits, scale_step=0.10, scale_frac=0.10
    )
    assert sold2 == int(remaining * 0.10 // 100) * 100
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert all(t["reason"] == "scale_out:5pct" for t in sells)
    assert st.stats.get("sell_scale_out") == 2


def test_scale_out_t0_and_below_cost_gates():
    from backtest.research.csv_ledger import exit_positions
    from backtest.research.minute_cash_order import scale_out_exits

    st = _group_with_two_lots()
    (pos,) = exit_positions(st, "600000.SH", 1)
    limits = (100.0, 5.0)
    # day_i=1：+10% 未及 → 不卖。
    sold = scale_out_exits(
        st, "600000.SH", pos, 10.5, "2025-11-04", 1, limits, scale_step=0.10, scale_frac=0.10
    )
    assert sold == 0
    # 低于锚价：不评。
    assert (
        scale_out_exits(
            st, "600000.SH", pos, 9.9, "2025-11-05", 2, limits, scale_step=0.10, scale_frac=0.10
        )
        == 0
    )


def test_peak_dd_clear_after_15_sessions():
    """峰值回撤 >15% 且 15 个交易日内未收复 → 全组清仓。"""
    from backtest.research.csv_ledger import exit_positions
    from backtest.research.minute_cash_order import peak_dd_clear_exits

    st = _group_with_two_lots()
    (pos,) = exit_positions(st, "600000.SH", 2)
    limits = (100.0, 5.0)
    # 峰值 = 首仓 10.0（T+0 固定），设 group.first_lot.peak = 12.0，现价 10.0 → 回撤 16.7% > 15%。
    pos.group.first_lot.peak = 12.0
    # 第 1 次触线：记录起始日，不清仓。
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            10.0,
            "2025-11-05",
            2,
            limits,
            peak_dd_exit=0.15,
            peak_dd_sessions=15,
        )
        == 0
    )
    # 第 14 个交易日：仍未收复，不清仓。
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            10.0,
            "2025-11-19",
            16,
            limits,
            peak_dd_exit=0.15,
            peak_dd_sessions=15,
        )
        == 0
    )
    # 第 15 个交易日：清仓。
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            10.0,
            "2025-11-20",
            17,
            limits,
            peak_dd_exit=0.15,
            peak_dd_sessions=15,
        )
        == 1
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert all(t["reason"] == "peak_dd_clear" for t in sells)
    assert not st.positions.get("600000.SH")  # 全组清仓
