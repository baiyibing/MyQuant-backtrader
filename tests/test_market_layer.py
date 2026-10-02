from datetime import date, datetime

import pytest

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
    ("code", "name", "expected"),
    [
        ("300001.SZ", "", 0.20),
        ("301001.SZ", "", 0.20),
        ("302001.SZ", "", 0.20),
        ("688001.SH", "", 0.20),
        ("689001.SH", "", 0.20),
        ("600000.SH", "", 0.10),
        ("000001.SZ", "", 0.10),
        ("920014.BJ", "", 0.30),
        ("430001.BJ", "", 0.30),
        ("830001.BJ", "", 0.30),
        ("870001.BJ", "", 0.30),
        ("880001.BJ", "", 0.30),
        ("600000.SH", "*ST 宁科", 0.05),
        ("300001.SZ", "ST华仪", 0.20),
        ("159001.SZ", "", None),
        ("510050.SH", "", None),
        ("123456.SH", "普通名", None),
    ],
)
def test_limit_pct_board_table_and_st_name(code, name, expected):
    assert limit_pct(code, name) == expected


def test_decimal_limit_prices_pin_1_65_to_1_49():
    assert limit_prices("600000.SH", 1.65) == (1.82, 1.49)
    assert round_fen(4.125) == 4.13
    assert limit_prices("159001.SZ", 1.65) is None


def test_lake_milliseconds_and_calendar_values():
    assert as_datetime(1735810200000) == datetime(2025, 1, 2, 9, 30)
    assert as_date(661564800000) == date(1990, 12, 19)
    assert as_date(20260804) == date(2026, 8, 4)
    assert as_date("2026-08-04") == date(2026, 8, 4)


@pytest.mark.parametrize("as_of,expected", [
    (None, .05), (20260705, .05), ("20260706", .10),
    (date(2026, 7, 6), .10), (datetime(2026, 7, 5, 23, 59), .05),
])
def test_main_st_switch(as_of, expected):
    assert limit_pct("600000", "*ST 测试", as_of) == expected


@pytest.mark.parametrize("code,expected", [
    ("300001", .20), ("301001", .20), ("302001", .20),
    ("688001", .20), ("689001", .20), ("920014", .30), ("123456", .05),
])
@pytest.mark.parametrize("as_of", [None, 20260705, "20260706"])
def test_st_board_precedes_date(code, expected, as_of):
    assert limit_pct(code, "ST测试", as_of) == expected


def test_dated_limits_decimal_and_qlib_bypass():
    from backtest.research.csv_common import book_limit_prices, qlib_limit_prices
    from backtest.research.csv_ledger import resolve_limit_prices

    assert limit_prices("600000", 1.65, "*ST测试", 20260705) == (1.73, 1.57)
    assert limit_prices("600000", 1.65, "*ST测试", 20260706) == (1.82, 1.49)
    assert resolve_limit_prices("600000", 1.65, "*ST测试", 20260706) == (1.82, 1.49)
    assert book_limit_prices("600000", 1.65, {"600000": "*ST测试"}, as_of=20260706) == (1.82, 1.49)
    assert book_limit_prices("600000", 1.65, {}, qlib_limit_pct=.095,
                             as_of="ignored") == qlib_limit_prices(1.65)
