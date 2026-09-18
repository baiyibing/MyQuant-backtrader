# -*- coding: utf-8 -*-
from datetime import date

from backtest.research.ashare_session import (
    defer_sell_at_limit,
    hit_limit_down,
    hit_limit_up,
    session_limit_prices,
    session_prev_close,
    skip_buy_at_limit,
    t1_sellable,
)


def test_t1_sellable_is_later_session_only():
    day = date(2026, 9, 1)
    assert t1_sellable(date(2026, 8, 31), day)
    assert not t1_sellable(day, day)


def test_session_prev_close_maps_exdiv_then_limit_band():
    closes = {date(2026, 8, 31): 10.0}
    today = date(2026, 9, 1)
    raw = session_prev_close(closes, today, "600000.SH", None)
    mapped = session_prev_close(
        closes, today, "600000.SH", {"600000.SH": {"20260901": 0.95}}
    )
    assert raw == 10.0
    assert mapped == 9.5
    board = session_limit_prices("600000.SH", raw)
    st = session_limit_prices("600000.SH", raw, "*ST甲")
    assert board == (11.0, 9.0)
    assert st == (10.5, 9.5)


def test_skip_buy_and_defer_sell_use_shared_hits():
    limits = (11.0, 9.0)
    assert skip_buy_at_limit(11.0, limits)
    assert hit_limit_up(11.0, 11.0)
    assert not skip_buy_at_limit(10.9, limits)
    assert defer_sell_at_limit(9.0, limits)
    assert hit_limit_down(9.0, 9.0)
    assert not defer_sell_at_limit(9.1, limits)
    assert not skip_buy_at_limit(11.0, None)
