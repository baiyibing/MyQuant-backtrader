from datetime import date, datetime

import pytest

from backtest.research.csv_minute_backtest_v7 import _limit_prices as v7_limit_prices
from backtest.research.market_layer import (
    as_date,
    as_datetime,
    limit_pct,
    limit_prices,
    round_fen,
    utc_ms_range,
)


def test_utc_ms_range_is_closed_utc_day_range():
    assert utc_ms_range("20250102", "20250102") == (
        1735776000000,
        1735862399999,
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [("300001.SZ", 0.20), ("301001.SZ", 0.20), ("688001.SH", 0.20), ("689001.SH", 0.10), ("600000.SH", 0.10)],
)
def test_limit_pct_preserves_existing_board_table(code, expected):
    assert limit_pct(code) == expected


def test_decimal_and_v7_float_limit_arithmetic_remain_distinct():
    assert limit_prices("600000.SH", 1.65)[1] == 1.49
    assert v7_limit_prices("600000.SH", 1.65)[1] == 1.48
    assert round_fen(4.125) == 4.13


def test_lake_milliseconds_and_calendar_values():
    assert as_datetime(1735810200000) == datetime(2025, 1, 2, 9, 30)
    assert as_date(661564800000) == date(1990, 12, 19)
    assert as_date(20260804) == date(2026, 8, 4)
    assert as_date("2026-08-04") == date(2026, 8, 4)
