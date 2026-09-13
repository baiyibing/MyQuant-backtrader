"""策略 9（底量超顶量）卖点纯函数。

买点不在本模块：由 ``export_strategy9_pool.py`` 写成契约日 CSV，引擎按名单买。
卖：止损 8%；持仓满 20 个交易日收盘记 ``force_sell:max_hold``，次日开盘离场。
不加仓。禁止默认 ``stock_pool/``（那是隔夜手工池，不是本信号）。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v9"
ALLOW_ADD = False
PEAK_GAP_MIN = 0

STOP_PCT = 0.08
MAX_HOLD = 20
REQUIRES_EXPLICIT_POOL = True

HELP_LOCK = """
策略 9 卖点（--strategy version9）：
  买点 = 底量超顶量名单（export_strategy9_pool.py），不是 stock_pool/。
  必须显式 --pool-dir；指向本仓 stock_pool/ 立即退出。
  止损 8 个点，由引擎执行。无分档回撤止盈。
  持仓交易日数 n_days>=20 收盘记 force_sell:max_hold，次日开盘卖
  （跌停则 defer）。已持仓票跳过，不叠加 lot；peak_gap_min=0。
  落盘：backtest_output/csv_{daily|minute}_v9_{start}_{end}/
"""


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """满持有期返回 force_sell；价格参数仅满足策略书钩子签名。"""
    del px, cost, peak
    if int(n_days) >= MAX_HOLD:
        return "force_sell:max_hold"
    return None


def record_strategy9_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["max_hold"] = MAX_HOLD
