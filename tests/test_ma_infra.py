"""Data-free pins for the shared research MA contract."""

from datetime import date
from math import isinf, isnan, sqrt
from statistics import stdev

import pandas as pd
import pytest

from backtest.research import ma_infra as ma
from oskh_factors.weekly_macd_divergence import _daily_to_weekly


def _dates(*values):
    return [date.fromisoformat(value) for value in values]


def _pandas_weekly(dates, closes):
    daily = pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1.0] * len(closes),
        },
        index=pd.DatetimeIndex(dates),
    )
    return _daily_to_weekly(daily)


def _assert_same_number(actual, expected):
    if expected is None:
        assert actual is None
    elif isnan(expected):
        assert actual is not None and isnan(actual)
    elif isinf(expected):
        assert actual == expected
    else:
        assert actual == pytest.approx(expected)


def test_sma_asof_seed_tail_full_window_and_int_truncation():
    assert ma.sma_asof([1, 2, 3, 4], 2.9) == 3.5
    assert ma.sma_asof([1, 2], 3) is None
    assert ma.sma_asof([], 1) is None
    assert ma.sma_asof(["1", "2", "3"], 2) == 2.5


def test_sma_asof_nan_is_not_none_and_leaves_window():
    result = ma.sma_asof([1, float("nan"), 3], 3)
    assert result is not None and isnan(result)
    assert ma.sma_asof([float("nan"), 2, 3], 2) == 2.5


@pytest.mark.parametrize("n", [0, -1, -10, 0.9])
def test_sma_nonpositive_window(n):
    assert ma.sma_asof([1, 2, 3], n) is None
    assert ma.sma_series([1, 2, 3], n) == [None] * 3
    assert ma.sma_live([1, 2, 3], 10, n) is None


@pytest.mark.parametrize("n", [1, 2, 5, 20, 2.9])
@pytest.mark.parametrize(
    "closes",
    [
        [],
        [1.0, 2.5, 3.1, 4.2, 5.8, 6.0],
        [1, float("nan"), 3, 4, 5, 6],
        [1, float("inf"), -float("inf"), 4, 5, 6],
    ],
)
def test_sma_series_matches_seed_at_every_prefix(closes, n):
    actual = ma.sma_series(closes, n)
    assert len(actual) == len(closes)
    for i, value in enumerate(actual):
        _assert_same_number(value, ma.sma_asof(closes[:i + 1], n))


def test_sma_series_warmup_and_floating_point_pin():
    closes = [10 + i / 100 for i in range(1000)]
    actual = ma.sma_series(closes, 20)
    assert actual[:19] == [None] * 19
    for i in range(19, len(closes)):
        assert actual[i] == pytest.approx(ma.sma_asof(closes[:i + 1], 20))


def test_sma_live_uses_tail_plus_price_without_mutation():
    prev = [1, 2, 3, 4]
    assert ma.sma_live(prev, 10, 3) == pytest.approx((3 + 4 + 10) / 3)
    assert ma.sma_live(prev, 10, 3) == ma.sma_asof(prev[-2:] + [10], 3)
    assert prev == [1, 2, 3, 4]
    assert ma.sma_live(prev, 10, 1) == 10
    assert ma.sma_live([], 10, 1) == 10
    assert ma.sma_live([1], 10, 3) is None


@pytest.mark.parametrize("px", [0, -1])
def test_sma_live_nonpositive_price(px):
    assert ma.sma_live([1, 2, 3], px, 3) is None


def test_bb_sample_sigma_numeric_pin_without_rounding():
    sigma = sqrt(2.5)
    assert sigma == 1.5811388300841898
    assert stdev([1, 2, 3, 4, 5]) == sigma
    bands = ma.bb_series([1, 2, 3, 4, 5], n=5, k=1)
    assert bands[:4] == [None] * 4
    assert bands[-1] == (3.0, 3.0 + sigma, 3.0 - sigma)
    assert ma.bb_asof([1, 2, 3, 4, 5], n=5) == (
        3.0, 3.0 + 2 * sigma, 3.0 - 2 * sigma
    )


@pytest.mark.parametrize("n", [-2, 0, 1])
def test_bb_n_less_than_two_is_all_none(n):
    assert ma.bb_series([1, 2, 3], n) == [None, None, None]
    assert ma.bb_asof([1, 2, 3], n) is None


@pytest.mark.parametrize("n,k", [(2, 1.0), (5, 2.0), (20, 2.5)])
def test_bb_equal_length_and_matches_pandas_rolling(n, k):
    closes = [10 + ((i * 7) % 13) / 10 for i in range(60)]
    actual = ma.bb_series(closes, n, k)
    rolling = pd.Series(closes).rolling(n)
    mids = rolling.mean()
    sigmas = rolling.std(ddof=1)
    assert len(actual) == len(closes)
    assert actual[:n - 1] == [None] * (n - 1)
    for i in range(n - 1, len(closes)):
        assert actual[i] == pytest.approx(
            (mids[i], mids[i] + k * sigmas[i], mids[i] - k * sigmas[i])
        )
        assert ma.bb_asof(closes[:i + 1], n, k) == actual[i]


def test_bb_default_window_short_history_and_constant_prices():
    assert ma.bb_series([]) == []
    assert ma.bb_asof([]) is None
    assert ma.bb_series([10] * 19) == [None] * 19
    assert ma.bb_asof([10] * 19) is None
    assert ma.bb_series([10] * 22) == [None] * 19 + [(10, 10, 10)] * 3


def test_bb_nan_propagates_only_while_in_window():
    result = ma.bb_series([1, float("nan"), 3, 4, 5], 3)
    assert result[:2] == [None, None]
    assert all(isnan(value) for bands in result[2:4] for value in bands)
    assert result[4] == (4, 6, 2)


def test_daily_to_weekly_pandas_diff_short_empty_cross_year_and_trailing_week():
    dates = _dates(
        "2023-12-28", "2023-12-29", "2023-12-30", "2023-12-31",
        "2024-01-02", "2024-01-04", "2024-01-15", "2024-01-17",
    )
    closes = [10, 11, 12, 13, 14, 15, 16, 17]
    reference = _pandas_weekly(dates, closes)
    expected = [(day.date(), float(close)) for day, close in zip(
        reference["_last_day"], reference["close"], strict=True
    )]
    assert ma.daily_to_weekly(dates, closes) == expected == [
        (date(2023, 12, 29), 11),
        (date(2024, 1, 4), 15),
        (date(2024, 1, 17), 17),
    ]
    assert any(label != last for label, last in zip(
        reference.index, reference["_last_day"], strict=True
    ))
    assert date(2024, 1, 12) not in reference.index.date  # Halt week is absent.


def test_daily_to_weekly_saturday_starts_new_bucket():
    dates = _dates("2023-12-29", "2023-12-30", "2023-12-31", "2024-01-01")
    closes = [10, 20, 30, 40]
    reference = _pandas_weekly(dates, closes)
    assert list(reference.index.date) == [date(2023, 12, 29), date(2024, 1, 5)]
    assert ma.daily_to_weekly(dates, closes) == [
        (date(2023, 12, 29), 10), (date(2024, 1, 1), 40)
    ]


def test_daily_to_weekly_pandas_diff_nan_last_close_and_all_nan_week():
    dates = _dates(
        "2024-01-01", "2024-01-04", "2024-01-08", "2024-01-12",
        "2024-01-15", "2024-01-17",
    )
    closes = [10, float("nan"), float("nan"), float("nan"), float("nan"), 30]
    reference = _pandas_weekly(dates, closes)
    assert ma.daily_to_weekly(dates, closes) == [
        (day.date(), float(close)) for day, close in zip(
            reference["_last_day"], reference["close"], strict=True
        )
    ] == [(date(2024, 1, 4), 10), (date(2024, 1, 17), 30)]
    assert ma.daily_to_weekly(dates[:2], [float("nan")] * 2) == []


def test_daily_to_weekly_pandas_diff_unsorted_and_duplicate_dates():
    dates = _dates("2024-01-05", "2024-01-01", "2024-01-05", "2024-01-04")
    closes = [10, 20, 30, 40]
    reference = _pandas_weekly(dates, closes)
    assert ma.daily_to_weekly(dates, closes) == [
        (day.date(), float(close)) for day, close in zip(
            reference["_last_day"], reference["close"], strict=True
        )
    ] == [(date(2024, 1, 5), 30)]


def test_weekly_sma_backward_alignment_short_empty_and_trailing_weeks():
    dates = _dates(
        "2023-12-28", "2023-12-29", "2024-01-02", "2024-01-04",
        "2024-01-15", "2024-01-17",
    )
    closes = [10, 12, 20, 22, 30, 32]
    actual = ma.weekly_sma_series(dates, closes, 2)
    assert len(actual) == len(dates)
    assert actual == [None, None, None, 17, 17, 27]
    assert ma.weekly_sma_asof(dates, closes, 2) == actual[-1]
    assert ma.weekly_sma_asof(dates[:3], closes[:3], 2) == 16
    assert ma.weekly_sma_asof(dates[:1], closes[:1], 1) == 10
    assert ma.weekly_sma_series(dates, closes, 4) == [None] * len(dates)


def test_weekly_sma_pandas_backward_alignment_with_nan_week():
    dates = _dates("2024-01-04", "2024-01-08", "2024-01-12", "2024-01-17")
    closes = [10, float("nan"), float("nan"), 30]
    reference = _pandas_weekly(dates, closes)
    averages = reference.set_index("_last_day")["close"].rolling(2).mean()
    expected = averages.reindex(pd.DatetimeIndex(dates), method="ffill")
    actual = ma.weekly_sma_series(dates, closes, 2)
    assert actual == [None, None, None, 20]
    for value, ref in zip(actual, expected, strict=True):
        _assert_same_number(value, None if pd.isna(ref) else ref)


def test_weekly_empty_nonpositive_and_all_nan_history():
    assert ma.daily_to_weekly([], []) == []
    assert ma.weekly_sma_series([], [], 2) == []
    assert ma.weekly_sma_asof([], [], 2) is None
    dates = _dates("2024-01-05", "2024-01-12")
    assert ma.weekly_sma_series(dates, [10, 20], 0) == [None, None]
    assert ma.weekly_sma_series(dates, [float("nan")] * 2, 1) == [None, None]
