"""Frozen two-name X-02 cash inversion, independent of a market lake."""

from decimal import ROUND_HALF_UP, Decimal

import pandas as pd


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def chronological_case(sell_hm=899, buy_hm=895, gap_open=False):
    a, b = "600000.SH", "600001.SH"
    days = pd.to_datetime(["2025-11-03", "2025-11-04", "2025-11-05"])
    daily = {code: pd.DataFrame({col: values for col in ("open", "high", "low", "close")}, index=days)
             for code, values in ((a, [10., 10., 9.4]), (b, [6., 6., 6.]))}
    def frame(rows):
        return pd.DataFrame(rows, columns=["ymd", "hm", "open", "high", "low", "close"])
    minute = {
        a: frame([("20251104", 895, 10., 10., 10., 10.),
                  ("20251105", 570, 10., 10., 10., 10.),
                  ("20251105", sell_hm, 9.4 if gap_open else 10., 10., 9.4, 9.4)]),
        b: frame([("20251105", 570, 6., 6., 6., 6.),
                  ("20251105", buy_hm, 6., 6., 6., 6.)]),
    }
    return {"minute_bars": minute, "daily_bars": daily,
                "pool_days": {"20251104": [a], "20251105": [b]},
                "start": "20251104", "end": "20251105", "strategy": "version8",
                "stop_pct": .05, "total_cash": 1001., "name_budget": 1000.}
