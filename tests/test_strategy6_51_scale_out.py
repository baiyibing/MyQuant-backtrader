# -*- coding: utf-8 -*-
"""6.51：+5% 减仓锚改为组内剩余均价；6.50 仍用首仓 A0。"""

from __future__ import annotations

import pytest

from backtest.research.csv_ledger import configure_s8, execute_buy, exit_positions
from backtest.research.csv_simulate_loop import extra_load_codes_for_strategy, init_sim_state
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.minute_cash_order import scale_out_exits
from backtest.research.strategy6_50_rules import PARKING_SYMBOL
from backtest.research.strategy6_51_rules import (
    SCALE_OUT_ANCHOR,
    SCALE_OUT_FRAC,
    SCALE_OUT_STEP,
)

CODE = "600000.SH"
SIG = "2025-11-03"


def test_scale_out_anchor_constants_and_hooks():
    assert SCALE_OUT_ANCHOR == "weighted"
    assert SCALE_OUT_STEP == pytest.approx(0.05)
    assert SCALE_OUT_FRAC == pytest.approx(0.05)
    hooks50 = apply_csv_strategy("version6_50")
    hooks51 = apply_csv_strategy("version6_51")
    assert hooks50["cost_anchor"] == "first_lot"
    assert hooks51["cost_anchor"] == "first_lot"
    assert hooks50.get("scale_out_anchor", "first_lot") == "first_lot"
    assert hooks51["scale_out_anchor"] == "weighted"
    assert hooks51["cont_stop_rebuy"] is True
    assert hooks51["parking_execute"] is True
    assert hooks51["parking_open_cover"] is True
    assert hooks51["min_lot_top_up"] is True
    assert extra_load_codes_for_strategy("version6_51") == {PARKING_SYMBOL}


def _two_cost_group(book: str):
    hooks = apply_csv_strategy(book)
    st = init_sim_state(hooks, total_cash=10_000_000, bars_loaded=3, pool_days={})[0]
    configure_s8(st, hooks)
    assert execute_buy(
        st, CODE, 10.0, 1_000_000, 0, SIG, entry_signal_date=SIG
    )
    assert execute_buy(
        st,
        CODE,
        20.0,
        1_000_000,
        1,
        "2025-11-04",
        reason="add:tranche",
        position_id=f"{CODE}@{SIG}",
        entry_signal_date=SIG,
    )
    return st


def test_version6_50_still_scales_from_first_lot():
    st = _two_cost_group("version6_50")
    (pos,) = exit_positions(st, CODE, 2)
    lots = st.positions[CODE]
    total = sum(lot.shares for lot in lots)
    assert len(lots) == 2
    assert lots[0].cost == pytest.approx(10.0)
    assert lots[1].cost == pytest.approx(20.0)
    sold = scale_out_exits(
        st, CODE, pos, 10.5, "2025-11-05", 2, (100.0, 5.0),
        scale_step=0.05, scale_frac=0.05, hm=600,
    )
    assert sold == int(total * 0.05 // 100) * 100
    assert sold > 0


def test_version6_51_waits_for_weighted_average():
    st = _two_cost_group("version6_51")
    (pos,) = exit_positions(st, CODE, 2)
    lots = st.positions[CODE]
    shares = sum(lot.shares for lot in lots)
    avg = sum(lot.shares * lot.cost for lot in lots) / shares
    assert avg > 10.5
    limits = (100.0, 5.0)
    assert scale_out_exits(
        st, CODE, pos, 10.5, "2025-11-05", 2, limits,
        scale_step=0.05, scale_frac=0.05, scale_anchor="weighted", hm=600,
    ) == 0
    remaining = sum(lot.shares for lot in st.positions[CODE])
    sold = scale_out_exits(
        st, CODE, pos, avg * 1.05, "2025-11-05", 2, limits,
        scale_step=0.05, scale_frac=0.05, scale_anchor="weighted", hm=601,
    )
    assert sold == int(remaining * 0.05 // 100) * 100
    assert sold > 0
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert all(t["reason"] == "scale_out:5pct" for t in sells)
    assert st.stats.get("sell_scale_out") == 1
