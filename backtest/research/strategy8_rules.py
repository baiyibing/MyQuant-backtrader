"""策略 8（金榕元交易回测）卖点纯函数 — stop10-max101-80-gap15-reserve-stale8 包。

止损 10%。T+1 起离场线 max(买价×1.01, 买价+涨幅×80%)。峰值判定延时 15 分钟。
遇涨停保留至开板。满 8 日仍持有则僵持平仓。名单全加 + 独立 +20% 台阶。
上证十日线两日下方停开新仓、已持可加。无六档、无 giveback、无未武装快切。
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Mapping, Optional

from backtest.research.market_layer import as_date, board_limit_pct
from backtest.research.strategy7_rules import build_index_gate

BOOK_TAG = "v8"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.10
FLOOR_MULT = 1.01
KEEP_FRAC = 0.80
GIVEBACK_MULT = 0.0
STALE_DAYS = 8
STALE_UNARMED_ONLY = False
UNARMED_STOP_PCT = 0.0
TP_MIN_DAYS = 1
PROBE_FRAC = 1.0
ADD_PEAK_MULT = 0.0
ADD_STEP = 0.20
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = False
INDEX_GATE_ON = True
RESERVE_LIMIT_UP = True
DEFER_LIMIT_UP = False
DEFER_LIMIT_UP_20 = DEFER_LIMIT_UP


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


def is_cyb_star_board(code: Optional[str]) -> bool:
    """创业板 / 科创板（20% 板）。"""
    if not code:
        return False
    return board_limit_pct(str(code)) == 0.20


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
    """max(买价×1.01, 买价+涨幅×80%)。"""
    rise = max(0.0, float(peak) - float(cost))
    return max(float(cost) * float(FLOOR_MULT), float(cost) + float(KEEP_FRAC) * rise)


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """T+1 起峰值≥买价×1.01 后，现价≤max(×1.01, 买价+80%涨幅) → trail:max101_80。

    现价低于买价不止盈。满 8 日 → force_sell:stale。止盈先于僵持。
    峰差 15 分钟由引擎 PEAK_GAP_MIN 挡住，不在本函数里算。
    """
    if int(n_days) < 1:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(px) >= float(cost) and float(peak) + 1e-12 >= float(cost) * float(
        FLOOR_MULT
    ):
        if float(px) <= trail_line(cost, peak) + 1e-12:
            return "trail:max101_80"
    if STALE_DAYS > 0 and int(n_days) >= int(STALE_DAYS):
        return "force_sell:stale"
    return None


HELP_LOCK = """
策略 8 卖点（--strategy version8）stop10-max101-80-gap15-reserve-stale8 包：
  止损 10 个点（T+1 起）。T+1 起峰值≥买入价×1.01 后，
        离场线 = max(买入价×1.01, 买入价+涨幅×80%)，现价≤该线 → trail:max101_80。
  峰值判定延时 15 分钟（同会话创新高后 15 分钟内不评止盈；隔夜/午休 gap<0 视为满足）。
  遇涨停保留至开板（与策略 3 同一分钟窗 09:30–09:40；开板按该分钟收盘卖）。
  满 8 日仍持有 → force_sell:stale（止盈先于僵持）。
  无六档回撤、无 giveback、无未武装快切。
  per_name（默认）：每股票预算 100 万；同码可加仓（独立 lot，单码单日上限 2 笔），
        名单再现输家也加。相对第一笔成本每满 +20% 再加一个独立台阶（名单外也评）。
        现金不足记 skip_cash。
  上证十日线两日下方停开新仓、已持可加。
  跌停：任何卖因成交前跌停则 defer，次日再评（不只 stop_loss）。
  落盘：backtest_output/csv_{daily|minute}_v8_{start}_{end}/
"""


def record_strategy8_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_target"] = 0.0
    st.stats["max101_80"] = True
    st.stats["floor_mult"] = float(FLOOR_MULT)
    st.stats["keep_frac"] = float(KEEP_FRAC)
    st.stats["keep50_floor110"] = False
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["stale_days"] = int(STALE_DAYS)
    st.stats["stale_unarmed_only"] = bool(STALE_UNARMED_ONLY)
    st.stats["unarmed_stop_pct"] = float(UNARMED_STOP_PCT)
    st.stats["bands6"] = False
    st.stats["band_split"] = False
    st.stats["blend_keep20"] = False
    st.stats["giveback_mult"] = float(GIVEBACK_MULT)
    st.stats["probe_frac"] = float(PROBE_FRAC)
    st.stats["add_peak_mult"] = float(ADD_PEAK_MULT)
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["add_cap"] = 0.0
    st.stats["step_ride"] = False
    st.stats["step_ind"] = False
    st.stats["t1_trail"] = True
    st.stats["reserve_limit_up"] = bool(RESERVE_LIMIT_UP)
    st.stats["defer_limit_up"] = bool(DEFER_LIMIT_UP)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["index_ma"] = int(INDEX_MA)
    st.stats["index_below_sessions"] = int(INDEX_BELOW_SESSIONS)
    st.stats["index_symbol"] = INDEX_SYMBOL
    st.stats["index_blocks_add"] = bool(INDEX_BLOCKS_ADD)
    st.stats["index_gate_on"] = bool(INDEX_GATE_ON)
    st.stats["allow_add"] = bool(ALLOW_ADD)
