"""策略 8（金榕元交易回测）卖点纯函数 — 利弗莫尔宿主包。

止损 10%。关键点 +6% 前不评档位回撤。
档2 [6%,15%) 买价×1.02；档3 [15%,50%) max(买价×1.15, 保留 60%)；
档4 [50%,100%) 保留 70%；档5 ≥100% 保留 80%。
T+1 起评止盈；分钟回撤须距峰值 ≥15 分钟。
满 8 个交易日且峰值从未到 +6% 记僵持清仓。
首笔 50 万试探，同码再加 50 万须现价≥成本且该码峰值≥+3%。
上证连续两日收于十日线下则停开新仓且已持不可加。
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Mapping, Optional

from backtest.research.market_layer import as_date
from backtest.research.strategy7_rules import build_index_gate

BOOK_TAG = "v8"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.10

BAND_ARMS: tuple[float, ...] = (0.06, 0.15, 0.50, 1.00)
BAND1_MIN_MULT = 0.0
BAND_TRAIL_MIN_MULT = 1.06
BAND2_ABS_MULT = 1.02
BAND3_KEEP = 0.60
BAND3_GLOBAL_MULT = 1.15
BAND4_KEEP = 0.70
BAND5_KEEP = 0.80
GIVEBACK_MULT = 0.0
STALE_DAYS = 8
PROBE_FRAC = 0.50
ADD_PEAK_MULT = 1.03
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = True


def stop_hits(px: float, cost: float, stop_pct: float = STOP_PCT) -> bool:
    if cost <= 0 or px <= 0:
        return False
    return float(px) / float(cost) - 1.0 <= -float(stop_pct)


def band_of(cost: float, peak: float) -> Optional[int]:
    """峰值所在档 1..5；peak≤cost 返回 None。

    价格比较：(0,6%) / [6%,15%) / [15%,50%) / [50%,100%) / [100%,∞)。
    """
    c = float(cost)
    p = float(peak)
    if c <= 0 or p <= c:
        return None
    if p < c * (1.0 + BAND_ARMS[0]):
        return 1
    if p < c * (1.0 + BAND_ARMS[1]):
        return 2
    if p < c * (1.0 + BAND_ARMS[2]):
        return 3
    if p < c * (1.0 + BAND_ARMS[3]):
        return 4
    return 5


def trigger_line(cost: float, peak: float, band: int) -> float:
    """档位触发线（px ≤ 线则止盈）。"""
    c = float(cost)
    p = float(peak)
    if band == 1:
        return c
    if band == 2:
        return c * BAND2_ABS_MULT
    if band == 3:
        return max(c * BAND3_GLOBAL_MULT, c + BAND3_KEEP * (p - c))
    if band == 4:
        return c + BAND4_KEEP * (p - c)
    return c + BAND5_KEEP * (p - c)


def never_armed(cost: float, peak: float) -> bool:
    """峰值从未进入档2（与 band_of 同一套价格比较）。"""
    b = band_of(cost, peak)
    return b is None or b == 1


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


def load_sse_ma10_block_new(start: str, end: str, *, root=None) -> dict[date, bool]:
    """从指数日线湖装载上证收盘并生成停买表。"""
    from backtest.research.csv_daily_loader import load_index_daily_closes

    closes = load_index_daily_closes(start, end, symbol=INDEX_SYMBOL, root=root)
    return build_sse_ma10_block_new(closes)


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """触发离场则返回 reason（供 CSV `_sell` 使用）。

    n_days<1（T+0）不评估。T+1 起评止盈。
    无 giveback。满 8 日且从未武装记 stale。px<cost 不评档位回撤。
    峰值 (0,6%] 不评档位回撤。无 1.01 底。
    reason=`trail:band:{1..5}`。
    """
    if int(n_days) < 1:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if GIVEBACK_MULT > 0 and float(px) <= float(cost) * GIVEBACK_MULT:
        return "force_sell:giveback"
    if STALE_DAYS > 0 and int(n_days) >= STALE_DAYS and never_armed(cost, peak):
        return "force_sell:stale"
    if float(px) < float(cost):
        return None
    if BAND_TRAIL_MIN_MULT > 1.0 and float(peak) <= float(cost) * BAND_TRAIL_MIN_MULT:
        return None
    band = band_of(cost, peak)
    if band is None:
        return None
    if band == 1 and BAND1_MIN_MULT > 1.0 and float(px) < float(cost) * BAND1_MIN_MULT:
        return None
    line = trigger_line(cost, peak, band)
    if float(px) <= line:
        return f"trail:band:{band}"
    return None


HELP_LOCK = """
策略 8 卖点（--strategy version8）利弗莫尔宿主包：
  止损 10 个点（T+1 起）。回撤止盈档位 6%/15%/50%/100%（价格比较）：
        (0,6%]→不评档位回撤；
        [6%,15%)→买入价 ×1.02；
        [15%,50%)→max(买入价 ×1.15, 保留涨幅 60%)；
        [50%,100%)→保留涨幅 70%；
        [100%,∞)→保留涨幅 80%。
  T+1 起评止盈。分钟回撤须距峰值 ≥15 分钟（隔夜/午休视为满足）。
  满 8 个交易日且峰值从未到 +6% → force_sell:stale。
  per_name（默认）：每股票预算 100 万；首笔 50 万试探，同码可再加 50 万
        （独立 lot，单码单日上限 2 笔），须现价不低于成本且峰值已到 +3%。
        现金不足记 skip_cash。
  上证 000001.SH：连续两个交易日收于十日线下，第三个交易日起不买新票
        且已持不可加仓（仍可卖出）；昨收回到十日线上方后次日恢复。只用昨收。
  跌停：任何卖因成交前跌停则 defer，次日再评（不只 stop_loss）。
  落盘：backtest_output/csv_{daily|minute}_v8_{start}_{end}/
"""


def record_strategy8_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["band_arms"] = list(BAND_ARMS)
    st.stats["band_keeps"] = [
        float(BAND3_KEEP),
        float(BAND4_KEEP),
        float(BAND5_KEEP),
    ]
    st.stats["band1_min_mult"] = float(BAND1_MIN_MULT)
    st.stats["band_trail_min_mult"] = float(BAND_TRAIL_MIN_MULT)
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
