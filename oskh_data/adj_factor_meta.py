"""BT compatibility facade for infra's adjustment-factor freshness sidecar.

The private dependency is optional at import time, as in D4. Runtime metadata IO
requires requirements-infra.txt; no second JSON publisher lives in the host.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import pandas as pd

from oskh_data._infra import require_infra

try:
    from myquant_infra.bars import adj_factor_meta as _infra_meta
except ImportError:
    class _MissingAdjFactorMeta:
        """Patchable boundary for public CI without the private package."""

        def adj_factor_meta_path(self, *args, **kwargs):
            return require_infra("bars.adj_factor_meta").adj_factor_meta_path(*args, **kwargs)

        def write_adj_factor_meta(self, *args, **kwargs):
            return require_infra("bars.adj_factor_meta").write_adj_factor_meta(*args, **kwargs)

        def read_adj_factor_data_max_date(self, *args, **kwargs):
            return require_infra("bars.adj_factor_meta").read_adj_factor_data_max_date(*args, **kwargs)

    _infra_meta = _MissingAdjFactorMeta()

PathLike = Union[str, Path]


def adj_factor_meta_path(parquet_path: PathLike) -> Path:
    return _infra_meta.adj_factor_meta_path(parquet_path)


def write_adj_factor_meta(
    parquet_path: PathLike,
    df: Optional[pd.DataFrame] = None,
    *,
    source: str,
    build_time: Optional[str] = None,
    data_max_date: Optional[str] = None,
    stock_count: Optional[int] = None,
) -> Path:
    return _infra_meta.write_adj_factor_meta(
        parquet_path, df, source=source, build_time=build_time,
        data_max_date=data_max_date, stock_count=stock_count,
    )


def read_adj_factor_data_max_date(parquet_path: PathLike) -> Optional[pd.Timestamp]:
    return _infra_meta.read_adj_factor_data_max_date(parquet_path)


__all__ = [
    "adj_factor_meta_path",
    "read_adj_factor_data_max_date",
    "write_adj_factor_meta",
]
