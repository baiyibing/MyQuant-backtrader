# -*- coding: utf-8 -*-
"""Pyright-friendly pandas coercion helpers for ``oskh_data``."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd


def as_series(obj: Any) -> pd.Series:
    return cast(pd.Series, obj)


def as_timestamp(ts: Any) -> pd.Timestamp:
    """Coerce to ``Timestamp`` (may still be NaT)."""
    return cast(pd.Timestamp, pd.Timestamp(ts))


def normalize_timestamp(ts: Any) -> pd.Timestamp:
    """``Timestamp.normalize()`` with pyright-safe coercion."""
    return cast(pd.Timestamp, as_timestamp(ts).normalize())


def timestamp_strftime(ts: Any, fmt: str) -> str:
    t = as_timestamp(ts)
    return t.strftime(fmt)


def to_numeric_series(series: Any, **kwargs: Any) -> pd.Series:
    return cast(pd.Series, pd.to_numeric(series, **kwargs))


def as_dataframe(obj: Any) -> pd.DataFrame:
    return cast(pd.DataFrame, obj)


def index_normalize_series(index: Any) -> pd.Series:
    """Calendar-day normalize for a datetime index (pyright-safe)."""
    return pd.Series(index).dt.normalize()
