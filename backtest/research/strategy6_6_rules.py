# -*- coding: utf-8 -*-
"""策略 6.6 卖点纯函数 — 6.5 之上：峰值×0.80 / step +10%×8 笔 / 低档保底细化（人裁 2026-10-02）。

相对 6.5 的三处修改：(1) 峰值涨幅 > 100% 时离场线 = 峰值×0.80（回撤 20% 落袋，
6.5 为 0.85）；(2) step 加仓每满 +10% 一档（每档一笔、每组每日一次），单票同码
所有组共享最多 8 笔 = 400 万（6.5 为 +20%×4 笔，总量不变）；(3) 低档保底按峰值
涨幅细化：[0,3%) 保底成本价、[3,5%) 保底 +1%（band1 +1%、band2 +3%、档 ≥3
无保底维持 6.5）。其余与 6.5 一致：B = 5%+3%×档号、首仓成本锚、−5% 止损、
T+1 09:45 追买合同、再现独立组、15 分钟峰差。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v6_6"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.05
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05  # 峰值涨幅 A 每档 5%
GIVE_BASE = 0.05  # 首档 B = 5%
GIVE_STEP = 0.03  # 每加一档 B + 3%，无上限
# 峰值涨幅上界 → 保底涨幅（离场线下限 = 首仓成本×(1+floor)）；超过 15% 无保底。
FLOOR_STEPS = ((0.03, 0.00), (0.05, 0.01), (0.10, 0.01), (0.15, 0.03))
PEAK_DD_RISE = 1.0  # 峰值涨幅超过 100% 启用峰值回撤线
PEAK_DD_PCT = 0.20  # 峰值回撤 20% 离场
NAME_BUDGET = 1_000_000.0
ADD_STEP = 0.10  # 每满 +10% 一档（6.5 为 0.20）
STEP_FRAC = 1.0
STEP_CAP_PER_CODE = 8  # 单票 step 总额 400 万 = 8 笔 × 整基 100 万


def give_band(peak: float, cost: float) -> int:
    """峰值涨幅落入的第几档（[0,5%)=0、[5,10%)=1、…），无上限。"""
    if float(cost) <= 0 or float(peak) <= float(cost):
        raise ValueError("peak must be above positive cost")
    rise = float(peak) / float(cost) - 1.0
    return int((rise + 1e-12) / BAND_WIDTH)


def peak_dd_active(peak: float, cost: float) -> bool:
    """峰值涨幅 > 100% 时启用峰值回撤线。"""
    return float(peak) / float(cost) - 1.0 + 1e-12 > PEAK_DD_RISE


def floor_gain(peak: float, cost: float) -> Optional[float]:
    """峰值涨幅对应的保底涨幅；> 15% 无保底（None）。"""
    rise = float(peak) / float(cost) - 1.0
    for upper, gain in FLOOR_STEPS:
        if rise + 1e-12 < upper:
            return gain
    return None


def exit_line(cost: float, peak: float) -> float:
    """离场线：峰值>100% → 峰值×0.80；否则 max(峰值−首仓成本×B, 档内保底)。"""
    if peak_dd_active(peak, cost):
        return float(peak) * (1.0 - PEAK_DD_PCT)
    band = give_band(peak, cost)
    give = GIVE_BASE + GIVE_STEP * band
    line = float(peak) - float(cost) * give
    gain = floor_gain(peak, cost)
    if gain is not None:
        line = max(line, float(cost) * (1.0 + gain))
    return line


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
    **_ignored,
) -> Optional[str]:
    """T+0（n_days<1）不评。T+1 起评；峰值 ≤ 成本不评。"""
    if int(n_days) < TP_MIN_DAYS:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(peak) <= float(cost):
        return None
    if float(px) <= exit_line(cost, peak):
        if peak_dd_active(peak, cost):
            return "trail:peakdd20"
        return f"trail:ladder:{give_band(peak, cost) * 5}"
    return None


def lot_budget(name_budget: float, _lots) -> float:
    """开仓每笔仍是整笔 name_budget；step 档距/上限由引擎参数控制。"""
    return float(name_budget)


def record_strategy6_6_params(st, *, stop_pct: float) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["ladder_band_width"] = float(BAND_WIDTH)
    st.stats["ladder_give_base"] = float(GIVE_BASE)
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["ladder_unbounded"] = True
    st.stats["floor_steps"] = [list(x) for x in FLOOR_STEPS]
    st.stats["peak_dd_rise"] = float(PEAK_DD_RISE)
    st.stats["peak_dd_pct"] = float(PEAK_DD_PCT)
    st.stats["allow_add"] = bool(ALLOW_ADD)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["step_frac"] = float(STEP_FRAC)
    st.stats["step_cap_per_code"] = int(STEP_CAP_PER_CODE)
    st.stats["cost_anchor"] = "first_lot"


HELP_LOCK = """
策略 6.6 卖点（--strategy version6_6，人裁 2026-10-02；6.5 之上改三处）：
  止损 5 个点（T+1 起）。T+1 日起评止盈；峰值 = 组内 bar high（T+0 固定买入价）。
  峰值涨幅 > 100%（peak > 2×首仓成本）时：离场线 = 峰值×0.80（回撤 20% 落袋，
  替代高档梯子）。否则梯子：峰值涨幅 A 每 5% 一档，B = 5% + 3%×档号
  （档 0/1/2/3/4… = 5%/8%/11%/14%/17%…，无上限档），离场价 =
  max(峰值 − 首仓成本×B, 保底)：保底按峰值涨幅 [0,3%) 成本价、[3,5%) +1%、
  [5,10%) +1%、[10,15%) +3%、≥15% 无保底（计算线仍可低于成本）。
  触价 bar 与创新高 bar 间隔 ≥ 15 分钟（=15 允许；隔夜/午休 gap<0 视为满足）。
  同进同出：+10% step 加仓（相对首仓成本每满一档加一笔整基 100 万）并入首次仓，
  但止损/梯子锚首仓买入价（step 不进成本基数）、峰值锚组首；单票（同一代码、
  所有组共享）step 总额 400 万 = 最多 8 笔，触顶跳过；名单再现 = 新独立组，
  输赢都加、各自止损止盈。
  单股预算 100 万 / 每笔整基；全局现金 --cash-total。无指数闸。
  T+1 09:45 追买：市价 > 开盘 买入；市价 < 开盘 或涨停 弃买（引擎既有合同）。
  落盘：backtest_output/csv_minute_v6_6_{start}_{end}/
"""
