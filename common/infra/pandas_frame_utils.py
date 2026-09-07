# -*- coding: utf-8 -*-
"""
Pyright-friendly helpers for :class:`pandas.DataFrame` construction.

Pandas 2.x stubs treat ``columns=`` strictly; ``list[str]`` is not accepted for empty /
from-rows frames in basic mode. Use ``typing.cast`` at this boundary only.
"""

from __future__ import annotations

from typing import Any, Iterable, cast

import pandas as pd


def empty_cal_date_dataframe() -> pd.DataFrame:
    """Single column ``cal_date`` (YYYYMMDD), zero rows."""
    return pd.DataFrame(columns=cast(Any, ["cal_date"]))


def cal_date_dataframe_from_strings(values: Iterable[str]) -> pd.DataFrame:
    """Build a one-column ``cal_date`` frame from string YYYYMMDD values."""
    rows = [str(x) for x in values]
    return pd.DataFrame(rows, columns=cast(Any, ["cal_date"])).reset_index(drop=True)


__all__ = ["cal_date_dataframe_from_strings", "empty_cal_date_dataframe"]
