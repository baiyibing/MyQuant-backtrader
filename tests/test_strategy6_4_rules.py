# -*- coding: utf-8 -*-
"""策略 6.4：6.3 + 档1/2 保底(1%/3%) + 单票 step 4 笔上限（人裁 2026-10-02）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_4_rules import (
    ADD_STEP,
    FLOOR_BANDS,
    PEAK_GAP_MIN,
    STOP_PCT,
    STEP_CAP_PER_CODE,
    STEP_FRAC,
    exit_line,
    give_band,
    lot_budget,
    take_profit_reason,
)


@pytest.mark.parametrize(
    ("peak", "cost", "band", "line"),
    [
        # 档 0：无保底，允许成本下方（不变）。
        (10.20, 10.0, 0, 10.20 - 0.50),
        # 档 1（B=8%）：保底 +1%。档内计算线 0.97~1.02，低端被抬到 1.01。
        (10.50, 10.0, 1, 10.10),
        (10.80, 10.0, 1, 10.10),  # 计算线 10.00 → 保底 10.10 生效
        (10.99, 10.0, 1, 10.19 - 0.00),  # 计算线 10.19 > 保底 → 计算线生效
        # 档 2（B=11%）：保底 +3%。计算线 0.99~1.04，+14% 前保底生效。
        (11.00, 10.0, 2, 10.30),
        (11.30, 10.0, 2, 10.30),  # 计算线 10.19 → 保底生效
        (11.45, 10.0, 2, 10.35),  # 计算线 10.35 > 保底
        # 档 ≥3：无保底（计算线原样）。
        (11.50, 10.0, 3, 11.50 - 1.40),
        (12.00, 10.0, 4, 12.00 - 1.70),
        (20.00, 10.0, 20, 20.00 - 6.50),
    ],
)
def test_ladder_with_floor(peak, cost, band, line):
    assert give_band(peak, cost) == band
    assert exit_line(cost, peak) == pytest.approx(line)


def test_take_profit_trigger_semantics():
    # 档 1 保底触发：px ≤ 10.10 触发、10.11 不触发。
    assert take_profit_reason(10.10, 10.0, 10.50, 1) == "trail:ladder:5"
    assert take_profit_reason(10.11, 10.0, 10.50, 1) is None
    # 档 0 仍允许成本下方。
    assert take_profit_reason(9.70, 10.0, 10.20, 1) == "trail:ladder:0"
    # 档 3 无保底：线 10.10，可低于档 2 的保底线（人裁指定「其他档位不改变」）。
    assert take_profit_reason(10.10, 10.0, 11.50, 1) == "trail:ladder:15"


def test_gates_and_constants():
    assert take_profit_reason(10.10, 10.0, 10.50, 0) is None
    assert take_profit_reason(9.90, 10.0, 10.00, 1) is None
    assert take_profit_reason(0.0, 10.0, 10.50, 1) is None
    with pytest.raises(ValueError):
        give_band(10.0, 10.0)
    assert FLOOR_BANDS == {1: 0.01, 2: 0.03}
    assert STOP_PCT == pytest.approx(0.05)
    assert ADD_STEP == pytest.approx(0.20)
    assert STEP_FRAC == pytest.approx(1.0)
    assert STEP_CAP_PER_CODE == 4
    assert PEAK_GAP_MIN == 15
    assert lot_budget(1_000_000.0, None) == pytest.approx(1_000_000.0)


def test_step_cap_per_code_blocks_fifth_add():
    """单票 step 上限 4 笔：第 5 档触发时跳过并计 skip_step_cap。"""
    from backtest.research.csv_ledger import configure_s8, execute_buy
    from backtest.research.csv_simulate_loop import init_sim_state, run_step_adds_day
    from backtest.research.csv_strategy_books import apply_csv_strategy

    hooks = apply_csv_strategy("version6_4")
    st = init_sim_state(hooks, total_cash=10_000_000, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, "600000.SH", 10.0, 1_000_000, 0, "2025-11-03")
    # +20%/+40%/+60%/+80% 各加一笔（跨 4 天，每日一笔）。
    for day_i, px in ((1, 12.0), (2, 14.4), (3, 16.8), (4, 19.2)):
        run_step_adds_day(
            st,
            day_i=day_i,
            day=f"2025-11-0{day_i + 2}",
            ds=f"2025110{day_i + 2}",
            names={},
            buy_quote_for=lambda _c, px=px: (px, [px]),
            sizing="per_name",
            name_budget=1_000_000,
        )
    assert len([t for t in st.trades if t.get("reason") == "add:step20"]) == 4
    # 第 5 档（+100%）：票级上限已满 → 跳过。
    run_step_adds_day(
        st,
        day_i=5,
        day="2025-11-08",
        ds="20251108",
        names={},
        buy_quote_for=lambda _c: (20.0, [20.0]),
        sizing="per_name",
        name_budget=1_000_000,
    )
    assert len([t for t in st.trades if t.get("reason") == "add:step20"]) == 4
    assert st.stats.get("skip_step_cap", 0) == 1


def test_step_cap_shared_across_groups_same_day():
    """同日同票两组都到 +20% 档：票级 4 笔上限不得被同一次访问绕过。"""
    from backtest.research.csv_ledger import configure_s8, execute_buy
    from backtest.research.csv_simulate_loop import (
        init_sim_state,
        run_pool_buys_day,
        run_step_adds_day,
    )
    from backtest.research.csv_strategy_books import apply_csv_strategy

    hooks = apply_csv_strategy("version6_4")
    st = init_sim_state(hooks, total_cash=20_000_000, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    # 两个独立组：01-03 与 01-05 两个信号日，成本都是 10.0。
    for day_i, (day, ds) in enumerate(
        (("2025-11-03", "20251103"), ("2025-11-05", "20251105"))
    ):
        run_pool_buys_day(
            st, {}, day_i=day_i, day=day, ds=ds, pool_days={ds: ["600000.SH"]},
            daily_quota=1_000_000, names={}, allow_add=True, buy_gate=None,
            buy_quote_for=lambda code: (10.0, [10.0]), sizing="per_name",
            name_budget=1_000_000,
        )
    assert len(st.positions["600000.SH"]) == 2
    # +100% 一根拉满：两组当日共 2 笔；连续三日 → 第 4 笔封顶、第 5 次尝试跳过。
    for day_i, (day, ds) in enumerate(
        (("2025-11-06", "20251106"), ("2025-11-07", "20251107"), ("2025-11-10", "20251110"))
    ):
        run_step_adds_day(
            st, day_i=2 + day_i, day=day, ds=ds, names={},
            buy_quote_for=lambda _c: (20.0, [20.0]), sizing="per_name",
            name_budget=1_000_000,
        )
    adds = [t for t in st.trades if t.get("reason") == "add:step20"]
    assert len(adds) == 4
    assert st.stats.get("skip_step_cap", 0) >= 1
