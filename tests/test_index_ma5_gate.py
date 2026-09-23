"""SSE MA5 gate: signal-day close below MA5 blocks the next session's new buys."""

from __future__ import annotations

from datetime import date, timedelta

from backtest.research.topk_dropout_eligibility import (
    SSE_INDEX_SYMBOL,
    index_ma5_buy_days,
    make_eligible_buy,
)


def _days(n: int, start: date = date(2026, 1, 5)) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def test_equal_ma_allows_next_day_and_below_blocks():
    days = _days(7)
    closes = {days[i]: 10.0 for i in range(5)}
    closes[days[5]] = 9.0
    closes[days[6]] = 12.0
    blocked, allowed = index_ma5_buy_days(closes)
    assert days[5].strftime("%Y%m%d") in allowed
    assert days[6].strftime("%Y%m%d") in blocked


def test_sse_below_blocks_every_name():
    days = _days(6)
    above = {days[i]: 10.0 for i in range(6)}
    below = {days[i]: 10.0 for i in range(4)}
    below[days[4]] = 9.0
    below[days[5]] = 9.0
    gate = make_eligible_buy(
        index_ma5_gate=True,
        index_closes_by_symbol={SSE_INDEX_SYMBOL: below, "399006.SZ": above},
    )
    buy = days[5].strftime("%Y%m%d")
    assert gate("600000.SH", buy) is False
    assert gate("000001.SZ", buy) is False
    assert gate("300001.SZ", buy) is False
    assert gate("688228.SH", buy) is False
    assert gate("920001.BJ", buy) is False


def test_sse_above_allows_every_name():
    days = _days(6)
    above = {days[i]: 10.0 for i in range(6)}
    below = {days[i]: 10.0 for i in range(4)}
    below[days[4]] = 9.0
    below[days[5]] = 9.0
    gate = make_eligible_buy(
        index_ma5_gate=True,
        index_closes_by_symbol={SSE_INDEX_SYMBOL: above, "399006.SZ": below},
    )
    buy = days[5].strftime("%Y%m%d")
    assert gate("600000.SH", buy) is True
    assert gate("300001.SZ", buy) is True
    assert gate("688228.SH", buy) is True
    assert gate("920001.BJ", buy) is True
