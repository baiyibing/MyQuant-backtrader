"""策略 8 里程碑 8.6 — 止损 2%，保底 +0.4% 并保留最高涨幅 80%，到过保底后跌破线即卖。

没摸到买价×1.004 的仓 T+1 收盘清。峰差 15 分钟、涨停保留、名单再现独立开仓、上证闸沿用。
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Mapping, Optional

from backtest.research.market_layer import as_date
from backtest.research.strategy7_rules import build_index_gate

BOOK_TAG = "v8_6"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.02
FLOOR_MULT = 1.004
KEEP_FRAC = 0.80
T1_CLOSE_DAYS = 1
ADD_STEP = 0.0
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = False
INDEX_GATE_ON = True
RESERVE_LIMIT_UP = True
DEFER_LIMIT_UP = False
T1_CLOSE_REASON = "force_sell:t1_close"
TRAIL_REASON = "trail:max1004_80"
SAME_BAR_PREFIXES = ("open_board", T1_CLOSE_REASON)


def stop_hits(px: float, cost: float, stop_pct: float = STOP_PCT) -> bool:
    if cost <= 0 or px <= 0:
        return False
    return float(px) / float(cost) - 1.0 <= -float(stop_pct)


def lot_budget(name_budget: float, _lots) -> float:
    """每笔都是整笔 name_budget。"""
    return float(name_budget)


def may_add(lots, px: float) -> bool:
    """已持且现价有效即加（输家也加）。"""
    return bool(lots) and float(px) > 0


def build_sse_ma10_block_new(
    closes: Mapping[date, float], *, symbol: str = INDEX_SYMBOL
) -> dict[date, bool]:
    """上证连续两日收于十日线下 → 次日（第三日）起 `True`=停买新票。"""
    return build_index_gate(closes, symbol=symbol)


def allow_new_name_from_gate(
    block_new: Optional[Mapping[date, bool]],
) -> Optional[Callable]:
    """`allow_new_name(day) -> bool`。本包 INDEX_GATE_ON=True，十日线下方停开新仓。"""
    if not INDEX_GATE_ON or block_new is None:
        return None

    def allow(day) -> bool:
        return not bool(block_new.get(as_date(day), False))

    return allow


def load_sse_ma10_block_new(start: str, end: str, *, root=None) -> dict[date, bool]:
    """从指数日线湖装载上证收盘并生成停买表。"""
    from backtest.research.csv_minute_backtest_v7 import load_index_daily

    def _ymd(value) -> date:
        text = str(value).replace("-", "")[:8]
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))

    closes = load_index_daily(_ymd(start), _ymd(end), root=root)
    return build_sse_ma10_block_new(closes)


def trail_line(cost: float, peak: float) -> float:
    """max(买价×1.004, 买价+最高涨幅×80%)。"""
    rise = max(0.0, float(peak) - float(cost))
    return max(float(cost) * float(FLOOR_MULT), float(cost) + float(KEEP_FRAC) * rise)


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """T+1 起峰值≥买价×1.004 后，现价≤保底线 → trail:max1004_80。

    保底是买价×1.004；线上再留最高涨幅的 80%。跌回买价下方也卖，不再等 2% 止损。
    不含 T+1 清仓。峰差由引擎挡住。
    """
    if int(n_days) < 1:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(peak) + 1e-12 >= float(cost) * float(FLOOR_MULT):
        if float(px) <= trail_line(cost, peak) + 1e-12:
            return TRAIL_REASON
    return None


def t1_close_reason(cost: float, peak: float, n_days: int) -> Optional[str]:
    """持仓最高价一直 < 买价×1.004 时，T+1 及之后的收盘清仓。"""
    if int(n_days) < int(T1_CLOSE_DAYS):
        return None
    if float(cost) <= 0 or float(peak) <= 0:
        return None
    if float(peak) < float(cost) * float(FLOOR_MULT):
        return T1_CLOSE_REASON
    return None


HELP_LOCK = """
策略 8.6 卖点（--strategy version8_6，止损 2% / 保底 +0.4% 留 80% 涨幅 / 跌破线即卖 / T+1 收盘清）：
  止损 2 个点（T+1 起，先于止盈和 T+1 清仓）。
  T+1 起峰值≥买入价×1.004 后，离场线 = max(买入价×1.004, 买入价+最高涨幅×80%)，
        现价≤该线 → trail:max1004_80。跌回买入价下方也卖，不再等 2% 止损。
  峰值判定延时 15 分钟（同会话创新高后 15 分钟内不评这条止盈；
        隔夜/午休 gap<0 视为满足）。不挡住止损、开板、T+1 收盘清。
  持仓最高价（T+1 起累计）一直 < 买入价×1.004 → T+1 收盘
        force_sell:t1_close。最高价一旦 ≥ ×1.004，这条作废，改走上面的保底线。
        分钟卖在 15:00 那根收盘；当日没有 15:00 则用最后一根。
        跌停卖不出则顺延到下一可卖日收盘。
  遇涨停保留至开板（与策略 3 同一分钟窗 09:30–09:40）。
  per_name（默认）：名单每个代码+信号日期各开独立持仓（position_id）；
        后日再现是新仓，不受旧仓盈亏影响；各持仓首买预算 100 万。
        首买/追买按新仓经过指数 gate；追买保留原信号身份和预算。
        追买保留原信号身份和预算；无价格加仓，单 lot 沿用原退出规则。
        按持仓加权成本整体评估止损/止盈/trail/stale（成本不含佣金）；
        peak 初始为首买价，T+1 起跟踪行情，加仓不重置；stale 从首买日计算。
        退出卖出该持仓全部可卖股。
        今日新增股遵守 T+1，次交易日首个可卖时机按原卖因加 |t1_deferred 卖出；
        跌停仍顺延，已挂起退出的持仓不再加仓；不同信号日期持仓互不连带。
        任一买单所需现金（含费用）不足即 InsufficientCashError，停止回测。
  上证十日线两日下方停开新仓（包括名单再现）。
  无六档回撤、无 giveback、无满 N 日一律僵持。
  落盘：backtest_output/csv_{daily|minute}_v8_6_{start}_{end}/
"""


def record_strategy8_6_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["floor_mult"] = float(FLOOR_MULT)
    st.stats["keep_frac"] = float(KEEP_FRAC)
    st.stats["max1004_80"] = True
    st.stats["t1_close_days"] = int(T1_CLOSE_DAYS)
    st.stats["bands6"] = False
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["reserve_limit_up"] = bool(RESERVE_LIMIT_UP)
    st.stats["defer_limit_up"] = bool(DEFER_LIMIT_UP)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["index_ma"] = int(INDEX_MA)
    st.stats["index_below_sessions"] = int(INDEX_BELOW_SESSIONS)
    st.stats["index_symbol"] = INDEX_SYMBOL
    st.stats["index_blocks_add"] = bool(INDEX_BLOCKS_ADD)
    st.stats["index_gate_on"] = bool(INDEX_GATE_ON)
    st.stats["allow_add"] = bool(ALLOW_ADD)
