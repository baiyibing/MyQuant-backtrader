# -*- coding: utf-8 -*-
"""Light shared helpers for CSV daily / minute engines.

Extracted so both engines can import calendar / name-asof without coupling
through the daily module. Do **not** merge the two ``simulate()`` loops here —
that remains future work after sell-book contracts stay locked.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtest.research.csv_ledger import resolve_limit_prices


def build_calendar(bars: dict[str, pd.DataFrame], start: str, end: str) -> list:
    t0 = pd.Timestamp(start)
    t1 = pd.Timestamp(end)
    seen = set()
    for df in bars.values():
        idx = df.index
        for d in idx[(idx >= t0) & (idx <= t1)]:
            seen.add(d)
    calendar = sorted(seen)
    if not calendar:
        raise SystemExit("no daily bars in window")
    return calendar


def _named_limits(code: str, prev_close: float, names: dict[str, str]):
    return resolve_limit_prices(code, prev_close, names.get(code, ""))


def _pool_names_asof(
    pool_names: Optional[dict[str, str]],
    pool_names_by_day: Optional[dict[str, dict[str, str]]],
):
    """Return a monotonic per-day name resolver; by-day input has priority."""
    if pool_names_by_day is None:
        names = dict(pool_names or {})
        return lambda _ds: names

    updates = sorted(pool_names_by_day.items())
    last_seen: dict[str, str] = {}
    cursor = 0

    def names_for_day(ds: str) -> dict[str, str]:
        nonlocal cursor
        while cursor < len(updates) and updates[cursor][0] <= ds:
            _ymd_key, observed = updates[cursor]
            for code, name in observed.items():
                if name:
                    last_seen[code] = name
            cursor += 1
        return last_seen

    return names_for_day
