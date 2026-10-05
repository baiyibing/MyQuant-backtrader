# -*- coding: utf-8 -*-
"""策略 6.8：6.7 + step lot 独立止损 −10%（引擎侧 step_stop_exits）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_8_rules import STEP_STOP_PCT, take_profit_reason


def test_rules_inherit_6_7_lines():
    # 离场线纯函数与 6.7 完全一致；step 止损在引擎侧。
    assert take_profit_reason(10.62, 10.0, 12.50, 1) == "trail:ladder:25"  # 中段保护线
    assert take_profit_reason(16.00, 10.0, 20.01, 1) == "trail:peakdd20"
    assert take_profit_reason(9.90, 10.0, 10.20, 1) == "trail:ladder:0"
    assert STEP_STOP_PCT == pytest.approx(0.10)


def _state_with_step():
    from backtest.research.csv_ledger import configure_s8, execute_buy
    from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
    from backtest.research.csv_strategy_books import apply_csv_strategy

    hooks = apply_csv_strategy("version6_8")
    st = init_sim_state(hooks, total_cash=5_000_000, bars_loaded=1, pool_days={})[0]
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
    lots = st.positions["600000.SH"]
    assert len(lots) == 2 and lots[1].is_step
    return st, lots


def test_step_stop_sells_only_step_lot():
    from backtest.research.minute_cash_order import step_stop_exits

    st, lots = _state_with_step()
    from backtest.research.csv_ledger import exit_positions

    expected_step_shares = lots[1].shares
    (pos,) = exit_positions(st, "600000.SH", 2)
    limits = (100.0, 5.0)  # (limit_up, limit_down) —— 远离涨跌停
    # day_i=2（step 已 T+1）：close 10.79 ≤ 12×0.90=10.80 → 只卖 step lot。
    sold = step_stop_exits(
        st, "600000.SH", pos, 10.79, "2025-11-05", 2, limits, step_stop_pct=0.10, hm=600
    )
    assert sold == 1
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == "stop_loss:step10"
    assert sells[0]["shares"] == expected_step_shares
    assert st.stats.get("sell_stop_step") == 1
    # 首仓 lot 仍在。
    assert st.positions["600000.SH"] and st.positions["600000.SH"][0].cost == pytest.approx(10.0)


def test_step_stop_t1_and_price_gates():
    from backtest.research.csv_ledger import exit_positions
    from backtest.research.minute_cash_order import step_stop_exits

    st, lots = _state_with_step()
    (pos,) = exit_positions(st, "600000.SH", 1)
    limits = (100.0, 5.0)
    # T+0（step 当日，day_i=1）：不可卖。
    assert (
        step_stop_exits(st, "600000.SH", pos, 10.0, "2025-11-04", 1, limits, step_stop_pct=0.10)
        == 0
    )
    # 未及线（10.81 > 10.80）：不动。
    st2, _ = _state_with_step()
    (pos2,) = exit_positions(st2, "600000.SH", 2)
    assert (
        step_stop_exits(st2, "600000.SH", pos2, 10.81, "2025-11-05", 2, limits, step_stop_pct=0.10)
        == 0
    )
