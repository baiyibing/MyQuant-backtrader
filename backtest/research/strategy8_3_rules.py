"""策略 8 里程碑 8.3 — 9b4b7e2「利弗莫尔宿主包」冻结本。

卖点数学不在此重冻：``backtest.research.livermore_exit_rules`` 就是当年
从本包冻结出去的副本（030d138 宿主书换轨时留下，可执行行逐行一致），
本书直接委托它，避免第三份拷贝漂移。本模块只补当年宿主包的买侧/仓位
钩子；引擎行为跟随现行宿主。对应提交 9b4b7e2「lock v8 Livermore host
package」。

买侧钩子：首笔 50 万试探、同码再加须现价≥成本且该码峰值已到 +3%、
上证十日线两日下方停开新仓且已持不可加。
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Mapping, Optional

from backtest.research.livermore_exit_rules import (
    BAND2_ABS_MULT,
    BAND3_GLOBAL_MULT,
    BAND3_KEEP,
    BAND4_KEEP,
    BAND5_KEEP,
    BAND_ARMS,
    GIVEBACK_MULT,
    STALE_DAYS,
    take_profit_reason as take_profit_reason,
)
from backtest.research.market_layer import as_date
from backtest.research.strategy7_rules import build_index_gate

BOOK_TAG = "v8_3"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.10
PROBE_FRAC = 0.50
ADD_PEAK_MULT = 1.03
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = True


def lot_budget(name_budget: float, lots) -> float:
    """首笔试探 PROBE_FRAC，加仓用剩余额度。"""
    budget = float(name_budget)
    if not lots:
        return budget * PROBE_FRAC
    return budget * (1.0 - PROBE_FRAC)


def may_add(lots, px: float) -> bool:
    """只加赢家，且该码至少一笔峰值已到 +3%。"""
    if not lots:
        return True
    mark = float(px)
    if mark <= 0:
        return False
    if not all(mark >= float(p.cost) for p in lots):
        return False
    return any(float(p.peak) >= float(p.cost) * ADD_PEAK_MULT for p in lots)


def build_sse_ma10_block_new(
    closes: Mapping[date, float], *, symbol: str = INDEX_SYMBOL
) -> dict[date, bool]:
    """上证连续两日收于十日线下 → 次日（第三日）起 `True`=停买（含加仓）。"""
    return build_index_gate(closes, symbol=symbol)


def allow_new_name_from_gate(
    block_new: Optional[Mapping[date, bool]],
) -> Optional[Callable]:
    """`allow_new_name(day) -> bool`；False 时新开与加仓都不做。缺会话不拦。"""
    if block_new is None:
        return None

    def allow(day) -> bool:
        return not bool(block_new.get(as_date(day), False))

    return allow


HELP_LOCK = """
策略 8.3 卖点（--strategy version8_3，9b4b7e2 利弗莫尔宿主包冻结）：
  止损 10 个点（T+1 起）。回撤止盈档位 6%/15%/50%/100%（价格比较）：
        (0,6%]→不评档位回撤；
        [6%,15%)→买入价 ×1.02；
        [15%,50%)→max(买入价 ×1.15, 保留涨幅 60%)；
        [50%,100%)→保留涨幅 70%；
        [100%,∞)→保留涨幅 80%。
  T+1 起评止盈。分钟回撤须距峰值 ≥15 分钟（隔夜/午休视为满足）。
  满 8 个交易日且峰值从未到 +6% → force_sell:stale。
  per_name（默认）：每股票预算 100 万；首笔 50 万试探，同码可再加 50 万
        （独立 lot），须现价不低于成本且峰值已到 +3%。
        现金不足记 skip_cash。
  上证 000001.SH：连续两个交易日收于十日线下，第三个交易日起不买新票
        且已持不可加仓（仍可卖出）；昨收回到十日线上方后次日恢复。只用昨收。
  落盘：backtest_output/csv_{daily|minute}_v8_3_{start}_{end}/
"""


def record_strategy8_3_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["band_arms"] = list(BAND_ARMS)
    st.stats["band_keeps"] = [
        float(BAND3_KEEP),
        float(BAND4_KEEP),
        float(BAND5_KEEP),
    ]
    st.stats["band1_min_mult"] = 0.0
    st.stats["band_trail_min_mult"] = 1.06
    st.stats["band2_abs_mult"] = float(BAND2_ABS_MULT)
    st.stats["band3_global_mult"] = float(BAND3_GLOBAL_MULT)
    st.stats["band3_keep"] = float(BAND3_KEEP)
    st.stats["band4_keep"] = float(BAND4_KEEP)
    st.stats["band5_keep"] = float(BAND5_KEEP)
    st.stats["giveback_mult"] = float(GIVEBACK_MULT)
    st.stats["stale_days"] = int(STALE_DAYS)
    st.stats["probe_frac"] = float(PROBE_FRAC)
    st.stats["add_peak_mult"] = float(ADD_PEAK_MULT)
    st.stats["t1_trail"] = True
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["index_ma"] = int(INDEX_MA)
    st.stats["index_below_sessions"] = int(INDEX_BELOW_SESSIONS)
    st.stats["index_symbol"] = INDEX_SYMBOL
    st.stats["index_blocks_add"] = bool(INDEX_BLOCKS_ADD)
