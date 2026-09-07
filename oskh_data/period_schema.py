# -*- coding: utf-8 -*-
"""Period / adjust-type helpers for local hive reads (no QMT download)."""
from __future__ import annotations

from typing import Tuple

import pandas as pd


class StockDataManager:
    """Period and adjust-type constants for local parquet reads."""

    ADJUST_MAPPING = {
        "none": "none",
        "front": "front",
        "back": "back",
    }

    PERIOD_MAPPING = {
        "1m": ("1分钟", True),
        "5m": ("5分钟", True),
        "10m": ("10分钟", True),
        "15m": ("15分钟", True),
        "30m": ("30分钟", True),
        "1h": ("60分钟", True),
        "1d": ("日线", False),
        "1w": ("周线", False),
        "1M": ("月线", False),
    }

    @classmethod
    def validate_period(cls, period: str) -> bool:
        return period in cls.PERIOD_MAPPING

    @classmethod
    def is_minute_period(cls, period: str) -> bool:
        return cls.PERIOD_MAPPING.get(period, (None, False))[1]

    @classmethod
    def get_period_name(cls, period: str) -> str:
        return cls.PERIOD_MAPPING.get(period, ("未知周期", False))[0]

    @classmethod
    def get_recommended_adjust_type(cls, period: str) -> str:
        return "none" if cls.is_minute_period(period) else "front"


class PeriodDataManager:
    """Time-range checks for local hive reads."""

    @staticmethod
    def validate_time_range(
        period: str, start_time: str, end_time: str
    ) -> Tuple[bool, str]:
        _ = period
        try:
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            if start_dt > end_dt:
                return False, "开始时间不能晚于结束时间"
            return True, "时间范围有效"
        except Exception as e:
            return False, f"时间格式错误: {e}"
