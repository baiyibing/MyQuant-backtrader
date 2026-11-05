# -*- coding: utf-8 -*-
"""ETF local fund_daily — StockDataReader + YYYYMMDD index shaper (no QMT session).

Used by ``strategies.etf_rotation`` after ① desession. Independent of global
``DAILY_BARS_SOURCE=duckdb`` (that flag is banned for live/paper readiness).
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import pandas as pd
try:
    from myquant_infra.lake import etf_bars as _infra_etf_bars
except ImportError:  # CI without private pin
    class _InfraEtfBarsStub:
        @staticmethod
        def reader_df_to_fund_daily_df(df):
            raise ImportError("myquant-infra required for etf_bars")

        @staticmethod
        def default_etf_fund_daily(*args, **kwargs):
            raise ImportError("myquant-infra required for etf_bars")

    _infra_etf_bars = _InfraEtfBarsStub()  # type: ignore[assignment]

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

_READER_HOLDER: Dict[str, Any] = {"reader": None}
_READER_LOCK = threading.Lock()
_READ_LOCK = threading.Lock()  # StockDataReader persistent con is not thread-safe


def reader_df_to_fund_daily_df(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    return _infra_etf_bars.reader_df_to_fund_daily_df(df)


def get_etf_stock_data_reader(*, db_path: Optional[str] = None) -> Any:
    """Lazy singleton ``StockDataReader(asset_type='etf')`` (thread-safe init)."""
    reader = _READER_HOLDER.get("reader")
    if reader is not None and db_path is None:
        return reader
    with _READER_LOCK:
        reader = _READER_HOLDER.get("reader")
        if reader is not None and db_path is None:
            return reader
        from oskh_data.reader import StockDataReader

        reader = StockDataReader(
            mode="duckdb_persistent",
            asset_type="etf",
            db_path=db_path,
        )
        if db_path is None:
            _READER_HOLDER["reader"] = reader
        return reader


def default_etf_fund_daily(
    etf: str, start_date: str, end_date: str, adjust: str = "front", **kwargs: Any,
) -> pd.DataFrame:
    return _infra_etf_bars.default_etf_fund_daily(
        etf, start_date, end_date, adjust, reader_factory=get_etf_stock_data_reader,
        read_lock=_READ_LOCK, **kwargs,
    )


__all__ = ["default_etf_fund_daily", "get_etf_stock_data_reader", "reader_df_to_fund_daily_df"]
