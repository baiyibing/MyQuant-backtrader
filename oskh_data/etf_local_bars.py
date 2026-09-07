# -*- coding: utf-8 -*-
"""ETF local fund_daily — StockDataReader + YYYYMMDD index shaper (no QMT session).

Used by ``strategies.etf_rotation`` after ① desession. Independent of global
``DAILY_BARS_SOURCE=duckdb`` (that flag is banned for live/paper readiness).
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import pandas as pd

from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

_READER_HOLDER: Dict[str, Any] = {"reader": None}
_READER_LOCK = threading.Lock()
_READ_LOCK = threading.Lock()  # StockDataReader persistent con is not thread-safe


def reader_df_to_fund_daily_df(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Shape ``StockDataReader`` OHLCV (``time`` ms) → fund_daily-like frame.

    - Index: ``YYYYMMDD`` strings (sorted ascending)
    - Drop ``symbol`` / ``time`` columns
    - Keep OHLCV (+ amount when present)
    """
    if df is None or getattr(df, "empty", True):
        return pd.DataFrame()
    out = df.copy()
    if "time" in out.columns:
        out.index = pd.to_datetime(out["time"], unit="ms").dt.strftime("%Y%m%d")
        out = out.drop(columns=["time"])
    else:
        # Already datetime-like index from some reader modes
        try:
            out.index = pd.to_datetime(out.index).strftime("%Y%m%d")
        except (TypeError, ValueError):
            out.index = pd.Index([str(x) for x in out.index])
    if "symbol" in out.columns:
        out = out.drop(columns=["symbol"])
    keep = [c for c in ("open", "high", "low", "close", "volume", "amount") if c in out.columns]
    if not keep:
        return pd.DataFrame()
    shaped = out.loc[:, keep].sort_index()
    if not isinstance(shaped, pd.DataFrame):
        return pd.DataFrame()
    return shaped


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
    etf: str,
    start_date: str,
    end_date: str,
    adjust: str = "front",
    **kwargs: Any,
) -> pd.DataFrame:
    """Local ETF bars for RSRS; never opens a miniQMT session."""
    _ = kwargs
    symbol = str(etf or "").strip().upper()
    if not symbol:
        return pd.DataFrame()
    adj = str(adjust or "front").strip().lower() or "front"
    try:
        reader = get_etf_stock_data_reader()
    except FileNotFoundError as exc:
        logger.warning(
            "ETF DuckDB missing; fund_daily returns empty",
            context={"error": str(exc)[:200], "symbol": symbol},
        )
        return pd.DataFrame()
    except Exception as exc:
        logger.warning(
            "ETF reader init failed; fund_daily returns empty",
            context={"error_type": type(exc).__name__, "error": str(exc)[:200]},
        )
        return pd.DataFrame()
    try:
        with _READ_LOCK:
            df = reader.read_stock(
                symbol,
                start_time=str(start_date).strip(),
                end_time=str(end_date).strip(),
                period="1d",
                adjust_type=adj,
            )
    except Exception as exc:
        logger.warning(
            "ETF read_stock failed; fund_daily returns empty",
            context={
                "symbol": symbol,
                "start": start_date,
                "end": end_date,
                "adjust": adj,
                "error_type": type(exc).__name__,
                "error": str(exc)[:200],
            },
        )
        return pd.DataFrame()
    return reader_df_to_fund_daily_df(df)


__all__ = [
    "default_etf_fund_daily",
    "get_etf_stock_data_reader",
    "reader_df_to_fund_daily_df",
]
