"""策略 2 卖点纯函数。

止损由引擎按 2% 执行；止盈阈值随 CSV 引擎持仓日数递减。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v2"
ALLOW_ADD = False
PEAK_GAP_MIN = 0

STOP_PCT = 0.02
DRAWDOWN_THRESHOLDS = {1: 0.50, 2: 0.40, 3: 0.30, 4: 0.20, 5: 0.10}

HELP_LOCK = """
策略 2 卖点（--strategy version2）：
  止损 2 个点，由引擎执行。利润回撤阈值为 T+1=50%、T+2=40%、
  T+3=30%、T+4=20%、T+5+=10%；现价低于成本或峰值未高于成本不评。
  CSV 引擎买入日 n_days=0，故当日不止盈；这与化石的 max(1, hold_days)
  语义有意不同。日线止盈先记 pending_exit，于下一交易日开盘卖出。
  已持仓票跳过，不叠加 lot；peak_gap_min=0。
"""


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """按持仓日数对应阈值判断利润回撤。"""
    n_days = int(n_days)
    if n_days < 1:
        return None
    px = float(px)
    cost = float(cost)
    peak = float(peak)
    if px < cost or peak <= cost:
        return None
    threshold = DRAWDOWN_THRESHOLDS.get(
        n_days, DRAWDOWN_THRESHOLDS[max(DRAWDOWN_THRESHOLDS)]
    )
    drawdown = (peak - px) / (peak - cost)
    if drawdown >= threshold:
        return f"profit_take:drawdown:T+{n_days}"
    return None


def record_strategy2_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    for n_days, threshold in DRAWDOWN_THRESHOLDS.items():
        st.stats[f"drawdown_t{n_days}"] = float(threshold)
