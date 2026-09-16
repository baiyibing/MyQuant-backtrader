# -*- coding: utf-8 -*-
"""Light shared helpers for CSV daily / minute engines.

Calendar / name-asof live here so engines avoid coupling through the daily
module. Chase / pool / equity-mark skeleton is in ``csv_simulate_loop.py``;
sell loops stay split on purpose (daily bar rules vs ``scan_held_day``).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtest.research.csv_ledger import resolve_limit_prices


def day_bar_and_prev_closes(
    df: pd.DataFrame, day
) -> Optional[tuple[pd.Series, list[float]]]:
    """Day OHLC row + prior closes via searchsorted (no ``index < day`` mask).

    Requires ``df.index`` sorted ascending and unique for ``day`` (as produced by
    ``load_daily_bars`` / test fixtures). Semantics match::

        if day not in df.index:
            return None
        prev = df.loc[df.index < day]
        if prev.empty:
            return None
        return df.loc[day], prev["close"].astype(float).tolist()
    """
    idx = df.index
    pos = idx.searchsorted(day)
    if pos >= len(idx) or idx[pos] != day:
        return None
    if pos == 0:
        return None
    row = df.iloc[pos]
    closes = df["close"].iloc[:pos].astype(float).tolist()
    return row, closes


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


def _progress(done: int, total: int, label: str, every: int = 200) -> None:
    if total <= 0:
        return
    if done == 1 or done == total or done % every == 0:
        print(f"{label} {done}/{total}", flush=True)


# Re-exported from csv_common for existing imports / minute engine.
# (build_calendar, _named_limits, _pool_names_asof)

_limit_prices = resolve_limit_prices
