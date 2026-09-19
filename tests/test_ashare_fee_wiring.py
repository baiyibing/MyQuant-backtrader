# -*- coding: utf-8 -*-
"""P3 δ1 Slice B: research fee-wiring contract pins (data-free / synthetic only).

Landing file for plan-industry-align-p3-fees §7 Slice B / §8 (MC-1).
Formula-only coverage stays in ``tests/test_ashare_fees.py``; fence/predicates
are side evidence, not wiring closure.
"""

from __future__ import annotations

from datetime import date
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from backtest.research.ashare_fees import (
    BILATERAL_10BP,
    COMMISSION,
    DEFAULT_SCHEDULE,
    FeeSchedule,
    QLIB_CLOSE_COST,
    QLIB_MIN_COST,
    QLIB_OPEN_COST,
    QLIB_PORTANA,
    trade_commission,
)
import backtest.research.csv_daily_backtest as daily_sim
import backtest.research.csv_minute_backtest as minute_sim
from backtest.research.csv_ledger import (
    Position as BookPosition,
    SimState,
    _sell,
    execute_buy,
    trade_commission as ledger_trade_commission,
)
from backtest.research.csv_minute_backtest_v7 import (
    Lot,
    Position as V7Position,
    SimResult,
    _buy as v7_buy,
    _sell_lots,
    simulate_v7,
)
from backtest.research.csv_simulate_loop import trade_commission as loop_trade_commission


CODE = "600000.SH"
DAYS = ["2025-11-03", "2025-11-04", "2025-11-05"]


def _daily_bars(
    days: list[str], rows: list[tuple[float, float, float, float]]
) -> dict[str, pd.DataFrame]:
    idx = pd.to_datetime(days)
    pre = pd.Timestamp(days[0]) - pd.Timedelta(days=2)
    frame = pd.DataFrame(
        {
            "open": [10.0] + [r[0] for r in rows],
            "high": [10.0] + [r[1] for r in rows],
            "low": [10.0] + [r[2] for r in rows],
            "close": [10.0] + [r[3] for r in rows],
        },
        index=pd.DatetimeIndex([pre]).append(idx),
    ).astype(np.float64)
    return {CODE: frame}


def _minute_day(date_s: str, rows: list[tuple]) -> pd.DataFrame:
    idx, opens, highs, lows, closes = [], [], [], [], []
    d = pd.Timestamp(date_s)
    for hm, oo, hh, ll, cc in rows:
        hour, minute = divmod(int(hm), 100)
        idx.append(d + pd.Timedelta(hours=hour, minutes=minute))
        opens.append(oo)
        highs.append(hh)
        lows.append(ll)
        closes.append(cc)
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=pd.DatetimeIndex(idx),
    ).astype(np.float64)
    return minute_sim._annotate(df)


def _minute_daily(dates: list[str], closes: list[float], prev: float = 10.0) -> pd.DataFrame:
    pre = pd.Timestamp(dates[0]) - pd.Timedelta(days=2)
    idx = pd.DatetimeIndex([pre] + [pd.Timestamp(d) for d in dates])
    px = [prev] + list(closes)
    return pd.DataFrame(
        {"open": px, "high": px, "low": px, "close": px}, index=idx
    ).astype(np.float64)


def test_dual_default_pointers_module_and_simstate():
    """DEFAULT_SCHEDULE is BILATERAL_10BP; book SimState floats match COMMISSION."""
    assert DEFAULT_SCHEDULE is BILATERAL_10BP
    assert BILATERAL_10BP.buy_rate == COMMISSION
    assert BILATERAL_10BP.sell_rate == COMMISSION
    assert BILATERAL_10BP.min_cost == 0.0

    st = SimState()
    assert (st.buy_cost_rate, st.sell_cost_rate, st.min_cost) == (
        COMMISSION,
        COMMISSION,
        0.0,
    )
    notional = 1_000.0
    assert trade_commission(notional, st.buy_cost_rate, st.min_cost) == pytest.approx(
        BILATERAL_10BP.buy_fee(notional)
    )
    assert trade_commission(notional, st.sell_cost_rate, st.min_cost) == pytest.approx(
        BILATERAL_10BP.sell_fee(notional)
    )


def test_formula_parity_at_ledger_and_loop_charge_sites():
    """Buy/sell charge sites and shared-loop import share ashare_fees.trade_commission."""
    assert ledger_trade_commission is trade_commission
    assert loop_trade_commission is trade_commission

    st = SimState(cash=2_000.0, buy_cost_rate=COMMISSION, sell_cost_rate=COMMISSION, min_cost=0.0)
    assert execute_buy(st, CODE, 10.0, 1_000.0, 0, "20251103")
    buy = st.trades[0]
    assert buy["commission"] == pytest.approx(
        trade_commission(buy["notional"], st.buy_cost_rate, st.min_cost)
    )

    pos = st.positions[CODE][0]
    _sell(st, CODE, pos, 10.0, "20251104", "force_sell")
    sell = next(t for t in st.trades if t["side"] == "SELL")
    assert sell["commission"] == pytest.approx(
        trade_commission(sell["notional"], st.sell_cost_rate, st.min_cost)
    )


def test_daily_simulate_default_and_qlib_override_two_state():
    """Daily opt-in fee kwargs reach charge sites; default stays bilateral 10bp."""
    bars = _daily_bars(DAYS, [(10.0, 10.0, 10.0, 10.0)] * 3)
    pool = {"20251103": [CODE]}

    st_default = daily_sim.simulate(
        bars, pool, "20251103", "20251105", strategy="version6"
    )
    buy_d = next(t for t in st_default.trades if t["side"] == "BUY")
    assert st_default.stats["buy_cost_rate"] == COMMISSION
    assert st_default.stats["sell_cost_rate"] == COMMISSION
    assert st_default.stats["min_cost"] == 0.0
    assert buy_d["commission"] == pytest.approx(
        trade_commission(buy_d["notional"], COMMISSION, 0.0)
    )

    st_qlib = daily_sim.simulate(
        bars,
        pool,
        "20251103",
        "20251105",
        strategy="version6",
        buy_cost_rate=QLIB_OPEN_COST,
        sell_cost_rate=QLIB_CLOSE_COST,
        min_cost=QLIB_MIN_COST,
    )
    buy_q = next(t for t in st_qlib.trades if t["side"] == "BUY")
    assert st_qlib.stats["buy_cost_rate"] == QLIB_OPEN_COST
    assert st_qlib.stats["sell_cost_rate"] == QLIB_CLOSE_COST
    assert st_qlib.stats["min_cost"] == QLIB_MIN_COST
    assert buy_q["commission"] == pytest.approx(
        trade_commission(buy_q["notional"], QLIB_OPEN_COST, QLIB_MIN_COST)
    )
    assert buy_q["commission"] == pytest.approx(QLIB_PORTANA.buy_fee(buy_q["notional"]))
    assert buy_q["commission"] != pytest.approx(buy_d["commission"])


def test_minute_simulate_inherits_simstate_default_rates():
    """Minute path has no fee kwargs; commissions follow SimState defaults."""
    dates = ["2025-11-03", "2025-11-04"]
    minute = {
        CODE: pd.concat(
            [
                _minute_day("2025-11-03", [(1455, 10.0, 10.0, 10.0, 10.0)]),
                _minute_day("2025-11-04", [(1455, 10.0, 10.0, 10.0, 10.0)]),
            ]
        )
    }
    daily = {CODE: _minute_daily(dates, [10.0, 10.0])}
    st = minute_sim.simulate(
        minute,
        daily,
        {"20251103": [CODE]},
        "20251103",
        "20251104",
        strategy="version6",
    )
    assert (st.buy_cost_rate, st.sell_cost_rate, st.min_cost) == (
        COMMISSION,
        COMMISSION,
        0.0,
    )
    buy = next(t for t in st.trades if t["side"] == "BUY")
    assert buy["commission"] == pytest.approx(
        trade_commission(buy["notional"], COMMISSION, 0.0)
    )


def test_v7_custom_fee_schedule_passthrough_without_monkeypatch():
    """simulate_v7 / _buy honor explicit FeeSchedule; do not patch DEFAULT_SCHEDULE."""
    assert DEFAULT_SCHEDULE is BILATERAL_10BP
    D1 = date(2026, 9, 1)
    minutes = {
        CODE: [
            {
                "date": D1,
                "hm": 895,
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
            }
        ]
    }
    daily = {CODE: {date(2026, 8, 31): 100.0, D1: 100.0}}

    custom = FeeSchedule(0.002, 0.003, 7.0)
    # trial: NAME_BUDGET * 0.20 / 100 → 2000 shares @ 100
    expected_debit = custom.debit_buy(2000 * 100.0)

    state_buy = SimResult(1_000_000.0)
    pos = v7_buy(
        state_buy,
        None,
        CODE,
        D1,
        895,
        100.0,
        0.20,
        "buy:trial",
        "trial",
        fee=custom,
    )
    assert pos is not None
    assert state_buy.cash == pytest.approx(1_000_000.0 - expected_debit)

    st_portana = simulate_v7(
        minutes, daily, {D1: [CODE]}, [D1], fee=QLIB_PORTANA
    )
    assert st_portana.cash == pytest.approx(
        21_000_000.0 - QLIB_PORTANA.debit_buy(2000 * 100.0)
    )

    st_default = simulate_v7(minutes, daily, {D1: [CODE]}, [D1])
    assert st_default.cash == pytest.approx(
        21_000_000.0 - BILATERAL_10BP.debit_buy(2000 * 100.0)
    )
    # Module default pointer must remain identity-stable (no monkeypatch).
    assert DEFAULT_SCHEDULE is BILATERAL_10BP


def test_floor_unit_two_lot_oracle_portana_schedule():
    """§2.4 / MC-2: book 10/+1990 vs v7 one-call 5/+1995 under QLIB_PORTANA sell."""
    # Book path: one floor per _sell call → 2 × max(1.5, 5) = 10; cash +1990
    book = SimState(cash=0.0, sell_cost_rate=QLIB_CLOSE_COST, min_cost=QLIB_MIN_COST)
    lot0 = BookPosition(CODE, 100, 10.0, 0, 10.0, lot_id=0)
    lot1 = BookPosition(CODE, 100, 10.0, 0, 10.0, lot_id=1)
    book.positions[CODE] = [lot0, lot1]
    _sell(book, CODE, lot0, 10.0, "20251104", "force_sell")
    _sell(book, CODE, lot1, 10.0, "20251104", "force_sell")
    book_comm = sum(t["commission"] for t in book.trades if t["side"] == "SELL")
    assert book_comm == pytest.approx(10.0)
    assert book.cash == pytest.approx(1990.0)

    # v7 one call aggregates both lots → one floor: max(3.0, 5) = 5; cash +1995
    v7_one = SimResult(0.0)
    pos = V7Position(
        symbol=CODE,
        entry_A=10.0,
        last_add_date=date(2025, 11, 3),
        avg_cost=10.0,
    )
    pos.lots = [
        Lot(100, date(2025, 11, 3), 10.0, "trial"),
        Lot(100, date(2025, 11, 3), 10.0, "trial"),
    ]
    v7_one.positions[CODE] = pos
    _sell_lots(v7_one, pos, date(2025, 11, 4), 895, 10.0, "force", fee=QLIB_PORTANA)
    assert v7_one.cash == pytest.approx(1995.0)

    # v7 two calls (one lot each) match book totals
    v7_two = SimResult(0.0)
    pos2 = V7Position(
        symbol=CODE,
        entry_A=10.0,
        last_add_date=date(2025, 11, 2),
        avg_cost=10.0,
    )
    pos2.lots = [
        Lot(100, date(2025, 11, 2), 10.0, "trial"),
        Lot(100, date(2025, 11, 2), 10.0, "add"),
    ]
    v7_two.positions[CODE] = pos2
    _sell_lots(
        v7_two, pos2, date(2025, 11, 4), 895, 10.0, "force", kind="trial", fee=QLIB_PORTANA
    )
    _sell_lots(
        v7_two, pos2, date(2025, 11, 4), 896, 10.0, "force", kind="add", fee=QLIB_PORTANA
    )
    assert v7_two.cash == pytest.approx(1990.0)

    # Default bilateral (min=0) does not expose the fork
    bilateral_book = SimState(cash=0.0)
    a = BookPosition(CODE, 100, 10.0, 0, 10.0, lot_id=0)
    b = BookPosition(CODE, 100, 10.0, 0, 10.0, lot_id=1)
    bilateral_book.positions[CODE] = [a, b]
    _sell(bilateral_book, CODE, a, 10.0, "20251104", "force_sell")
    _sell(bilateral_book, CODE, b, 10.0, "20251104", "force_sell")
    v7_bi = SimResult(0.0)
    pos_bi = V7Position(
        symbol=CODE, entry_A=10.0, last_add_date=date(2025, 11, 3), avg_cost=10.0
    )
    pos_bi.lots = [
        Lot(100, date(2025, 11, 3), 10.0, "trial"),
        Lot(100, date(2025, 11, 3), 10.0, "trial"),
    ]
    v7_bi.positions[CODE] = pos_bi
    _sell_lots(
        v7_bi, pos_bi, date(2025, 11, 4), 895, 10.0, "force", fee=BILATERAL_10BP
    )
    assert sum(t["commission"] for t in bilateral_book.trades) == pytest.approx(2.0)
    assert bilateral_book.cash == pytest.approx(1998.0)
    assert v7_bi.cash == pytest.approx(1998.0)


def test_cash_gate_exact_vs_one_fen_short_unchanged_on_reject():
    """Exact cash fills; one fen short rejects with cash/positions/trades unchanged."""
    # Book execute_buy: 100 sh @ 10 → notional 1000 + 10bp fee 1 = 1001
    exact = SimState(cash=1001.0)
    assert execute_buy(exact, CODE, 10.0, 1_000.0, 0, "20251103") is True
    assert exact.cash == pytest.approx(0.0)
    assert CODE in exact.positions
    assert len(exact.trades) == 1

    short = SimState(cash=1000.99)
    snap_cash = short.cash
    snap_pos = deepcopy(short.positions)
    snap_trades = list(short.trades)
    assert execute_buy(short, CODE, 10.0, 1_000.0, 0, "20251103") is False
    assert short.cash == snap_cash
    assert short.positions == snap_pos
    assert short.trades == snap_trades

    # v7 _buy under PortAna floor: 100 sh @ 10 → fee max(0.5, 5)=5 → need 1005
    D1 = date(2026, 9, 1)
    # fraction such that NAME_BUDGET * fraction / price / 100 * 100 = 100 shares
    # 1_000_000 * f / 10 / 100 * 100 = 100 → f = 0.001
    v7_exact = SimResult(1005.0)
    pos = v7_buy(
        v7_exact,
        None,
        CODE,
        D1,
        895,
        10.0,
        0.001,
        "buy:trial",
        "trial",
        fee=QLIB_PORTANA,
    )
    assert pos is not None
    assert v7_exact.cash == pytest.approx(0.0)

    v7_short = SimResult(1004.99)
    snap_cash = v7_short.cash
    assert (
        v7_buy(
            v7_short,
            None,
            CODE,
            D1,
            895,
            10.0,
            0.001,
            "buy:trial",
            "trial",
            fee=QLIB_PORTANA,
        )
        is None
    )
    # As-built: cash/positions unchanged; skip_cash event is observability (E-r2-04).
    assert v7_short.cash == snap_cash
    assert v7_short.positions == {}
    assert any(t.get("reason") == "skip_cash" for t in v7_short.trades)
    assert all(t.get("side") != "buy" for t in v7_short.trades)
