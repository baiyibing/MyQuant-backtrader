"""Host path/producer compatibility for the infra TR store (B6, D8=A).

All parquet reads, locking, writes, caching and staging merges live in infra.
Host root/environment policy and the numerical bands producer stay here.
The shared package is required; host imports do not resolve a lake.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Sequence, Union

import pandas as pd

from oskh_data._infra import require_infra
from oskh_factors.chip.bands import compute_tr_bb_columns

if TYPE_CHECKING:
    from myquant_infra.derived_data.turnover_resistance.ports import BandsProducer

PathLike = Union[str, Path]
_INFRA_MODULE = "derived_data.turnover_resistance.store"

from myquant_infra.derived_data.turnover_resistance.store import (
    DEFAULT_WINDOW, DEFAULT_FREE_FLOAT_POLICY, UNIQUE_KEYS, SCHEMA_COLUMNS,
)


def resolve_parquet_path(path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve Parquet path (env ``TURNOVER_RESIST_BANDS_PATH`` overrides default)."""
    if path is not None:
        return Path(path)
    env = os.getenv("TURNOVER_RESIST_BANDS_PATH")
    if env:
        return Path(env)
    from common.infra.data_root import resolve_source_parquet

    return resolve_source_parquet("turnover_resistance_daily.parquet")


def resolve_staging_dir(staging_dir: Optional[Union[str, Path]] = None) -> Path:
    """Directory for per-year TR staging files in the configured container."""
    if staging_dir is not None:
        return Path(staging_dir)
    env = os.getenv("TURNOVER_RESIST_STAGING_DIR")
    if env:
        return Path(env)
    from common.infra.data_root import resolve_tr_staging_dir

    return resolve_tr_staging_dir()


def resolve_year_staging_path(
    year: int,
    staging_dir: Optional[PathLike] = None,
) -> Path:
    return require_infra(_INFRA_MODULE).resolve_year_staging_path(
        year, resolve_staging_dir(staging_dir),
    )


def merge_parquet_into_canonical(
    *sources: PathLike,
    canonical_path: Optional[PathLike] = None,
) -> dict[str, int]:
    return require_infra(_INFRA_MODULE).merge_parquet_into_canonical(
        *sources, canonical_path=resolve_parquet_path(canonical_path),
    )


def normalize_ffi_row(
    row: dict[str, Any],
    *,
    trade_date: str,
    window: int = DEFAULT_WINDOW,
    source: str = "canonical_rust",
    free_float_policy: str = DEFAULT_FREE_FLOAT_POLICY,
) -> dict[str, Any]:
    return require_infra(_INFRA_MODULE).normalize_ffi_row(
        row, trade_date=trade_date, window=window, source=source,
        free_float_policy=free_float_policy,
    )


class TurnoverResistanceStore:
    """Compatibility surface; IO delegates to infra with a host-owned producer."""

    def __init__(
        self,
        path: Optional[PathLike] = None,
        *,
        bands_producer: Optional[BandsProducer] = None,
    ) -> None:
        self._store = require_infra(_INFRA_MODULE).TurnoverResistanceStore(
            resolve_parquet_path(path),
            bands_producer=compute_tr_bb_columns if bands_producer is None else bands_producer,
        )

    @property
    def path(self) -> Path:
        return self._store.path

    @property
    def read_disk_loads(self) -> int:
        return self._store.read_disk_loads

    @read_disk_loads.setter
    def read_disk_loads(self, value: int) -> None:
        self._store.read_disk_loads = value

    @property
    def read_cache_hits(self) -> int:
        return self._store.read_cache_hits

    @read_cache_hits.setter
    def read_cache_hits(self, value: int) -> None:
        self._store.read_cache_hits = value

    def invalidate_cache(self) -> None:
        self._store.invalidate_cache()

    def cache_stats(self) -> dict[str, int]:
        return self._store.cache_stats()

    def upsert_daily(
        self, trade_date: str, rows: Sequence[dict[str, Any]], *,
        window: int = DEFAULT_WINDOW, source: str = "canonical_rust",
        free_float_policy: str = DEFAULT_FREE_FLOAT_POLICY,
    ) -> dict[str, int]:
        return self._store.upsert_daily(
            trade_date, rows, window=window, source=source,
            free_float_policy=free_float_policy,
        )

    def load_series(
        self, stock_code: str, *, end_date: Optional[str] = None, n: int = 60,
        window: int = DEFAULT_WINDOW, strict: bool = True,
    ) -> pd.DataFrame:
        return self._store.load_series(
            stock_code, end_date=end_date, n=n, window=window, strict=strict,
        )

    def load_cross_section(
        self, trade_date: str, *, window: int = DEFAULT_WINDOW,
        require_bands: bool = False,
    ) -> pd.DataFrame:
        return self._store.load_cross_section(
            trade_date, window=window, require_bands=require_bands,
        )

    def load_bb_breakout(
        self, trade_date: str, *, band: str = "upper", window: int = DEFAULT_WINDOW,
    ) -> pd.DataFrame:
        return self._store.load_bb_breakout(trade_date, band=band, window=window)

    def load_recent_history(
        self, *, n_trading_days: int = 60, end_date: Optional[str] = None,
        window: int = DEFAULT_WINDOW,
    ) -> pd.DataFrame:
        return self._store.load_recent_history(
            n_trading_days=n_trading_days, end_date=end_date, window=window,
        )

    def compute_and_update_bands(
        self, trade_dates: Optional[Sequence[str]] = None, *, n_history: int = 60,
        period: int = 20, nbdev: float = 2.0, ddof: int = 1,
        window: int = DEFAULT_WINDOW, only_missing: bool = False,
    ) -> dict[str, int]:
        return self._store.compute_and_update_bands(
            trade_dates=trade_dates, n_history=n_history, period=period,
            nbdev=nbdev, ddof=ddof, window=window, only_missing=only_missing,
        )

    def compute_all_bands_vectorized(
        self, *, period: int = 20, nbdev: float = 2.0, ddof: int = 1,
        window: int = DEFAULT_WINDOW,
    ) -> dict[str, int]:
        return self._store.compute_all_bands_vectorized(
            period=period, nbdev=nbdev, ddof=ddof, window=window,
        )

    def list_trade_dates(self, *, window: int = DEFAULT_WINDOW) -> list[str]:
        return self._store.list_trade_dates(window=window)

    def has_trade_date(self, trade_date: str, *, window: int = DEFAULT_WINDOW) -> bool:
        return self._store.has_trade_date(trade_date, window=window)

    def distribution_stats(
        self, trade_date: Optional[str] = None, *, window: int = DEFAULT_WINDOW,
    ) -> dict[str, float]:
        return self._store.distribution_stats(trade_date, window=window)
