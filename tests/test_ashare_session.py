# -*- coding: utf-8 -*-
from datetime import date

import pytest

from backtest.research.ashare_session import (
    defer_sell_at_limit,
    flatten_pool_names,
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


@pytest.mark.parametrize("raw,mapped,limits", [
    (10.0, 5.0, (5.50, 4.50)), (3.30, 1.65, (1.82, 1.49)),
])
def test_d2_mapped_return_flows_into_decimal_limits(raw, mapped, limits):
    # MC-6: main board; no float multiplication/rounding bypass for the band.
    previous = session_prev_close(
        {date(2026, 8, 31): raw, date(2026, 9, 1): 999.0},
        date(2026, 9, 1), "600000.SH", {"600000.SH": {"20260901": 0.5}},
    )
    assert previous == mapped
    assert session_limit_prices("600000.SH", previous) == limits
    assert skip_buy_at_limit(limits[0], limits)
    assert defer_sell_at_limit(limits[1], limits)


def test_d2_no_previous_close_retains_none_policy():
    previous = session_prev_close({}, date(2026, 9, 1), "600000.SH", None)
    assert previous is None
    limits = session_limit_prices("600000.SH", previous)
    assert limits is None
    assert not skip_buy_at_limit(10.0, limits)
    assert not defer_sell_at_limit(10.0, limits)


@pytest.mark.parametrize("code,name,expected", [
    pytest.param("600000.SH", "", (110, 90), id="unknown-name-known-board"),
    pytest.param("999999.SZ", "普通名", None, id="unknown-board-normal-name"),
    pytest.param("999999.SZ", "*ST甲", (105, 95), id="st-before-unknown-board"),
    pytest.param("300001.SZ", "ST甲", (105, 95), id="st-before-twenty-percent"),
    pytest.param("920014.BJ", "*st甲", (105, 95), id="st-before-thirty-percent"),
    pytest.param("600000.SH", "WEST", (110, 90), id="latin-token-not-st"),
])
def test_d3_name_and_board_boundaries(code, name, expected):
    limits = session_limit_prices(code, 100, name)
    assert limits == expected
    # Predicate pass is not a fill claim (in particular when limits is None).
    assert skip_buy_at_limit(105, limits) is (expected == (105, 95))
    assert defer_sell_at_limit(95, limits) is (expected == (105, 95))


def test_d3_direct_flatten_empty_name_clears_unlike_loader():
    # Direct helper callers can supply an empty string; the real loader filters it.
    names = flatten_pool_names({
        "20260902": {"600000.SH": ""},
        "20260901": {"600000.SH": "*ST甲"},
    })
    assert names == {"600000.SH": ""}
    assert session_limit_prices("600000.SH", 100, names["600000.SH"]) == (110, 90)
