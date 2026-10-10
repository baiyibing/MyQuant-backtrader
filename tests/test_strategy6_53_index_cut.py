# -*- coding: utf-8 -*-
"""6.53：上证连续两日 MA10 下方停止进新筹码并减半持仓，收复买回。"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.csv_ledger import (
    execute_buy,
    execute_parking_buy,
    is_parking_lot,
    s8_policy,
)
from backtest.research.csv_simulate_loop import (
    extra_load_codes_for_strategy,
    init_sim_state,
    run_index_gate_cut_day,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_52_rules import PARKING_SYMBOL
from backtest.research.strategy6_53_rules import (
    INDEX_BLOCKS_S8_ADD,
    INDEX_CUT,
    INDEX_CUT_FRAC,
    INDEX_CUT_MIN_KEEP,
    index_cut_shares,
)

CODE = "600000.SH"
BUDGET = 10_000.0


def test_index_cut_shares_helper():
    assert index_cut_shares(100) == 0
    assert index_cut_shares(150) == 0
    assert index_cut_shares(200) == 100
    assert index_cut_shares(300) == 100
    assert index_cut_shares(500) == 200
    assert index_cut_shares(0) == 0
    assert index_cut_shares(80) == 0


def test_index_cut_hooks_and_scope():
    assert INDEX_CUT is True
    assert INDEX_CUT_FRAC == pytest.approx(0.50)
    assert INDEX_CUT_MIN_KEEP == 100
    assert INDEX_BLOCKS_S8_ADD is True
    hooks = apply_csv_strategy("version6_53")
    assert hooks["index_cut"] is True
    assert hooks["index_cut_frac"] == pytest.approx(0.50)
    assert hooks["index_cut_min_keep"] == 100
    assert hooks["index_blocks_s8_add"] is True
    assert hooks["profit_skim"] is True
    assert extra_load_codes_for_strategy("version6_53") == {PARKING_SYMBOL}
    sibling = apply_csv_strategy("version6_52")
    assert sibling.get("index_cut") is not True
    assert sibling.get("index_blocks_s8_add") is not True
    assert "已归档" in __import__(
        "backtest.research.strategy6_52_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK
    assert "version6_53" in __import__(
        "backtest.research.strategy6_52_rules", fromlist=["HELP_LOCK"]
    ).HELP_LOCK


def _state(book="version6_53", cash=2_000_000.0, per=2_000.0):
    hooks = apply_csv_strategy(book, name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})[0]
    assert execute_buy(st, CODE, 10.0, per, 0, "2025-11-03")
    return st, hooks


def _bars(px_by_code: dict[str, float], days=("2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06")):
    idx = pd.to_datetime(list(days))
    out = {}
    for code, px in px_by_code.items():
        out[code] = pd.DataFrame(
            {"open": px, "high": px, "low": px, "close": px, "volume": 1_000_000},
            index=idx,
        )
    return out


def _cut(st, hooks, day, ds, bars, blocked):
    hooks["allow_new_name"] = (lambda _d, flag=blocked: not flag)
    run_index_gate_cut_day(
        st,
        hooks,
        day_i=1 if ds == "20251104" else 2 if ds == "20251105" else 3,
        day=pd.Timestamp(day),
        ds=ds,
        names={},
        daily_bars=bars,
        qlib_limit_pct=0.50,
    )


def _held(st, code=CODE) -> int:
    return sum(int(lot.shares) for lot in st.positions.get(code, []) if not is_parking_lot(st, lot))


def test_cut_halves_once_then_rebuy_on_recover():
    st, hooks = _state()
    bars = _bars({CODE: 10.0})
    assert _held(st) == 200
    _cut(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    cuts = [t for t in st.trades if t["side"] == "SELL" and t["reason"] == "index_cut"]
    assert len(cuts) == 1
    assert cuts[0]["shares"] == 100
    assert cuts[0]["price_rule"] == "index_cut_open"
    assert _held(st) == 100
    assert st.stats["index_cut_shares"] == 100
    assert st.stats["index_cut_events"] == 1
    _cut(st, hooks, "2025-11-05", "20251105", bars, blocked=True)
    assert len([t for t in st.trades if t["reason"] == "index_cut"]) == 1
    assert _held(st) == 100
    _cut(st, hooks, "2025-11-06", "20251106", bars, blocked=False)
    rebuys = [t for t in st.trades if t["reason"] == "add:index_rebuy"]
    assert len(rebuys) == 1
    assert rebuys[0]["shares"] == 100
    assert _held(st) == 200
    assert st.stats["index_rebuy_shares"] == 100
    assert st.stats["index_rebuy_events"] == 1


def test_one_hundred_share_group_is_kept():
    st, hooks = _state(per=1_000.0)
    bars = _bars({CODE: 10.0})
    assert _held(st) == 100
    _cut(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    assert [t for t in st.trades if t["reason"] == "index_cut"] == []
    assert _held(st) == 100


def test_parking_lots_are_not_cut():
    st, hooks = _state()
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 10_000.0, 0, "2025-11-03")
    park_before = sum(int(lot.shares) for lot in st.positions[PARKING_SYMBOL])
    assert park_before >= 100
    bars = _bars({CODE: 10.0, PARKING_SYMBOL: 10.0})
    _cut(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    assert sum(int(lot.shares) for lot in st.positions[PARKING_SYMBOL]) == park_before
    assert all(t["code"] != PARKING_SYMBOL for t in st.trades if t["reason"] == "index_cut")


def test_version6_52_does_not_cut():
    st, hooks = _state(book="version6_52")
    bars = _bars({CODE: 10.0})
    _cut(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    assert [t for t in st.trades if t["reason"] == "index_cut"] == []
    assert _held(st) == 200


def test_s8_adds_are_blocked_while_gated():
    blocked = {"on": True}

    def allow(_day):
        return not blocked["on"]

    hooks = apply_csv_strategy("version6_53", name_budget=BUDGET)
    hooks["allow_new_name"] = allow
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    assert execute_buy(st, CODE, 10.0, 2_000.0, 0, "2025-11-03")
    assert s8_policy(st)["index_blocks_s8_add"] is True
    run_step_adds_day(
        st,
        day_i=1,
        day="2025-11-04",
        ds="20251104",
        names={},
        buy_quote_for=lambda _c: (11.0, [11.0]),
        sizing="per_name",
        name_budget=BUDGET,
    )
    assert [t for t in st.trades if str(t["reason"]).startswith("add:")] == []
    blocked["on"] = False
    run_step_adds_day(
        st,
        day_i=2,
        day="2025-11-05",
        ds="20251105",
        names={},
        buy_quote_for=lambda _c: (11.0, [11.0]),
        sizing="per_name",
        name_budget=BUDGET,
    )
    assert [t for t in st.trades if t["reason"] == "add:tranche"]


def test_pool_buy_skips_instead_of_raise_when_open_cover_left_short():
    st, _hooks = _state()
    st.cash = 200.0
    st.stats["parking_open_cover"] = True
    run_pool_buys_day(
        st,
        {},
        day_i=1,
        day="2025-11-04",
        ds="20251104",
        pool_days={"20251104": [CODE]},
        daily_quota=1_000_000.0,
        names={},
        allow_add=True,
        buy_gate=None,
        buy_quote_for=lambda _c: (10.0, [10.0]),
        sizing="per_name",
        name_budget=BUDGET,
        qlib_limit_pct=0.50,
        allow_new_name=lambda _d: True,
    )
    assert st.stats.get("skip_cash", 0) >= 1
    assert not [
        t for t in st.trades
        if t["side"] == "BUY" and t["date"] == "20251104" and t["reason"] == "pool"
    ]
