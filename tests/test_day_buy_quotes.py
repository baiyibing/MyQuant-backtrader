from __future__ import annotations

import pandas as pd

from backtest.research.csv_minute_backtest import BUY_HM, _buy_px, _buy_px_from_arrays
from backtest.research.csv_simulate_loop import DayBuyQuotes, _day_buy_quotes


def test_day_buy_quotes_caches_px_and_limits():
    calls = []

    def quote(code):
        calls.append(code)
        return 10.5, [10.0, 10.2]

    quotes = DayBuyQuotes(
        quote, ds="20251104", names={}, qlib_limit_pct=0.10,
    )
    first = quotes.get("600000.SH")
    second = quotes.get("600000.SH")
    via_fn = quotes.as_quote_fn()("600000.SH")
    assert calls == ["600000.SH"]
    assert first is second
    assert first.px == 10.5
    assert first.closes == [10.0, 10.2]
    assert first.did_map is False
    assert first.limits == (11.22, 9.18)
    assert via_fn == (10.5, [10.0, 10.2])


def test_day_buy_quotes_empty_closes_and_reuse():
    def quote(_code):
        return 10.0, []

    quotes = DayBuyQuotes(quote, ds="20251104", names={})
    assert quotes.get("600000.SH") is None
    shared = _day_buy_quotes(quotes, quote, ds="20251104", names={})
    assert shared is quotes


def test_buy_px_from_arrays_matches_dataframe():
    day = pd.DataFrame(
        {
            "hm": [14 * 60 + 30, BUY_HM, 15 * 60],
            "close": [10.1, 10.2, 10.3],
        }
    )
    assert _buy_px(day) == 10.2
    assert _buy_px_from_arrays(day["hm"].to_numpy("int64"), day["close"].to_numpy("float64")) == 10.2
    late = pd.DataFrame({"hm": [14 * 60 + 40, 14 * 60 + 50], "close": [9.8, 9.9]})
    assert _buy_px(late) == 9.9
    assert _buy_px_from_arrays(late["hm"].to_numpy("int64"), late["close"].to_numpy("float64")) == 9.9
    assert _buy_px_from_arrays(
        pd.Series([9 * 60 + 31], dtype="int64").to_numpy(),
        pd.Series([10.0], dtype="float64").to_numpy(),
    ) is None
