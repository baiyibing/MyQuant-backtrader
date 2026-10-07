# -*- coding: utf-8 -*-
"""策略 6.49 卖点纯函数 — 6.47 + 高 band 梯子回吐上限（人裁 2026-10-06）。

6.47 全部（-5% 止损、上证闸门、多档建仓梯 42.0 平档、三腿卖出、涨停 Defer）基础上：
梯子离场线增加回吐兜底 —— 离场线 = max(峰值 − 首仓成本×B, 峰值×(1−GIVE_MAX))。
低 band（涨幅 <60%）原式不变；band ≥ 12 起（B×成本 > 25%×峰值）由 cap 收紧，
最多回吐峰值的 25%。动机：002491 lot3 在 band-80 回吐 29%（已落袋 +2.8w 回吐 75%），
全场净值峰值回吐 39%。档序盈亏扫描证明晚档本身是赚的（#11–#20 +10%~+28%），
问题在离场线太松，不在加仓表。
"""

from __future__ import annotations

from backtest.research import strategy_book_helpers as _book_helpers

from typing import Optional

BOOK_TAG = "v6_49"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.05
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05  # 峰值涨幅 A 每档 5%
GIVE_BASE = 0.05  # 首档 B = 5%
GIVE_STEP = 0.03  # 每加一档 B + 3%，无上限（6.13 修改③）
GIVE_MAX = 0.25  # 梯子回吐上限：离场线 ≥ 峰值×(1−25%)（6.49 新增）
NAME_BUDGET = 1_000_000.0
OPEN_FRAC = 0.20
ADD_STEP = 0.20
STEP_FRAC = 1.0
STEP_CAP_PER_CODE = None
STEP_STOP_PCT = 0.10
ADD_SCHEDULE = [(0.10, 0.30), (0.20, 0.50)] + [(0.20 * i, 42.0) for i in range(2, 52)]
INDEX_GATE_ON = True
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = False

PARKING_SYMBOL = "600036.SH"
PARKING_FRAC = 0.60
PARKING_BUFFER = 2_000_000
SCALE_OUT_STEP = 0.05
SCALE_OUT_FRAC = 0.05
PEAK_DD_EXIT = 0.15
PEAK_DD_SESSIONS = 15


def give_band(peak: float, cost: float) -> int:
    """峰值涨幅落入的第几档（[0,5%)=0、[5,10%)=1、…），无上限。"""
    return _book_helpers.give_band(peak, cost, BAND_WIDTH=BAND_WIDTH)


def exit_line(cost: float, peak: float) -> float:
    """离场线 = max(峰值 − 成本×B, 峰值×(1−GIVE_MAX))；低 band 与 6.47 完全一致。"""
    band = give_band(peak, cost)
    give = GIVE_BASE + GIVE_STEP * band
    classic = float(peak) - float(cost) * give
    return max(classic, float(peak) * (1.0 - GIVE_MAX))


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
    **_ignored,
) -> Optional[str]:
    """T+0（n_days<1）不评。T+1 起按无上限梯子回撤（含 25% 回吐上限）。"""
    if int(n_days) < TP_MIN_DAYS:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(peak) <= float(cost):
        return None
    if float(px) <= exit_line(cost, peak):
        return f"trail:ladder:{give_band(peak, cost) * 5}"
    return None


def lot_budget(name_budget: float, _lots) -> float:
    """引擎实际取 6.45 链的 lot_budget（此处镜像保持书内一致）。"""
    return float(name_budget)


def record_strategy6_49_params(st, *, stop_pct: float) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["ladder_band_width"] = float(BAND_WIDTH)
    st.stats["ladder_give_base"] = float(GIVE_BASE)
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["ladder_give_max"] = float(GIVE_MAX)
    st.stats["ladder_unbounded"] = True
    st.stats["tp_below_cost"] = True
    st.stats["allow_add"] = bool(ALLOW_ADD)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["add_cap"] = 0.0
    st.stats["step_stop_pct"] = float(STEP_STOP_PCT)
    st.stats["scale_out_step"] = float(SCALE_OUT_STEP)
    st.stats["scale_out_frac"] = float(SCALE_OUT_FRAC)
    st.stats["peak_dd_exit"] = float(PEAK_DD_EXIT)
    st.stats["peak_dd_sessions"] = int(PEAK_DD_SESSIONS)
    st.stats["cost_anchor"] = "first_lot"
    st.stats["open_frac"] = float(OPEN_FRAC)
    st.stats["add_schedule_head"] = [list(x) for x in ADD_SCHEDULE[:4]]


def load_sse_ma10_block_new(start, end, *, root=None):
    """From index daily lake, load SSE closes and build the block-new map (8.4 loader)."""
    from backtest.research.strategy8_4_rules import load_sse_ma10_block_new as _load
    return _load(start, end, root=root)


HELP_LOCK = """
策略 6.49 卖点（--strategy version6_49，人裁 2026-10-06；6.47 + 回吐上限 25%）：
  6.47 全部（-5% 止损、上证闸门、多档建仓梯、三腿卖出、涨停 Defer）不变，仅改梯子线：
  离场线 = max(峰值 − 首仓成本×B, 峰值×75%)。涨幅 <60% 行为与 6.47 完全一致；
  band ≥ 12（B×成本 > 25%×峰值）起最多回吐峰值 25%。
  动机：002491 band-80 回吐 29%、全场峰值回吐 39%；晚档本身是赚的（#11–#20 档
  收益率 +10%~+28%），问题在离场线太松。
  落盘：backtest_output/csv_minute_v6_49_{start}_{end}/
"""
