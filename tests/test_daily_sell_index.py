# -*- coding: utf-8 -*-
"""H8: day_bar_and_prev_closes searchsorted parity vs naive .loc."""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.csv_common import day_bar_and_prev_closes


def _df(closes_by_day: dict[str, float]) -> pd.DataFrame:
    idx = pd.to_datetime(list(closes_by_day))
    closes = list(closes_by_day.values())
    return pd.DataFrame(
        {
            "open": [c - 0.01 for c in closes],
            "high": [c + 0.02 for c in closes],
            "low": [c - 0.02 for c in closes],
            "close": closes,
        },
        index=idx,
    )


def _naive(df: pd.DataFrame, day):
    if day not in df.index:
        return None
    prev = df.loc[df.index < day]
    if prev.empty:
        return None
    row = df.loc[day]
    closes = prev["close"].astype(float).tolist()
    return row, closes


def test_day_bar_and_prev_closes_matches_naive_on_day_and_edges():
    df = _df({"2025-11-03": 10.0, "2025-11-04": 11.0, "2025-11-05": 12.0})
    for day_s in ("2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-02"):
        day = pd.Timestamp(day_s)
        naive = _naive(df, day)
        fast = day_bar_and_prev_closes(df, day)
        if naive is None:
            assert fast is None
            continue
        nrow, ncloses = naive
        frow, fcloses = fast
        assert fcloses == ncloses
        assert float(frow["open"]) == pytest.approx(float(nrow["open"]))
        assert float(frow["high"]) == pytest.approx(float(nrow["high"]))
        assert float(frow["low"]) == pytest.approx(float(nrow["low"]))
        assert float(frow["close"]) == pytest.approx(float(nrow["close"]))


def test_day_bar_first_bar_has_no_prev():
    df = _df({"2025-11-03": 10.0})
    assert day_bar_and_prev_closes(df, pd.Timestamp("2025-11-03")) is None


def test_day_bar_missing_day_none():
    df = _df({"2025-11-03": 10.0, "2025-11-05": 12.0})
    # gap day not in index
    assert day_bar_and_prev_closes(df, pd.Timestamp("2025-11-04")) is None
