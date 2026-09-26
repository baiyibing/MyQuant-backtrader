"""策略 8 里程碑 8.4 — stop10-tp10-reserve 上把止盈改为 20%。

止损 10%，T+1 起现价达到买价 +20% 止盈，涨停保留至开板。名单再现开独立持仓、
各持仓独立 +20% 台阶、上证十日线两日下方停开新仓（已持可加）留在本书。
+10% 止盈的对照留在
``backtest_output/csv_minute_v8_20251023_20260909_v8_stop10_tp10_reserve/``
和 ``backtest_output/csv_minute_v8_4_20251023_20260909/``。
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Mapping, Optional

from backtest.research.market_layer import as_date
from backtest.research.strategy7_rules import build_index_gate

BOOK_TAG = "v8_4"
ALLOW_ADD = True
PEAK_GAP_MIN = 0

STOP_PCT = 0.10
PROFIT_TARGET = 0.20
STALE_DAYS = 0
GIVEBACK_MULT = 0.0
ADD_STEP = 0.20
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = False
INDEX_GATE_ON = True
RESERVE_LIMIT_UP = True
DEFER_LIMIT_UP = False


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
    """T+1 起现价 ≥ 买价×1.20 → profit_take:target。峰值不参与。无僵持。"""
    del peak
    if int(n_days) < 1:
        return None
    if cost <= 0 or px <= 0:
        return None
    if float(px) >= float(cost) * (1.0 + float(PROFIT_TARGET)):
        return "profit_take:target"
    return None


HELP_LOCK = """
策略 8.4 卖点（--strategy version8_4，stop10-tp10-reserve 止盈改 20%）：
  止损 10 个点（T+1 起）。T+1 起现价≥买入价×1.20 → profit_take:target。
        峰值不参与。无六档回撤、无 giveback、无僵持。
  遇涨停保留至开板（与策略 3 同一分钟窗 09:30–09:40；开板按该分钟收盘卖）。
  per_name（默认）：名单每个代码+信号日期各开独立持仓（position_id）；
        后日再现是新仓，不受旧仓盈亏影响；各持仓首买预算 100 万。
        首买/追买按新仓经过指数 gate；追买保留原信号身份和预算。
        相对各持仓自己的首笔成本每满 +20% 加 100 万；名单外也评。
        分钟 14:55 扫描（沿用尾盘缺 bar 回退），日线收盘扫描；每持仓每日最多一级，
        成交后记录历史级数，step lot 卖出不回退；全部 lots 卖完即关闭。
        各 lot 按自身成本、峰值、T+1 和止损/止盈独立退出，互不连带。
        任一买单所需现金（含费用）不足即 InsufficientCashError，停止回测。
  上证十日线两日下方停开新仓（含名单再现）；旧持仓价格台阶仍可加。峰值判定不延时（peak_gap_min=0）。
  落盘：backtest_output/csv_{daily|minute}_v8_4_{start}_{end}/
"""


def record_strategy8_4_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_target"] = float(PROFIT_TARGET)
    st.stats["stale_days"] = int(STALE_DAYS)
    st.stats["giveback_mult"] = float(GIVEBACK_MULT)
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
