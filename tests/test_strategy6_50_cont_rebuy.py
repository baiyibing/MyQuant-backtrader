# -*- coding: utf-8 -*-
"""6.50：延续档 step 止损清仓后，股价回到该档 +20 个百分点再买 1 个基数。"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.csv_ledger import (
    bind_account_fee_schedule,
    configure_s8,
    execute_buy,
    execute_parking_buy,
    exit_positions,
    is_parking_lot,
    s8_policy,
)
from backtest.research.csv_simulate_loop import (
    append_equity_and_eod_marks,
    init_sim_state,
    run_parking_open_cover_day,
    run_parking_rebalance_day,
    run_step_adds_day,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_50_rules import (
    CONT_FROM_RISE,
    CONT_STOP_REBUY_FRAC,
    CONT_STOP_REBUY_LIFT,
    CONT_STOP_REBUY_OPEN_FRAC,
    CONT_STOP_REBUY_WITH_SCHEDULE,
    MIN_LOT_TOP_UP,
    OPEN_FRAC,
    PARKING_BUFFER,
    PARKING_EXECUTE,
    PARKING_FRAC,
    PARKING_OPEN_COVER,
    PARKING_SYMBOL,
    due_cont_rebuy_rise,
    is_continuation_rise,
)

CODE = "600000.SH"
BUDGET = 10_000.0


def test_cont_rebuy_pure_functions():
    assert is_continuation_rise(0.40)
    assert not is_continuation_rise(0.20)
    assert due_cont_rebuy_rise([0.60], 17.9, 10.0) is None
    assert due_cont_rebuy_rise([0.60], 18.0, 10.0) == pytest.approx(0.60)
    assert CONT_FROM_RISE == pytest.approx(0.40)
    assert CONT_STOP_REBUY_LIFT == pytest.approx(0.20)
    assert CONT_STOP_REBUY_FRAC == pytest.approx(1.0)
    assert CONT_STOP_REBUY_OPEN_FRAC == pytest.approx(OPEN_FRAC)
    assert CONT_STOP_REBUY_WITH_SCHEDULE is True
    assert PARKING_FRAC == pytest.approx(0.80)
    assert PARKING_BUFFER == pytest.approx(1_000_000)
    assert PARKING_EXECUTE is True
    assert PARKING_OPEN_COVER is True
    hooks = apply_csv_strategy("version6_50")
    assert hooks["parking_frac"] == pytest.approx(0.80)
    assert hooks["parking_execute"] is True
    assert hooks["parking_open_cover"] is True
    assert hooks["cont_stop_rebuy_open_frac"] == pytest.approx(0.20)
    assert hooks["cont_stop_rebuy_with_schedule"] is True
    assert MIN_LOT_TOP_UP is True
    assert hooks["min_lot_top_up"] is True
    hooks47 = apply_csv_strategy("version6_47")
    assert hooks47["parking_frac"] == pytest.approx(0.80)
    assert hooks47.get("parking_execute") is True
    assert hooks47.get("parking_open_cover") is not True
    assert hooks47["parking_buffer"] == pytest.approx(2_000_000)
    assert hooks47["min_lot_top_up"] is False
    assert apply_csv_strategy("version6_48").get("parking_execute") is not True
    assert apply_csv_strategy("version6_48")["parking_frac"] == pytest.approx(0.60)


def _state(book="version6_50", cash=2_000_000.0):
    hooks = apply_csv_strategy(book, name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, CODE, 10.0, 2_000.0, 0, "2025-11-03")
    group = next(iter(st.book_state["s8_independent"]["groups"].values()))
    return st, hooks, group


def _add(st, hooks, day_i, day, ds, px):
    run_step_adds_day(
        st,
        day_i=day_i,
        day=day,
        ds=ds,
        names={},
        buy_quote_for=lambda _c: (px, [px]),
        sizing="per_name",
        name_budget=BUDGET,
    )


def _buys(st, reason=None):
    return [
        t for t in st.trades if t["side"] == "BUY" and (reason is None or t["reason"] == reason)
    ]


def test_cont_tranche_stop_rebuy_one_base_at_plus_20pp():
    from backtest.research.minute_cash_order import step_stop_exits

    st, hooks, group = _state()
    group.executed_steps = 3  # next slot is A0*1.60 continuation
    _add(st, hooks, 1, "2025-11-04", "20251104", 16.0)
    tranches = _buys(st, "add:tranche")
    assert len(tranches) == 1
    assert tranches[0]["price"] == pytest.approx(16.0)
    assert group.executed_steps == 4
    assert group.cont_open
    cont_lot = next(lot for lot in st.positions[CODE] if lot.lot_id in group.cont_open)
    expected_shares = cont_lot.shares

    (pos,) = exit_positions(st, CODE, 2)
    sold = step_stop_exits(
        st,
        CODE,
        pos,
        14.4,
        "2025-11-05",
        2,
        (100.0, 5.0),
        step_stop_pct=0.10,
        hm=600,
    )
    assert sold == 1
    assert st.stats.get("arm_cont_rebuy") == 1
    assert group.cont_rebuy_armed == [pytest.approx(0.60)]
    assert CODE in st.positions  # first lot remains

    _add(st, hooks, 3, "2025-11-06", "20251106", 17.0)
    assert _buys(st, "add:cont_rebuy") == []
    assert _buys(st, "add:tranche") == tranches

    _add(st, hooks, 4, "2025-11-07", "20251107", 18.0)
    rebuys = _buys(st, "add:cont_rebuy")
    opens = _buys(st, "add:cont_rebuy_open")
    assert len(rebuys) == 1
    assert len(opens) == 1
    assert rebuys[0]["price"] == pytest.approx(18.0)
    assert opens[0]["price"] == pytest.approx(18.0)
    assert rebuys[0]["shares"] == int(BUDGET / 18.0 / 100) * 100
    assert opens[0]["shares"] == int(BUDGET * OPEN_FRAC / 18.0 / 100) * 100
    later = [t for t in _buys(st, "add:tranche") if t["date"] == "20251107"]
    assert len(later) == 1
    assert later[0]["shares"] == int(BUDGET * 42.0 / 18.0 / 100) * 100
    assert group.executed_steps == 5  # schedule tranche consumes the ladder
    assert group.cont_rebuy_done == [pytest.approx(0.60)]
    assert group.cont_rebuy_armed == []
    assert st.stats.get("add_cont_rebuy") == 1
    assert st.stats.get("add_cont_rebuy_open") == 1
    assert expected_shares > 0

    _add(st, hooks, 5, "2025-11-08", "20251108", 18.0)
    assert len(_buys(st, "add:cont_rebuy")) == 1
    assert len(_buys(st, "add:cont_rebuy_open")) == 1


def test_early_schedule_lots_do_not_arm_rebuy():
    from backtest.research.minute_cash_order import step_stop_exits

    st, hooks, group = _state()
    _add(st, hooks, 1, "2025-11-04", "20251104", 11.0)
    assert group.executed_steps == 1
    assert group.cont_open == {}
    step = next(lot for lot in st.positions[CODE] if lot.is_step)
    (pos,) = exit_positions(st, CODE, 2)
    step_stop_exits(
        st,
        CODE,
        pos,
        step.cost * 0.90,
        "2025-11-05",
        2,
        (100.0, 5.0),
        step_stop_pct=0.10,
        hm=600,
    )
    assert st.stats.get("arm_cont_rebuy", 0) == 0
    assert group.cont_rebuy_armed == []


@pytest.mark.parametrize("book", ["version6_46", "version6_47", "version6_48"])
def test_sibling_books_keep_the_42x_schedule_at_the_same_print(book):
    from backtest.research.minute_cash_order import step_stop_exits

    st, hooks, group = _state(book)
    group.executed_steps = 3
    _add(st, hooks, 1, "2025-11-04", "20251104", 16.0)
    assert group.cont_open == {}
    (pos,) = exit_positions(st, CODE, 2)
    step_stop_exits(
        st,
        CODE,
        pos,
        14.4,
        "2025-11-05",
        2,
        (100.0, 5.0),
        step_stop_pct=0.10,
        hm=600,
    )
    _add(st, hooks, 4, "2025-11-07", "20251107", 18.0)
    assert _buys(st, "add:cont_rebuy") == []
    later = [t for t in _buys(st, "add:tranche") if t["date"] == "20251107"]
    assert len(later) == 1
    assert later[0]["shares"] == int(BUDGET * 42.0 / 18.0 / 100) * 100


def test_version6_50_industry_tops_up_short_lot_from_cash_pool():
    from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
    from backtest.research.rule_profile import INDUSTRY

    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    st.rule_profile = INDUSTRY
    bind_account_fee_schedule(st, INDUSTRY_ACCOUNT_FEES)
    assert execute_buy(st, CODE, 25.0, 2_000.0, 0, "2025-11-03")
    buy = [t for t in st.trades if t["side"] == "BUY"][-1]
    assert buy["shares"] == 100
    assert buy["notional"] == pytest.approx(2500.0)
    assert st.stats["supplementary_used"] == pytest.approx(500.0)


def test_version6_50_can_turn_min_lot_top_up_off():
    from argparse import ArgumentParser
    from pathlib import Path

    from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
    from backtest.research.csv_strategy_books import (
        add_csv_backtest_common_args,
        csv_run_kwargs_from_args,
    )
    from backtest.research.rule_profile import INDUSTRY

    hooks = apply_csv_strategy("version6_50", min_lot_top_up=False)
    assert hooks["min_lot_top_up"] is False
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    st.rule_profile = INDUSTRY
    bind_account_fee_schedule(st, INDUSTRY_ACCOUNT_FEES)
    configure_s8(st, hooks)
    assert s8_policy(st)["min_lot_top_up"] is False
    assert not execute_buy(st, CODE, 25.0, 2_000.0, 0, "2025-11-03")
    assert st.stats.get("skip_min_lot_budget") == 1
    assert st.stats["min_lot_top_up"] is False
    assert st.stats.get("supplementary_used", 0.0) == 0.0

    parser = ArgumentParser()
    add_csv_backtest_common_args(
        parser,
        repo=Path("."),
        end_default="20261006",
        cash_total_default=21_000_000,
        daily_quota_default=1_000_000,
    )
    omitted = parser.parse_args(["--strategy", "version6_50"])
    assert omitted.min_lot_top_up is None
    assert "min_lot_top_up" not in csv_run_kwargs_from_args(omitted)
    off = parser.parse_args(["--strategy", "version6_50", "--no-min-lot-top-up"])
    assert csv_run_kwargs_from_args(off)["min_lot_top_up"] is False
    on = parser.parse_args(["--strategy", "version6_50", "--min-lot-top-up"])
    assert csv_run_kwargs_from_args(on)["min_lot_top_up"] is True
    assert apply_csv_strategy("version6_51", min_lot_top_up=False)["min_lot_top_up"] is False
    assert apply_csv_strategy("version6_52", min_lot_top_up=False)["min_lot_top_up"] is False
    assert apply_csv_strategy("version6_53", min_lot_top_up=False)["min_lot_top_up"] is False


def test_version6_47_industry_still_skips_below_one_lot():
    from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
    from backtest.research.rule_profile import INDUSTRY

    hooks = apply_csv_strategy("version6_47", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    st.rule_profile = INDUSTRY
    bind_account_fee_schedule(st, INDUSTRY_ACCOUNT_FEES)
    assert not execute_buy(st, CODE, 25.0, 2_000.0, 0, "2025-11-03")
    assert st.stats.get("skip_min_lot_budget") == 1
    assert st.stats.get("supplementary_used", 0.0) == 0.0


def test_version6_47_does_not_enable_cont_rebuy():
    hooks = apply_csv_strategy("version6_47")
    assert hooks.get("cont_stop_rebuy") is False
    from backtest.research import strategy6_47_rules
    assert not hasattr(strategy6_47_rules, "CONT_STOP_REBUY")
    assert not hasattr(strategy6_47_rules, "due_cont_rebuy_rise")


def _parking_bars(px=10.0):
    idx = pd.to_datetime(["2025-11-03", "2025-11-04", "2025-11-05"])
    return {
        PARKING_SYMBOL: pd.DataFrame(
            {"open": px, "high": px, "low": px, "close": px, "volume": 1_000_000},
            index=idx,
        )
    }


def _open_cover(st, hooks, day_i, day, ds, bars, cash=None):
    if cash is not None:
        st.cash = float(cash)
    run_parking_open_cover_day(
        st,
        hooks,
        day_i=day_i,
        day=pd.Timestamp(day),
        ds=ds,
        names={},
        daily_bars=bars,
    )


def _rebalance(st, hooks, day_i, day, ds, bars, cash=None):
    if cash is not None:
        st.cash = float(cash)
    run_parking_rebalance_day(
        st,
        hooks,
        day_i=day_i,
        day=pd.Timestamp(day),
        ds=ds,
        names={},
        daily_bars=bars,
    )


def test_parking_rebalance_buys_idle_fraction():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000_000.0, bars_loaded=1, pool_days={})[0]
    bars = _parking_bars()
    _rebalance(st, hooks, 1, "2025-11-04", "20251104", bars)
    park = [t for t in st.trades if t["reason"] == "parking:rebalance"]
    assert len(park) == 1
    assert park[0]["side"] == "BUY"
    assert park[0]["code"] == PARKING_SYMBOL
    assert park[0]["shares"] == 720_000
    lots = st.positions[PARKING_SYMBOL]
    assert len(lots) == 1
    assert is_parking_lot(st, lots[0])
    assert PARKING_SYMBOL not in (s8_policy(st) or {}).get("groups", {})
    assert exit_positions(st, PARKING_SYMBOL, 1) == []
    append_equity_and_eod_marks(
        st,
        ds="20251104",
        day=pd.Timestamp("2025-11-04"),
        calendar_last=pd.Timestamp("2025-11-05"),
        mark_bars=bars,
    )
    _ds, equity = st.equity_curve[-1]
    assert equity == pytest.approx(st.cash + 720_000 * 10.0)


def test_parking_flattens_when_idle_at_or_below_buffer():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 1_000_000.0, 0, "2025-11-03")
    held = sum(p.shares for p in st.positions[PARKING_SYMBOL])
    _rebalance(st, hooks, 1, "2025-11-04", "20251104", _parking_bars(), cash=0.0)
    sells = [t for t in st.trades if t["side"] == "SELL" and t["reason"] == "parking:rebalance"]
    assert sells
    assert sum(t["shares"] for t in sells) == held
    assert PARKING_SYMBOL not in st.positions


def test_parking_same_day_buy_is_t1_locked():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 1_000_000.0, 1, "2025-11-04")
    _rebalance(st, hooks, 1, "2025-11-04", "20251104", _parking_bars(), cash=100_000.0)
    assert st.stats.get("skip_parking_t1") == 1
    assert PARKING_SYMBOL in st.positions
    assert not any(t["side"] == "SELL" for t in st.trades)


def test_parking_no_bar_is_noop():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000_000.0, bars_loaded=1, pool_days={})[0]
    _rebalance(st, hooks, 1, "2025-11-04", "20251104", {})
    assert st.stats.get("skip_parking_no_bar") == 1
    assert PARKING_SYMBOL not in st.positions
    assert not st.trades


def test_parking_open_cover_skips_buy_instead_of_raising_when_still_short():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000.0, bars_loaded=1, pool_days={})[0]
    st.cash = 100.0
    assert not execute_buy(st, CODE, 10.0, 2_000.0, 1, "2025-11-04")
    assert st.stats.get("skip_cash") == 1
    assert not any(t["side"] == "BUY" and t["code"] == CODE for t in st.trades)


def test_parking_unparks_to_fund_strategy_buy():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000_000.0, bars_loaded=1, pool_days={})[0]
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 6_400_000.0, 0, "2025-11-03")
    st.cash = 100.0
    st.book_state["parking_session"] = {
        "symbol": PARKING_SYMBOL,
        "px": 10.0,
        "day_i": 1,
        "day": pd.Timestamp("2025-11-04"),
        "ds": "20251104",
        "limits": (11.0, 9.0),
    }
    assert execute_buy(st, CODE, 10.0, 2_000.0, 1, "2025-11-04")
    unpark = [t for t in st.trades if t["reason"] == "parking:unpark"]
    assert unpark
    assert st.stats.get("parking_unpark") == 1
    assert any(t["code"] == CODE and t["side"] == "BUY" for t in st.trades)


def test_parking_open_cover_sells_only_the_cash_gap():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000_000.0, bars_loaded=1, pool_days={})[0]
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 2_000_000.0, 0, "2025-11-03")
    held = sum(p.shares for p in st.positions[PARKING_SYMBOL])
    _open_cover(st, hooks, 1, "2025-11-04", "20251104", _parking_bars(), cash=100_000.0)
    covers = [t for t in st.trades if t["reason"] == "parking:open_cover"]
    assert covers
    assert all(t["side"] == "SELL" for t in covers)
    assert all(t.get("price_rule") == "parking_open" for t in covers)
    assert st.cash >= PARKING_BUFFER
    left = sum(p.shares for p in st.positions.get(PARKING_SYMBOL, []))
    assert 0 < left < held
    assert st.stats.get("parking_open_cover_days") == 1


def test_parking_open_cover_skips_when_cash_already_covers_buffer():
    hooks = apply_csv_strategy("version6_50", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000_000.0, bars_loaded=1, pool_days={})[0]
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 2_000_000.0, 0, "2025-11-03")
    _open_cover(st, hooks, 1, "2025-11-04", "20251104", _parking_bars(), cash=2_000_000.0)
    assert not any(t["reason"] == "parking:open_cover" for t in st.trades)
    assert PARKING_SYMBOL in st.positions


def test_version6_47_executes_parking_rebalance_at_80pct():
    hooks = apply_csv_strategy("version6_47", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000_000.0, bars_loaded=1, pool_days={})[0]
    _rebalance(st, hooks, 1, "2025-11-04", "20251104", _parking_bars())
    park = [t for t in st.trades if t.get("reason") == "parking:rebalance"]
    assert len(park) == 1
    assert park[0]["side"] == "BUY"
    assert park[0]["shares"] == 640_000
    _open_cover(st, hooks, 1, "2025-11-04", "20251104", _parking_bars())
    assert not any(t.get("reason") == "parking:open_cover" for t in st.trades)


def test_version6_48_does_not_execute_parking():
    hooks = apply_csv_strategy("version6_48", name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=10_000_000.0, bars_loaded=1, pool_days={})[0]
    _rebalance(st, hooks, 1, "2025-11-04", "20251104", _parking_bars())
    _open_cover(st, hooks, 1, "2025-11-04", "20251104", _parking_bars())
    assert PARKING_SYMBOL not in st.positions
    assert not any(t.get("reason") == "parking:rebalance" for t in st.trades)
    assert not any(t.get("reason") == "parking:open_cover" for t in st.trades)
