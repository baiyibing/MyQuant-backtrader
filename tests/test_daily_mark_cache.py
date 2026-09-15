# -*- coding: utf-8 -*-
"""H5: market_close_mark / per-code equity mark cache parity."""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.csv_ledger import (
    Position,
    SimState,
    last_close_mark,
    market_close_mark,
)
from backtest.research.csv_simulate_loop import append_equity_and_eod_marks


def _df(closes_by_day: dict[str, float]) -> pd.DataFrame:
    idx = pd.to_datetime(list(closes_by_day))
    closes = list(closes_by_day.values())
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes},
        index=idx,
    )


def test_market_close_mark_on_day_and_prior_and_missing():
    df = _df({"2025-11-03": 10.0, "2025-11-04": 11.0})
    day_ok = pd.Timestamp("2025-11-04")
    day_halt = pd.Timestamp("2025-11-05")
    day_before = pd.Timestamp("2025-11-01")
    assert market_close_mark(df, day_ok) == 11.0
    assert market_close_mark(df, day_halt) == 11.0
    assert market_close_mark(df, day_before) is None
    assert market_close_mark(None, day_ok) is None
    assert last_close_mark(df, day_halt, fallback=9.0) == 11.0
    assert last_close_mark(None, day_ok, fallback=9.0) == 9.0
    assert last_close_mark(df, day_before, fallback=9.0) == 9.0


def test_append_equity_multi_lot_same_code_one_mark_and_eod():
    day = pd.Timestamp("2025-11-05")
    bars = {"600000.SH": _df({"2025-11-03": 10.0, "2025-11-04": 12.5})}
    st = SimState(cash=1_000_000.0)
    st.positions["600000.SH"] = [
        Position(code="600000.SH", shares=100, cost=10.0, peak=10.0, entry_idx=0, lot_id=1),
        Position(code="600000.SH", shares=200, cost=11.0, peak=11.0, entry_idx=1, lot_id=2),
    ]
    append_equity_and_eod_marks(
        st,
        ds="20251105",
        day=day,
        calendar_last=day,
        mark_bars=bars,
    )
    # both lots marked at prior close 12.5 (halt day), not respective costs
    assert dict(st.equity_curve)["20251105"] == pytest.approx(
        1_000_000.0 + 100 * 12.5 + 200 * 12.5
    )
    eod = [t for t in st.trades if t["side"] == "EOD_MARK"]
    assert len(eod) == 2
    assert {t["price"] for t in eod} == {12.5}
    assert {t["lot"] for t in eod} == {1, 2}


def test_append_equity_missing_bars_uses_per_lot_cost():
    day = pd.Timestamp("2025-11-05")
    st = SimState(cash=500_000.0)
    st.positions["600000.SH"] = [
        Position(code="600000.SH", shares=100, cost=10.0, peak=10.0, entry_idx=0, lot_id=1),
        Position(code="600000.SH", shares=50, cost=20.0, peak=20.0, entry_idx=0, lot_id=2),
    ]
    append_equity_and_eod_marks(
        st,
        ds="20251105",
        day=day,
        calendar_last=day,
        mark_bars={},
    )
    assert dict(st.equity_curve)["20251105"] == pytest.approx(
        500_000.0 + 100 * 10.0 + 50 * 20.0
    )
    eod = [t for t in st.trades if t["side"] == "EOD_MARK"]
    assert sorted(t["price"] for t in eod) == [10.0, 20.0]
