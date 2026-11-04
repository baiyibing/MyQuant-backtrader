"""STAB_LOW_TREND T+1 收盘卖纯信号书（L2 大单 × Alpha158 信号线）。

信号：IMIN10<=q20 & QTLD30>=q80 & RSQR5>=q80，C1 大单阶跃池（MyQuant l2_signals）。
本仓只做执行研究：T 日收盘（分钟引擎 14:55）买入，T+1 收盘卖出，一日动量。

退出走 close_clear 钩子（日线=当日收盘扫描；分钟线=仅 15:00 bar），n_days>=1
即首个可卖收盘触发；日线侧配 daily_same_bar_prefixes 当日收盘价成交。
无止损（stop_pct=None，纯信号 v0），不加仓。
"""

from __future__ import annotations

BOOK_TAG = "stab_t1"
ALLOW_ADD = False
PEAK_GAP_MIN = 0

EXIT_N_DAYS_MIN = 1
EXIT_REASON = "stab_t1:exit"

HELP_LOCK = """
STAB_LOW_TREND T+1 收盘卖（--strategy stab_t1）：
  L2 大单 × Alpha158 信号（MyQuant l2_signals，C1 大单阶跃池）的执行研究书。
  T 日收盘买入（分钟引擎 14:55 bar），T+1 收盘卖出：close_clear 在首个
  可卖收盘（n_days>=1）触发 stab_t1:exit，日线经 daily_same_bar_prefixes
  当日收盘成交。无止损、不加仓、日额度等权（daily_quota）。
  涨跌停/停牌/T+1 锁由引擎统一处理（涨停跳过入追买桶，跌停延卖）。
"""


def close_clear_reason(cost: float, peak: float, n_days: int = 1) -> str | None:
    """首个可卖收盘（T+1）平仓。"""
    del cost, peak
    if n_days >= EXIT_N_DAYS_MIN:
        return EXIT_REASON
    return None


def never_take_profit(px: float, cost: float, peak: float, n_days: int = 1) -> str | None:
    """占位桩：注册表要求 take_profit 非 None；真逻辑在 close_clear。

    分钟引擎逐 bar 评估 take_profit，此处必须恒 None，否则会变成开盘附近卖出。
    """
    del px, cost, peak, n_days
    return None


def record_stab_t1_params(st) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["exit_n_days_min"] = EXIT_N_DAYS_MIN
    st.stats["stop_pct"] = None
