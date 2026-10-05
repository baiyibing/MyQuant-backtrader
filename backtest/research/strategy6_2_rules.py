# -*- coding: utf-8 -*-
"""策略 6.2 卖点纯函数 — band0 保本锚 + 止损 10% + 半基 step（人裁 2026-10-02）。

相对 6.1 的三处修改：止损 5%→10%；band0 离场线 = max(峰值−成本×B, 成本)
（未到 +5% 前跌回成本价就走，D 方案）；step 加仓每满 +10% 加一个 50 万
（基数一半），仍同进同出、无上限；止损/梯子一律锚首仓买入价，step 不进
成本基数（人裁 2026-10-02 纠偏）。band≥1 梯子、Q1=G、峰值 T+1 起算、
15 分钟峰差、追买合同、再现独立组、单笔 100 万、现金 40 亿全部沿用 6.1。
"""

from __future__ import annotations

from backtest.research import strategy_book_helpers as _book_helpers

from typing import Optional

BOOK_TAG = "v6_2"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.10
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05  # 峰值涨幅 A 每档 5%
GIVE_BASE = 0.05  # 首档 B = 5%
GIVE_STEP = 0.02  # 每加一档 B + 2%，无上限
BAND0_FLOOR_COST = True  # D 方案：band0 离场线取 max(计算线, 成本)
NAME_BUDGET = 1_000_000.0
ADD_STEP = 0.10  # 每满 +10% 一档（6.1 为 0.20）
STEP_FRAC = 0.5  # 每笔 step = name_budget×0.5（6.1 为整基）


def give_band(peak: float, cost: float) -> int:
    """峰值涨幅落入的第几档（[0,5%)=0、[5,10%)=1、…），无上限。"""
    return _book_helpers.give_band(peak, cost, BAND_WIDTH=BAND_WIDTH)


def exit_line(cost: float, peak: float) -> float:
    """离场价：band≥1 = 峰值 − 成本×B；band0 = max(计算线, 成本)（保本锚）。"""
    band = give_band(peak, cost)
    give = GIVE_BASE + GIVE_STEP * band
    line = float(peak) - float(cost) * give
    if band == 0 and BAND0_FLOOR_COST:
        return max(line, float(cost))
    return line


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
    **_ignored,
) -> Optional[str]:
    """T+0（n_days<1）不评。T+1 起按梯子回撤；峰值 ≤ 成本不评。"""
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
    """开仓每笔仍是整笔 name_budget；step 半基由引擎 step_frac 控制。"""
    return _book_helpers.lot_budget(name_budget, _lots)


def record_strategy6_2_params(st, *, stop_pct: float) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["ladder_band_width"] = float(BAND_WIDTH)
    st.stats["ladder_give_base"] = float(GIVE_BASE)
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["ladder_unbounded"] = True
    st.stats["band0_floor_cost"] = bool(BAND0_FLOOR_COST)
    st.stats["allow_add"] = bool(ALLOW_ADD)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["step_frac"] = float(STEP_FRAC)
    st.stats["add_cap"] = 0.0
    st.stats["cost_anchor"] = "first_lot"


HELP_LOCK = """
策略 6.2 卖点（--strategy version6_2，人裁 2026-10-02；6.1 之上改三处）：
  止损 10 个点（T+1 起）。T+1 日起评止盈；峰值 = 组内 bar high（T+0 固定买入价）。
  梯子：峰值涨幅 A 每 5% 一档，B = 5% + 2%×档号（无上限）；band≥1 离场价 =
  峰值 − 首仓成本×B；band0 离场价 = max(峰值−首仓成本×5%, 首仓成本) —— 未到 +5%
  前跌回成本价即走（保本锚，D 方案），不再在成本下方触发。
  触价 bar 与创新高 bar 间隔 ≥ 15 分钟（=15 允许；隔夜/午休 gap<0 视为满足）。
  step 加仓：相对首仓成本每满 +10% 加一笔 50 万（基数一半，无上限），并入
  首次仓同进同出，但止损/梯子锚首仓买入价（step 不进成本基数）、峰值锚
  组首；名单再现 = 新独立组，
  输赢都加、各自止损止盈（开仓仍整笔 100 万）。
  全局现金 --cash-total（人裁 40 亿）。无指数闸。
  T+1 09:45 追买：市价 > 开盘 买入；市价 < 开盘 或涨停 弃买（引擎既有合同）。
  落盘：backtest_output/csv_minute_v6_2_{start}_{end}/
"""
