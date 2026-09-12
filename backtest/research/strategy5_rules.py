"""策略 5 卖点纯函数。

无止损；持仓至少一个交易日后，盈利达到 2% 时止盈。14:50 强制卖出
属于分钟引擎时钟，不属于这个看不见分钟时间的四参函数。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v5"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
STOP_PCT = None
PROFIT_TARGET = 0.02
FORCE_SELL_HM = 14 * 60 + 50

HELP_LOCK = """
策略 5 卖点（--strategy version5）：
  无止损；持仓至少一个交易日后，现价相对成本盈利达到 2% 时止盈。
  分钟引擎在 T+1 起 14:50 强制卖出；同分钟先评 2% 止盈。
  日线没有分钟时钟，不做强制卖；2% 止盈先记 pending_exit，次日开盘卖出。
  买入日不止盈、不挂 pending、不强制卖；不叠加 lot；peak_gap_min=0。
"""


def take_profit_reason(px: float, cost: float, peak: float, n_days: int) -> Optional[str]:
    """盈利达到 2% 时返回止盈 reason；峰值不参与目标判断。"""
    del peak
    if int(n_days) < 1:
        return None
    px = float(px)
    cost = float(cost)
    if cost > 0 and px >= cost * (1.0 + PROFIT_TARGET):
        return "profit_take:target"
    return None


def record_strategy5_params(st, *, stop_pct=None) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = stop_pct
    st.stats["profit_target"] = PROFIT_TARGET
    st.stats["force_sell_hm"] = FORCE_SELL_HM
