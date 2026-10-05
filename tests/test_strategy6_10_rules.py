# -*- coding: utf-8 -*-
"""策略 6.10：6.9 + 止损与 step 止损均 5%（人裁 2026-10-02）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_10_rules import (
    ADD_STEP,
    ADD_STEP2,
    BASE_ZONE_CAPS,
    OPEN_FRAC,
    STOP_PCT,
    TRANCHE_MAX,
    lot_budget,
    take_profit_reason,
)


def test_rules_constants():
    assert STOP_PCT == pytest.approx(0.05)
    from backtest.research.strategy6_10_rules import STEP_STOP_PCT

    assert STEP_STOP_PCT == pytest.approx(0.05)
    assert OPEN_FRAC == pytest.approx(0.20)
    assert ADD_STEP == pytest.approx(0.05)
    assert TRANCHE_MAX == 4
    assert ADD_STEP2 == pytest.approx(0.20)
    assert BASE_ZONE_CAPS == (2, 4)
    assert lot_budget(1_000_000.0, None) == pytest.approx(200_000.0)


def test_sell_side_inherits_6_7_ladder():
    # 三段梯子与 6.7 逐点一致。
    assert take_profit_reason(9.90, 10.0, 10.20, 1) == "trail:ladder:0"
    assert take_profit_reason(10.62, 10.0, 12.50, 1) == "trail:ladder:25"
    assert take_profit_reason(16.00, 10.0, 20.01, 1) == "trail:peakdd20"
    assert take_profit_reason(10.00, 10.0, 10.20, 0) is None


def _open(st, hooks):
    from backtest.research.csv_simulate_loop import run_pool_buys_day

    run_pool_buys_day(
        st,
        {},
        day_i=0,
        day="2025-11-03",
        ds="20251103",
        pool_days={"20251103": ["600000.SH"]},
        daily_quota=1_000_000,
        names={},
        allow_add=True,
        buy_gate=None,
        buy_quote_for=lambda code: (10.0, [10.0]),
        sizing="per_name",
        name_budget=1_000_000,
        name_lot_budget=hooks.get("name_lot_budget"),
    )


def _day(st, day_i, day, ds, px):
    from backtest.research.csv_simulate_loop import run_step_adds_day

    run_step_adds_day(
        st,
        day_i=day_i,
        day=day,
        ds=ds,
        names={},
        buy_quote_for=lambda _c, px=px: (px, [px]),
        sizing="per_name",
        name_budget=1_000_000,
    )


def test_dual_ladder_fills_and_zone_caps():
    """T0 买 20%；+5% 分批×4 至满仓；+20% 基数腿；<100% 上限 2、≥100% 共 4。"""
    from backtest.research.csv_ledger import configure_s8
    from backtest.research.csv_simulate_loop import init_sim_state
    from backtest.research.csv_strategy_books import apply_csv_strategy

    hooks = apply_csv_strategy("version6_10")
    st = init_sim_state(hooks, total_cash=20_000_000, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    _open(st, hooks)
    # T0 首笔 = 20 万。
    assert st.trades[0]["notional"] == pytest.approx(200_000, rel=1e-3)

    days = [
        (1, "2025-11-04", "20251104", 10.5),  # +5% → 分批1 20 万
        (2, "2025-11-05", "20251105", 11.0),  # +10% → 分批2
        (3, "2025-11-06", "20251106", 11.5),  # +15% → 分批3
        (4, "2025-11-07", "20251107", 12.0),  # +20% → 分批4（满仓 100 万）
        (5, "2025-11-10", "20251110", 12.0),  # 仍 +20% → 基数1 100 万
        (6, "2025-11-11", "20251111", 14.0),  # +40% → 基数2 100 万
        (7, "2025-11-12", "20251112", 16.0),  # +60% → 被 <100% 上限 2 拦下
        (8, "2025-11-13", "20251113", 18.0),  # +80% → 仍拦
        (9, "2025-11-14", "20251114", 20.0),  # +100% → 基数3（cap 4）
        (10, "2025-11-17", "20251117", 22.0),  # +120% → 基数4
        (11, "2025-11-18", "20251118", 24.0),  # +140% → 上限 4 拦下
    ]
    for day_i, day, ds, px in days:
        _day(st, day_i, day, ds, px)

    tr = [t for t in st.trades if t["side"] == "BUY"]
    tranches = [t for t in tr if t["reason"] == "add:step20"]
    bases = [t for t in tr if t["reason"] == "add:base20"]
    assert len(tranches) == 4
    assert all(t["notional"] <= 200_000 + 1 for t in tranches)  # 整百向下
    assert len(bases) == 4
    assert all(990_000 < t["notional"] <= 1_000_000 for t in bases)  # 整百向下
    # 总投入 ≤ 20 + 4×20 + 4×100 = 500 万（整百向下略少）。
    assert 4_800_000 < sum(t["notional"] for t in tr) <= 5_000_000
    # 上限拦截计数（16/18/24 三天各一次）。
    assert st.stats.get("skip_step_cap", 0) == 0  # 双梯子书不走旧票级上限
