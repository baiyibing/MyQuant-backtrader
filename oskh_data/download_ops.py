# -*- coding: utf-8 -*-
"""QMT download / local hive maintenance — SSOT outside backtest."""

from __future__ import annotations

from common.infra.quant_logger import get_logger
from .symbol_format import to_partition_key
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.infra.data_root import resolve_data_root
from oskh_data.downloader import DataDownloader

logger = get_logger(__name__)

_DEFAULT_STOCK_DATA_DIR = str(resolve_data_root() / "stock_data")


def download_market_data(
    stock_list: List[str],
    start_time: str,
    end_time: str,
    period: str = "1d",
    *,
    base_dir: str = _DEFAULT_STOCK_DATA_DIR,
    adjust_type: str = "front",
    incrementally: bool = False,
) -> Dict[str, Any]:
    """Download OHLCV from miniQMT into local parquet hive."""
    downloader = DataDownloader(base_dir)
    return downloader.download_data(
        stock_list,
        start_time,
        end_time,
        period,
        adjust_type,
        incrementally,
    )


def clear_local_market_data(
    base_dir: str = _DEFAULT_STOCK_DATA_DIR,
    period: Optional[str] = None,
    adjust_type: Optional[str] = None,
    stock_code: Optional[str] = None,
) -> None:
    """Remove parquet hive paths under *base_dir* (destructive)."""
    base_path = Path(base_dir)
    if not base_path.exists():
        logger.info("目录不存在，无需清理")
        return

    try:
        if period is None:
            shutil.rmtree(base_path)
            logger.info("清理所有数据")
            return
        from common.infra.data_root import resolve_period_root

        period_path = resolve_period_root(period, base=base_path)
        if adjust_type is None:
            if period_path.exists():
                shutil.rmtree(period_path)
                logger.info("清理周期 %s 所有数据", period)
            return
        adjust_path = period_path / f"dividend_type={adjust_type}"
        if stock_code is None:
            if adjust_path.exists():
                shutil.rmtree(adjust_path)
                logger.info("清理周期 %s 复权 %s 数据", period, adjust_type)
            return
        stock_path = adjust_path / f"symbol={to_partition_key(stock_code)}"
        if stock_path.exists():
            shutil.rmtree(stock_path)
            logger.info("清理股票 %s 数据", stock_code)
    except Exception as exc:
        logger.error("清理数据失败: %s", exc)


# Historical alias (pre-M-003 scripts)
get_miniqmt_data = download_market_data
clear_stock_data = clear_local_market_data

__all__ = [
    "clear_local_market_data",
    "clear_stock_data",
    "download_market_data",
    "get_miniqmt_data",
]
