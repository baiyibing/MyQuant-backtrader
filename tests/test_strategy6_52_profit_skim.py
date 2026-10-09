# -*- coding: utf-8 -*-
"""6.52：抽离只动闲置；欠账后补；加仓先卖闲置停泊，不够再动锁仓后补回。"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.csv_ledger import (
    execute_buy,
    execute_parking_buy,
    is_principal_lot,
    sleeve_parking_lots,
)
from backtest.research.csv_simulate_loop import (
    bind_parking_session,
    extra_load_codes_for_strategy,
    init_sim_state,
    run_parking_rebalance_day,
    run_profit_skim_day,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_51_rules import PARKING_SYMBOL
from backtest.research.strategy6_52_rules import (
    PROFIT_SKIM,
    PROFIT_SKIM_FRAC,
    PROFIT_SKIM_KEEP_IDLE,
    PROFIT_SKIM_PRO_RATA,
    PROFIT_SKIM_STEP,
    PROFIT_SKIM_TO_PARKING,
)

CODE = "600000.SH"
CODE2 = "600001.SH"
BASE = 1_000_000.0


def test_profit_skim_hooks_and_scope():
    assert PROFIT_SKIM is True
    assert PROFIT_SKIM_STEP == pytest.approx(0.20)
    assert PROFIT_SKIM_FRAC == pytest.approx(0.20)
    assert PROFIT_SKIM_PRO_RATA is True
    assert PROFIT_SKIM_KEEP_IDLE is True
    assert PROFIT_SKIM_TO_PARKING is True
    hooks52 = apply_csv_strategy("version6_52")
    hooks51 = apply_csv_strategy("version6_51")
    assert hooks52["profit_skim"] is True
    assert hooks52["profit_skim_to_parking"] is True
    assert hooks51.get("profit_skim") is not True
    assert extra_load_codes_for_strategy("version6_52") == {PARKING_SYMBOL}


def _state(book="version6_52", cash=BASE):
    hooks = apply_csv_strategy(book)
    st = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})[0]
    return st, hooks


def _skim(st, hooks, day_i=1, day="2025-11-04", ds="20251104", bars=None):
    run_profit_skim_day(
        st,
        hooks,
        day_i=day_i,
        day=pd.Timestamp(day),
        ds=ds,
        names={},
        daily_bars=bars or {},
        qlib_limit_pct=0.50,
    )


def _bars(px_by_code: dict[str, float], days=("2025-11-03", "2025-11-04", "2025-11-05")):
    idx = pd.to_datetime(list(days))
    out = {}
    for code, px in px_by_code.items():
        out[code] = pd.DataFrame(
            {"open": px, "high": px, "low": px, "close": px, "volume": 1_000_000},
            index=idx,
        )
    return out


def _principal_shares(st) -> int:
    return sum(
        int(lot.shares)
        for lot in st.positions.get(PARKING_SYMBOL, [])
        if is_principal_lot(st, lot)
    )


def _sleeve_shares(st) -> int:
    return sum(int(lot.shares) for lot in sleeve_parking_lots(st, PARKING_SYMBOL))


def test_cash_only_without_bar_is_pending():
    st, hooks = _state()
    st.cash = 1_200_000.0
    _skim(st, hooks)
    assert st.cash == pytest.approx(1_200_000.0)
    assert st.stats.get("profit_skim_withdrawn", 0.0) == pytest.approx(0.0)
    assert st.stats.get("profit_skim_parked", 0.0) == pytest.approx(0.0)
    assert int(st.stats.get("profit_skim_pending", 0)) >= 1


def test_idle_cash_above_buffer_buys_600036():
    st, hooks = _state()
    st.cash = 1_200_000.0
    bars = _bars({PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    parks = [
        t for t in st.trades
        if t["side"] == "BUY" and t.get("reason") == "parking:profit_skim"
    ]
    assert parks
    assert _principal_shares(st) >= 100
    assert not [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats.get("profit_skim_withdrawn", 0.0) == pytest.approx(0.0)
    assert st.stats["profit_skim_parked"] == pytest.approx(200_000.0, abs=2_000.0)
    assert st.cash == pytest.approx(1_000_000.0, abs=2_000.0)


def test_below_threshold_is_noop():
    st, hooks = _state()
    st.cash = 1_199_999.0
    _skim(st, hooks)
    assert st.cash == pytest.approx(1_199_999.0)
    assert st.stats.get("profit_skim_events", 0) == 0


def test_version6_51_does_not_skim():
    st, hooks = _state("version6_51")
    st.cash = 1_200_000.0
    _skim(st, hooks)
    assert st.cash == pytest.approx(1_200_000.0)
    assert st.stats.get("profit_skim_events", 0) == 0


def test_transfers_idle_parking_without_selling_strategy():
    st, hooks = _state()
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 400_000.0, 0, "2025-11-03")
    assert execute_buy(
        st, CODE, 10.0, 400_000.0, 0, "2025-11-03", entry_signal_date="2025-11-03"
    )
    sleeve0 = _sleeve_shares(st)
    cash0 = float(st.cash)
    bars = _bars({PARKING_SYMBOL: 15.0, CODE: 15.0})
    _skim(st, hooks, bars=bars)
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert not sells
    assert _principal_shares(st) >= 100
    assert _sleeve_shares(st) < sleeve0
    assert st.cash == pytest.approx(cash0, abs=2.0)
    assert st.stats.get("profit_skim_transferred", 0.0) > 0
    assert st.stats.get("profit_skim_withdrawn", 0.0) == pytest.approx(0.0)
    assert st.stats["profit_skim_parked"] == pytest.approx(200_000.0, abs=2_000.0)


def test_idle_short_does_not_sell_strategy():
    st, hooks = _state()
    assert execute_buy(
        st, CODE, 10.0, 800_000.0, 0, "2025-11-03", entry_signal_date="2025-11-03"
    )
    cash0 = float(st.cash)
    bars = _bars({CODE: 13.0, PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert not sells
    assert st.cash == pytest.approx(cash0)
    assert st.stats.get("profit_skim_parked", 0.0) == pytest.approx(0.0)
    assert float(st.stats.get("profit_skim_pending_notional", 0.0)) > 0
    assert int(st.stats.get("profit_skim_pending", 0)) >= 1


def test_later_idle_completes_pending_before_rebalance():
    st, hooks = _state()
    st.cash = 1_200_000.0
    _skim(st, hooks)
    assert _principal_shares(st) == 0
    assert float(st.stats.get("profit_skim_pending_notional", 0.0)) > 0
    bars = _bars({PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    assert not [t for t in st.trades if t["side"] == "SELL"]
    assert _principal_shares(st) >= 100
    assert st.stats["profit_skim_parked"] == pytest.approx(200_000.0, abs=2_000.0)
    cash_after_skim = float(st.cash)
    run_parking_rebalance_day(
        st,
        hooks,
        day_i=1,
        day=pd.Timestamp("2025-11-04"),
        ds="20251104",
        names={},
        daily_bars=bars,
        qlib_limit_pct=0.50,
    )
    assert st.stats["profit_skim_parked"] == pytest.approx(200_000.0, abs=2_000.0)
    assert float(st.cash) <= cash_after_skim + 1.0


def test_rebalance_does_not_flatten_principal():
    st, hooks = _state()
    st.cash = 1_200_000.0
    bars = _bars({PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    principal0 = _principal_shares(st)
    assert principal0 >= 100
    run_parking_rebalance_day(
        st,
        hooks,
        day_i=1,
        day=pd.Timestamp("2025-11-04"),
        ds="20251104",
        names={},
        daily_bars=bars,
        qlib_limit_pct=0.50,
    )
    assert _principal_shares(st) == principal0
    flatten = [
        t for t in st.trades
        if t["side"] == "SELL" and t.get("reason") == "parking:rebalance"
    ]
    assert not flatten


def test_already_paid_rung_does_not_repeat():
    st, hooks = _state()
    st.cash = 1_200_000.0
    bars = _bars({PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    parked = float(st.stats["profit_skim_parked"])
    principal = _principal_shares(st)
    assert parked > 0
    _skim(st, hooks, bars=bars)
    assert st.stats["profit_skim_parked"] == pytest.approx(parked)
    assert _principal_shares(st) == principal
    assert st.stats["profit_skim_events"] == 1


def test_add_shortfall_sells_sleeve_first():
    st, hooks = _state()
    st.cash = 1_200_000.0
    bars = _bars({CODE: 10.0, PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    assert execute_buy(
        st, CODE, 10.0, 10_000.0, 0, "2025-11-03", entry_signal_date="2025-11-03"
    )
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 200_000.0, 0, "2025-11-03")
    sleeve0 = _sleeve_shares(st)
    principal0 = _principal_shares(st)
    assert principal0 >= 100
    assert sleeve0 >= 100
    st.cash = 1_000.0
    bind_parking_session(
        st,
        hooks,
        day_i=2,
        day=pd.Timestamp("2025-11-05"),
        ds="20251105",
        names={},
        daily_bars=bars,
    )
    filled = execute_buy(
        st,
        CODE,
        10.0,
        150_000.0,
        2,
        pd.Timestamp("2025-11-05"),
        reason="add:tranche",
        position_id=f"{CODE}@2025-11-03",
        entry_signal_date="2025-11-03",
    )
    assert filled
    unpark = [t for t in st.trades if t.get("reason") == "parking:unpark"]
    assert unpark
    assert all(t["code"] == PARKING_SYMBOL for t in unpark)
    assert _sleeve_shares(st) < sleeve0
    assert _principal_shares(st) == principal0
    assert float(st.stats.get("profit_skim_lock_drawn", 0.0)) == pytest.approx(0.0)


def test_add_shortfall_uses_lock_after_sleeve():
    st, hooks = _state()
    st.cash = 1_200_000.0
    bars = _bars({CODE: 10.0, PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    assert execute_buy(
        st, CODE, 10.0, 10_000.0, 0, "2025-11-03", entry_signal_date="2025-11-03"
    )
    assert execute_parking_buy(st, PARKING_SYMBOL, 10.0, 50_000.0, 0, "2025-11-03")
    sleeve0 = _sleeve_shares(st)
    principal0 = _principal_shares(st)
    assert principal0 >= 100
    assert sleeve0 >= 100
    st.cash = 1_000.0
    bind_parking_session(
        st,
        hooks,
        day_i=2,
        day=pd.Timestamp("2025-11-05"),
        ds="20251105",
        names={},
        daily_bars=bars,
    )
    filled = execute_buy(
        st,
        CODE,
        10.0,
        150_000.0,
        2,
        pd.Timestamp("2025-11-05"),
        reason="add:tranche",
        position_id=f"{CODE}@2025-11-03",
        entry_signal_date="2025-11-03",
    )
    assert filled
    assert _sleeve_shares(st) < sleeve0
    assert _principal_shares(st) < principal0
    assert float(st.stats.get("profit_skim_lock_drawn", 0.0)) > 0


def test_later_idle_restores_lock_after_unpark():
    st, hooks = _state()
    st.cash = 1_200_000.0
    bars = _bars({CODE: 10.0, PARKING_SYMBOL: 10.0})
    _skim(st, hooks, bars=bars)
    assert execute_buy(
        st, CODE, 10.0, 10_000.0, 0, "2025-11-03", entry_signal_date="2025-11-03"
    )
    st.cash = 1_000.0
    bind_parking_session(
        st,
        hooks,
        day_i=2,
        day=pd.Timestamp("2025-11-05"),
        ds="20251105",
        names={},
        daily_bars=bars,
    )
    assert execute_buy(
        st,
        CODE,
        10.0,
        150_000.0,
        2,
        pd.Timestamp("2025-11-05"),
        reason="add:tranche",
        position_id=f"{CODE}@2025-11-03",
        entry_signal_date="2025-11-03",
    )
    drawn = float(st.stats.get("profit_skim_lock_drawn", 0.0))
    principal1 = _principal_shares(st)
    assert drawn > 0
    st.cash = 1_500_000.0
    _skim(st, hooks, day_i=2, day="2025-11-05", ds="20251105", bars=bars)
    assert float(st.stats.get("profit_skim_lock_restored", 0.0)) > 0
    assert float(st.stats.get("profit_skim_lock_drawn", 0.0)) < drawn
    assert _principal_shares(st) > principal1
    assert any(t.get("reason") == "parking:lock_restore" for t in st.trades)
    assert not [t for t in st.trades if t.get("reason") == "profit_skim"]
