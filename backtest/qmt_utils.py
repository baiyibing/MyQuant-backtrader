# -*- coding: utf-8 -*-
"""Legacy keyword-first cache read for A5.py.

Market download lives in the original repo. This module only reads path-SSOT.
"""
from common.infra.qmt_utils_adv import get_stock_data_from_cache as _ssot_get


def get_stock_data_from_cache(
    base_dir="../stock_data",
    stock_code=None,
    period="1d",
    adjust_type="front",
    start_time=None,
    end_time=None,
):
    """Load OHLCV via path-SSOT. Legacy ``../stock_data`` is ignored."""
    if stock_code is None:
        print("请指定股票代码")
        return None
    kwargs = {}
    if base_dir not in (None, "", "../stock_data"):
        kwargs["base_dir"] = base_dir
    start = start_time if start_time is not None else "19900101"
    end = end_time if end_time is not None else "20991231"
    return _ssot_get(
        stock_code=stock_code,
        start_time=start,
        end_time=end,
        period=period,
        adjust_type=adjust_type,
        **kwargs,
    )
