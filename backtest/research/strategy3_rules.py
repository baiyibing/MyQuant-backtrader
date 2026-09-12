"""策略 3 卖点与涨停保留纯函数。"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v3"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
STOP_PCT = 0.04
PROFIT_TARGET = 0.20
RESERVE_START_HM = 9 * 60 + 30
RESERVE_END_HM = 9 * 60 + 40

HELP_LOCK = """
策略 3 卖点（--strategy version3）：
  止损 4%；持仓至少一个交易日后，盈利达到 20% 时止盈。
  分钟 09:30–09:40 逐根重估涨停保留；窗口后开板立即按该分钟收盘卖出。
  日线近似：开盘达到昨收涨停价即 reserved，这不等同于分钟窗口。
  日线近似：reserved 且收盘仍涨停时不做 20% 止盈；收盘开板则当日收盘卖。
  日线近似：开板收盘同时跌停时不成交，挂 open_board 到下一可卖开盘。
  买入日不卖；不叠加 lot；peak_gap_min=0。
"""


def take_profit_reason(
    px: float, cost: float, peak: float, n_days: int
) -> Optional[str]:
    """盈利达到 20% 时返回止盈 reason；峰值不参与目标判断。"""
    del peak
    if int(n_days) < 1:
        return None
    px = float(px)
    cost = float(cost)
    if cost > 0 and px >= cost * (1.0 + PROFIT_TARGET):
        return "profit_take:target"
    return None


def reserve_step_minute(
    *, reserved: bool, hm: int, is_limit_up: bool
) -> tuple[bool, Optional[str]]:
    """推进一分钟涨停保留状态，并在窗口后首次开板时发出卖出原因。"""
    reserved = bool(reserved)
    hm = int(hm)
    is_limit_up = bool(is_limit_up)
    if RESERVE_START_HM <= hm < RESERVE_END_HM:
        return is_limit_up, None
    if reserved and not is_limit_up:
        return False, "open_board"
    return reserved, None


def record_strategy3_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_target"] = PROFIT_TARGET
    st.stats["reserve_limit_up"] = True
