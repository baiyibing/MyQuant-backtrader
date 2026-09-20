# -*- coding: utf-8 -*-
"""H5 mark cache; Human GO P4=A closure (2026-09-20).

Daily on/prior close and lot-cost fallback do not depend on minute touch
eligibility. P1=A / P2=B remain unchanged; EOD_MARK is valuation, not a fill.
"""

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


@pytest.mark.parametrize("close_day", ["2025-11-04", "2025-11-05"], ids=["halt", "on_day"])
def test_append_equity_multi_lot_same_code_one_mark_and_eod(monkeypatch, close_day):
    import backtest.research.csv_simulate_loop as loop

    day = pd.Timestamp("2025-11-05")
    bars = {"600000.SH": _df({"2025-11-03": 10.0, close_day: 12.5})}
    calls = []

    def counted_mark(df, mark_day):
        calls.append(mark_day)
        return market_close_mark(df, mark_day)

    monkeypatch.setattr(loop, "market_close_mark", counted_mark)
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
    # P4=A: daily close (on-day or prior on halt), independent of minute data.
    assert calls == [day]  # One per code, shared by both lots and EOD_MARK.
    assert dict(st.equity_curve)["20251105"] == pytest.approx(
        1_000_000.0 + 100 * 12.5 + 200 * 12.5
    )
    eod = [t for t in st.trades if t["side"] == "EOD_MARK"]
    assert len(eod) == 2
    assert {t["price"] for t in eod} == {12.5}
    assert {t["lot"] for t in eod} == {1, 2}
    assert all(t["session_phase"] == t["price_rule"] == "" for t in eod)


@pytest.mark.parametrize("future_only", [False, True], ids=["missing", "future_only"])
def test_append_equity_missing_bars_uses_per_lot_cost(future_only):
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
        mark_bars={"600000.SH": _df({"2025-11-06": 99.0})} if future_only else {},
    )
    assert dict(st.equity_curve)["20251105"] == pytest.approx(
        500_000.0 + 100 * 10.0 + 50 * 20.0
    )
    eod = [t for t in st.trades if t["side"] == "EOD_MARK"]
    assert sorted(t["price"] for t in eod) == [10.0, 20.0]
    assert len(eod) == 2
    assert all(t["session_phase"] == t["price_rule"] == "" for t in eod)
