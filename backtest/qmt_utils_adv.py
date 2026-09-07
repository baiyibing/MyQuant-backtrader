# -*- coding: utf-8 -*-
"""Cerebro-facing data helpers.

Hive reads go through ``common.infra.qmt_utils_adv`` / ``oskh_data.StockDataReader``
(path-SSOT). This fork does not download market data. Cerebro-only pieces
(``PrevClosePandasData``, ``load_single_stock_data``) stay here.
"""
from __future__ import annotations

import backtrader as bt
import pandas as pd

from common.infra.qmt_utils_adv import (  # noqa: F401
    add_prev_close_data,
    batch_format_stock_codes,
    check_bom,
    check_date_in_data,
    detect_encoding,
    ensure_datetime_index,
    format_stock_code,
    get_stock_data_from_cache,
    is_close,
    is_trading_day,
    read_stock_codes,
    to_datetime,
)

__all__ = [
    "PrevClosePandasData",
    "add_prev_close_data",
    "batch_format_stock_codes",
    "check_bom",
    "check_date_in_data",
    "detect_encoding",
    "ensure_datetime_index",
    "format_stock_code",
    "get_stock_data_from_cache",
    "is_close",
    "is_trading_day",
    "load_single_stock_data",
    "read_stock_codes",
    "to_datetime",
]


class PrevClosePandasData(bt.feeds.PandasData):
    """包含前收字段的自定义数据类"""

    lines = ("prev_close", "turnover_rate")
    params = (
        ("datetime", None),
        ("open", -1),
        ("high", -1),
        ("low", -1),
        ("close", -1),
        ("volume", -1),
        ("prev_close", -1),
        ("turnover_rate", -1),
    )


def load_single_stock_data(code, start_dt, end_dt, buy_date, adjust_type: str = "none"):
    """Load one symbol's 1m bars into a Cerebro feed (SSOT cache, no cwd hive)."""
    try:
        df = get_stock_data_from_cache(
            stock_code=code,
            period="1m",
            adjust_type=adjust_type,
            start_time=start_dt,
            end_time=end_dt,
        )
        if df is None or df.empty:
            print(f"⚠️ {code} 无分钟数据 {start_dt}..{end_dt}")
            return None, False
        df = ensure_datetime_index(df)
        if df is None or df.empty:
            return None, False

        print(f"📅 {code} 数据日期范围: {df.index.min()} 到 {df.index.max()}")

        df = add_prev_close_data(df, code, start_dt, end_dt, adjust_type=adjust_type)
        df = ensure_datetime_index(df)
        if df is None or df.empty:
            return None, False

        data_contains_buy_date = check_date_in_data(df, buy_date)
        if not data_contains_buy_date:
            print(f"⚠️ {code} 缺少买入日期 {buy_date} 的1m数据")
            return None, False

        df = df.copy().sort_index()
        data = PrevClosePandasData(
            dataname=df,
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
            prev_close="prevclose",
            timeframe=bt.TimeFrame.Minutes,
            compression=1,
            fromdate=pd.to_datetime(start_dt),
            todate=pd.to_datetime(end_dt),
        )
        return data, True
    except Exception as e:
        print(f"❌ {code} 数据加载失败: {e}")
        import traceback

        print(traceback.format_exc())
        return None, False
