"""策略 1 卖点纯函数。

止损由引擎按 2% 执行；止盈仅在仍有浮盈时，按峰值至成本之间的利润
回撤达到 50% 触发。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v1"
ALLOW_ADD = False
PEAK_GAP_MIN = 0

STOP_PCT = 0.02
PROFIT_DRAWDOWN_PCT = 0.50

HELP_LOCK = """
策略 1 卖点（--strategy version1）：
  止损 2 个点，由引擎执行。仅当现价不低于成本且峰值高于成本时，
  计算 (峰值-现价)/(峰值-成本)；利润回撤达到 50% 时止盈。
  日线止盈先记 pending_exit，于下一交易日开盘卖出。
  已持仓票跳过，不叠加 lot；peak_gap_min=0。
"""


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """利润回撤达到 50% 时返回止盈 reason。"""
    del n_days
    px = float(px)
    cost = float(cost)
    peak = float(peak)
    if px < cost or peak <= cost:
        return None
    drawdown = (peak - px) / (peak - cost)
    if drawdown >= PROFIT_DRAWDOWN_PCT:
        return "profit_take:drawdown:50"
    return None


def record_strategy1_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_drawdown_pct"] = PROFIT_DRAWDOWN_PCT
