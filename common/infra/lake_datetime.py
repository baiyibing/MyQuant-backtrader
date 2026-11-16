"""BT host policy for the datetime representation of consumed lake bars."""

from __future__ import annotations

import pandas as pd


def lake_datetime_index(stamps: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Keep the pandas 3.0.6 index unit without changing timestamps or timezone.

    pandas 3.0.6 retained ``unit="ms"``; 3.1 infers microseconds instead.
    Keep the 3.0.6 representation for uncached research bars, including their
    row hashes. Cache schemas independently require nanoseconds. For historical
    floating inputs containing sub-millisecond times, retain 3.0.6's nanoseconds
    instead of silently truncating their values.
    """
    millis = stamps.as_unit("ms")
    if ((stamps != millis) & ~stamps.isna()).any():
        return stamps.as_unit("ns")
    return millis


def utc_ms_index(values) -> pd.DatetimeIndex:
    """Decode epoch milliseconds using BT's explicit UTC index policy."""
    return lake_datetime_index(pd.DatetimeIndex(pd.to_datetime(values, unit="ms", utc=True)))
