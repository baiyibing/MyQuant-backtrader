"""策略 8 里程碑 8.5 — 8.4 止盈改 4%，峰差 30 分钟，未到 +4% 的 T+4 收盘清。

买侧与止损、涨停保留、名单加仓、+20% 台阶、上证闸沿用 8.4。
T+4 清仓不进四参止盈函数，由 opt-in ``t4_close_reason`` 在收盘评估。
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Mapping, Optional

from backtest.research.market_layer import as_date
from backtest.research.strategy7_rules import build_index_gate

BOOK_TAG = "v8_5"
ALLOW_ADD = True
PEAK_GAP_MIN = 30

STOP_PCT = 0.10
PROFIT_TARGET = 0.04
T4_CLOSE_DAYS = 4
ADD_STEP = 0.20
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = False
INDEX_GATE_ON = True
RESERVE_LIMIT_UP = True
DEFER_LIMIT_UP = False
T4_CLOSE_REASON = "force_sell:t4_close"
SAME_BAR_PREFIXES = ("open_board", T4_CLOSE_REASON)


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


def step_add_due(lots, px: float, step: float = ADD_STEP) -> bool:
    """相对仍开着的 lot 0 成本，每满 +step 且已有 is_step 数不足则加。"""
    if float(step) <= 0 or float(px) <= 0 or not lots:
        return False
    parent = next((p for p in lots if int(getattr(p, "lot_id", -1)) == 0), None)
    if parent is None:
        return False
    cost = float(getattr(parent, "cost", 0) or 0)
    if cost <= 0:
        return False
    n_steps = sum(1 for p in lots if getattr(p, "is_step", False))
    allowed = int((float(px) / cost - 1.0) / float(step) + 1e-12)
    return allowed > n_steps


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


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """T+1 起现价 ≥ 买价×1.04 → profit_take:target。峰值不参与。不含 T+4 清仓。"""
    del peak
    if int(n_days) < 1:
        return None
    if cost <= 0 or px <= 0:
        return None
    if float(px) >= float(cost) * (1.0 + float(PROFIT_TARGET)):
        return "profit_take:target"
    return None


def t4_close_reason(cost: float, peak: float, n_days: int) -> Optional[str]:
    """持仓最高价一直 < 买价×1.04 时，T+4 及之后的收盘清仓。"""
    if int(n_days) < int(T4_CLOSE_DAYS):
        return None
    if float(cost) <= 0 or float(peak) <= 0:
        return None
    if float(peak) < float(cost) * (1.0 + float(PROFIT_TARGET)):
        return T4_CLOSE_REASON
    return None


HELP_LOCK = """
策略 8.5 卖点（--strategy version8_5，8.4 止盈改 4% / 峰差 30 / T+4 收盘清）：
  止损 10 个点（T+1 起，先于止盈和 T+4 清仓）。
  T+1 起现价≥买入价×1.04 → profit_take:target。峰值不参与目标价。
  峰值判定延时 30 分钟（同会话创新高后 30 分钟内不评 +4% 止盈；
        隔夜/午休 gap<0 视为满足）。不挡住止损、开板、T+4 收盘清。
  持仓最高价（T+1 起累计）一直 < 买入价×1.04 → T+4 收盘
        force_sell:t4_close。最高价一旦 ≥ ×1.04，这条作废。
        分钟卖在 15:00 那根收盘；当日没有 15:00 则用最后一根。
        跌停卖不出则顺延到下一可卖日收盘。
  遇涨停保留至开板（与策略 3 同一分钟窗 09:30–09:40）。
  per_name（默认）：每股票预算 100 万；同码可加仓（独立 lot，输家也加）。
        相对第一笔成本每满 +20% 再加一个独立台阶（名单外也评）。
        现金不足记 skip_cash。
  上证十日线两日下方停开新仓、已持可加。
  无六档回撤、无 giveback、无满 N 日一律僵持。
  落盘：backtest_output/csv_{daily|minute}_v8_5_{start}_{end}/
"""


def record_strategy8_5_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_target"] = float(PROFIT_TARGET)
    st.stats["t4_close_days"] = int(T4_CLOSE_DAYS)
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
