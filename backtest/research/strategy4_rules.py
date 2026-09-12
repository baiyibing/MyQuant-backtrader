"""策略 4 均线买卖闸；均线输入刻意不含今日收盘。"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v4"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
STOP_PCT = None
MA_BUY = 10
MA_SELL = 5

HELP_LOCK = """
策略 4 卖点（--strategy version4）：
  无止损；买入价须不低于截至昨收 SMA10，历史不足 10 根则不买。
  卖出用截至昨收 SMA5；现价跌破 SMA5 记 ma_signal:MA5，日线次日开盘卖。
  SMA5 历史不足时冻仓不卖；尾盘涨停后的追买也须通过 buy_gate。
  追买日的“昨收”包含信号日收盘（不是 bug）；不使用 chip_indicator/StockDataReader。
"""


def sma_asof(closes: list[float], n: int) -> Optional[float]:
    n = int(n)
    if n <= 0 or len(closes) < n:
        return None
    return sum(float(x) for x in closes[-n:]) / n


def buy_gate(code, px, day, daily_closes_ending_yesterday) -> bool:
    del code, day
    sma10 = sma_asof(daily_closes_ending_yesterday, MA_BUY)
    return sma10 is not None and float(px) >= sma10


def sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]:
    del code, day
    sma5 = sma_asof(daily_closes_ending_yesterday, MA_SELL)
    if sma5 is not None and float(px) < sma5:
        return "ma_signal:MA5"
    return None


def take_profit_reason(px, cost, peak, n_days) -> None:
    del px, cost, peak, n_days
    return None


def record_strategy4_params(st, *, stop_pct=None) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = stop_pct
    st.stats["ma_buy"] = MA_BUY
    st.stats["ma_sell"] = MA_SELL
