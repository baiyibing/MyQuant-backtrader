# -*- coding: utf-8 -*-
"""6.54：现金分红入账后买入 600036，6.53 不启用。"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.ashare_exdiv_economics import ExDivEconomics, ExDivEvent
from backtest.research.cash_div_events import official_cmb_events
from backtest.research.csv_ledger import execute_buy, parking_lots
from backtest.research.csv_simulate_loop import (
    accrue_overnight_cash_div,
    bind_parking_session,
    extra_load_codes_for_strategy,
    init_sim_state,
    run_div_to_parking_day,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_54_rules import DIV_TO_PARKING, PARKING_SYMBOL

CODE = "600000.SH"
DAY = "2025-11-04"
DS = "20251104"


def test_div_to_parking_hooks_and_scope():
    assert DIV_TO_PARKING is True
    hooks54 = apply_csv_strategy("version6_54")
    hooks53 = apply_csv_strategy("version6_53")
    assert hooks54["div_to_parking"] is True
    assert hooks54["index_cut"] is True
    assert hooks54["profit_skim_to_parking"] is True
    assert hooks53.get("div_to_parking") is not True
    assert extra_load_codes_for_strategy("version6_54") == {PARKING_SYMBOL}
    assert "现金分红" in __import__(
        "backtest.research.strategy6_54_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "已归档" in __import__(
        "backtest.research.strategy6_54_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "已归档" in __import__(
        "backtest.research.strategy6_53_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "version6_54" in __import__(
        "backtest.research.strategy6_53_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "version6_55" in __import__(
        "backtest.research.strategy6_54_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK


def test_official_cmb_events_are_explicit():
    ev = official_cmb_events()
    assert ev[(PARKING_SYMBOL, "20260116")].cash_div_per_share == pytest.approx(1.013)
    assert ev[(PARKING_SYMBOL, "20260710")].cash_div_per_share == pytest.approx(1.003)
    assert ev[(PARKING_SYMBOL, "20260116")].bonus_ratio == 0
    assert ev[(PARKING_SYMBOL, "20260116")].pay_date == "20260116"


def _bars(px_by_code, days=("2025-11-03", "2025-11-04", "2025-11-05")):
    idx = pd.to_datetime(list(days))
    out = {}
    for code, px in px_by_code.items():
        out[code] = pd.DataFrame(
            {"open": px, "high": px, "low": px, "close": px, "volume": 1_000_000},
            index=idx,
        )
    return out


def test_overnight_cash_div_buys_parking():
    hooks = apply_csv_strategy("version6_54")
    st, _, _ = init_sim_state(hooks, total_cash=500_000.0, bars_loaded=1, pool_days={})
    assert execute_buy(st, CODE, 10.0, 100_000.0, 0, "2025-11-03")
    held = sum(p.shares for p in st.positions[CODE])
    assert held >= 1000
    cash_ps = 1.0
    st.exdiv_economics = ExDivEconomics(
        {
            (CODE, DS): ExDivEvent(
                "unit-cash",
                0,
                cash_ps,
                DS,
                DS,
            )
        },
        st.stats,
    )
    posted = accrue_overnight_cash_div(st, DS)
    assert posted == pytest.approx(held * cash_ps)
    st.stats["div_to_parking_pending"] = posted
    bars = _bars({PARKING_SYMBOL: 10.0, CODE: 10.0})
    day = pd.Timestamp(DAY)
    bind_parking_session(
        st,
        hooks,
        day_i=1,
        day=day,
        ds=DS,
        names={},
        daily_bars=bars,
        qlib_limit_pct=0.50,
    )
    spent = run_div_to_parking_day(
        st,
        hooks,
        day_i=1,
        day=day,
        ds=DS,
        names={},
        daily_bars=bars,
        qlib_limit_pct=0.50,
    )
    assert spent > 0
    park = parking_lots(st, PARKING_SYMBOL)
    assert sum(p.shares for p in park) >= 100
    reasons = [t["reason"] for t in st.trades if t.get("reason") == "parking:cash_div"]
    assert reasons
    assert st.stats["div_to_parking_spent"] == pytest.approx(spent)
