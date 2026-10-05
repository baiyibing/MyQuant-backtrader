# -*- coding: utf-8 -*-
"""策略 6.11：突破买侧（A0×1.2 首买、1.3–1.6 各 1 基封顶 4，信号无限期）。"""

from __future__ import annotations

import pytest

from backtest.research.strategy6_11_rules import (
    ADD_OFFSET,
    ADD_STEP,
    BREAKOUT_MULT,
    STOP_PCT,
    TRANCHE_MAX,
    lot_budget,
    take_profit_reason,
)


def test_constants():
    assert STOP_PCT == pytest.approx(0.10)
    assert BREAKOUT_MULT == pytest.approx(1.2)
    assert ADD_STEP == pytest.approx(0.10)
    assert ADD_OFFSET == 2
    assert TRANCHE_MAX == 4
    assert lot_budget(1_000_000.0, None) == pytest.approx(1_000_000.0)
    # 卖侧纯函数继承 6.9。
    assert take_profit_reason(16.00, 10.0, 20.01, 1) == "trail:peakdd20"
    assert take_profit_reason(10.62, 10.0, 12.50, 1) == "trail:ladder:25"


def _state():
    from backtest.research.csv_ledger import configure_s8, exit_positions
    from backtest.research.csv_simulate_loop import (
        init_sim_state,
        run_breakout_day,
        run_step_adds_day,
    )
    from backtest.research.csv_strategy_books import apply_csv_strategy

    hooks = apply_csv_strategy("version6_11")
    st = init_sim_state(hooks, total_cash=20_000_000, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)

    def breakout(day_i, day, ds, px, pool=None):
        run_breakout_day(
            st,
            day_i=day_i,
            day=day,
            ds=ds,
            names={},
            pool_days=pool or {},
            buy_quote_for=lambda _c, px=px: (px, [px]),
        )

    def adds(day_i, day, ds, px):
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

    return st, breakout, adds, exit_positions


def test_breakout_signal_wait_and_fill():
    st, breakout, adds, exit_positions = _state()
    pool = {"20251103": ["600000.SH"]}
    breakout(0, "2025-11-03", "20251103", 10.0, pool)  # T0 记 A0=10，不买
    assert st.trades == []
    breakout(1, "2025-11-04", "20251104", 11.9)  # 未及 1.2×A0
    assert st.trades == []
    breakout(2, "2025-11-05", "20251105", 12.1)  # 突破 → 1 基，锚 A0=10
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert len(buys) == 1 and buys[0]["reason"] == "breakout"
    assert buys[0]["notional"] == pytest.approx(1_000_000, rel=1e-3)
    (view,) = exit_positions(st, "600000.SH", 2)
    assert view.cost == pytest.approx(10.0)  # 退出锚 = A0（非成交价 12.1）


def test_add_ladder_from_1_3_capped_4():
    st, breakout, adds, exit_positions = _state()
    breakout(0, "2025-11-03", "20251103", 10.0, {"20251103": ["600000.SH"]})
    breakout(2, "2025-11-05", "20251105", 12.1)
    # 1.2（rise .21 → allowed 2−2=0）不加；1.25（allowed 2−2=0）不加。
    adds(3, "2025-11-06", "20251106", 12.5)
    assert not [t for t in st.trades if t["reason"] == "add:step20"]
    # 1.31（rise .31 → allowed 3−2=1）加第 1 基；1.45 → 第 2；1.55 → 第 3；1.65 → 第 4。
    for day_i, (day, ds, px) in enumerate(
        (
            ("2025-11-07", "20251107", 13.1),
            ("2025-11-10", "20251110", 14.5),
            ("2025-11-11", "20251111", 15.5),
            ("2025-11-12", "20251112", 16.5),
        ),
        start=4,
    ):
        adds(day_i, day, ds, px)
    a = [t for t in st.trades if t["reason"] == "add:step20"]
    assert len(a) == 4
    assert all(990_000 < t["notional"] <= 1_000_000 for t in a)
    # 1.7：封顶后不再加。
    adds(8, "2025-11-13", "20251113", 17.0)
    assert len([t for t in st.trades if t["reason"] == "add:step20"]) == 4
