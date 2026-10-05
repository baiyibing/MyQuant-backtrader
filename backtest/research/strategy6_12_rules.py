# -*- coding: utf-8 -*-
"""策略 6.12 卖点纯函数 — 6.11 之上加仓档细化 1.25/1.30/1.35/1.40（人裁 2026-10-02）。

买侧：T0 名单日记 A0 = 当日 14:55 收盘（只记锚不买入）；自 T+1 起每日 14:55
检查，价格 ≥ A0×1.2 即以该 14:55 成交价买入 1 个基数（100 万），信号无限期
有效、突破日涨停则继续等；开组后 A0×1.25/1.30/1.35/1.40 各加 1 个基数（封顶 4 个）。
卖侧 = 6.9 原样（6.7 三段梯子 + 止损 −10%），锚 A0（= T0 收盘，非成交价）。

买侧（锚 A0 = T0 14:55 首笔成交价 = 首仓成本）：T0 买 20% 仓位（20 万）；
相对 A0 每涨 5% 分批加 20% 至满仓（+5/10/15/20% 共 4 笔 → 一个基数 100 万）；
相对 A0 每涨 20% 加一个整基数 100 万（基数腿），基数上限：涨幅 <100% 时 2 个、
[100%,200%) 再 +2 个（共 4 个）；每日每档一笔（分批腿优先）。
卖侧 = 6.7 三段梯子不变（<15% 保底带 / [15%,100%] max(梯子线, 峰值×0.85) /
>100% 峰值×0.80），锚 A0；止损 10%（T+1 起）。

优化 6.6 的中段失血（峰值涨幅 [15%,100%) 无保底、无峰值线，step 重仓驻留）：
该区间离场线 = max(梯子计算线, 峰值×0.85)——保护线只在高于梯子线时生效
（约 A>23% 起绑定）。峰值 > 100% 维持 6.6 的峰值×0.80。其余（止损 5%、
B = 5%+3%×档号、[0,3%) 保本 / [3,5%) +1% / [5,10%) +1% / [10,15%) +3% 保底、
首仓成本锚、step +10%×单票 8 笔、追买合同、再现独立组）与 6.6 一致。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v6_12"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.10
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05  # 峰值涨幅 A 每档 5%
GIVE_BASE = 0.05  # 首档 B = 5%
GIVE_STEP = 0.03  # 每加一档 B + 3%，无上限
# 峰值涨幅上界 → 保底涨幅（离场线下限 = 首仓成本×(1+floor)）；超过 15% 无保底。
FLOOR_STEPS = ((0.03, 0.00), (0.05, 0.01), (0.10, 0.01), (0.15, 0.03))
MID_PEAK_DD_RISE = 0.15  # 峰值涨幅 ≥15% 起，中段峰值保护线参与
MID_PEAK_DD_PCT = 0.15  # 中段保护线 = 峰值×0.85
PEAK_DD_RISE = 1.0  # 峰值涨幅 > 100% 启用峰值回撤线
PEAK_DD_PCT = 0.20  # 峰值回撤 20% 离场（>100% 区间，替代梯子与中段线）
NAME_BUDGET = 1_000_000.0
BREAKOUT_MULT = 1.2  # 突破触发价 = A0×1.2
ADD_STEP = 0.05  # 加仓档距：相对 A0 每涨 5%（1.25/1.30/1.35/1.40）
ADD_OFFSET = 4  # 跳过 1.05~1.20 四档（1.2 为首买触发价）
STEP_FRAC = 1.0  # 每笔加仓 = 整基 100 万
TRANCHE_MAX = 4  # 最高加 4 个基数
STEP_CAP_PER_CODE = None


def give_band(peak: float, cost: float) -> int:
    """峰值涨幅落入的第几档（[0,5%)=0、[5,10%)=1、…），无上限。"""
    if float(cost) <= 0 or float(peak) <= float(cost):
        raise ValueError("peak must be above positive cost")
    rise = float(peak) / float(cost) - 1.0
    return int((rise + 1e-12) / BAND_WIDTH)


def peak_dd_active(peak: float, cost: float) -> bool:
    """峰值涨幅 > 100% 时启用峰值回撤线（替代梯子与中段线）。"""
    return float(peak) / float(cost) - 1.0 + 1e-12 > PEAK_DD_RISE


def mid_peak_dd_active(peak: float, cost: float) -> bool:
    """峰值涨幅 ∈ [15%, 100%] 时中段保护线（峰值×0.85）参与取 max。"""
    rise = float(peak) / float(cost) - 1.0
    return rise + 1e-12 >= MID_PEAK_DD_RISE and not peak_dd_active(peak, cost)


def floor_gain(peak: float, cost: float) -> Optional[float]:
    """峰值涨幅对应的保底涨幅；> 15% 无保底（None）。"""
    rise = float(peak) / float(cost) - 1.0
    for upper, gain in FLOOR_STEPS:
        if rise + 1e-12 < upper:
            return gain
    return None


def exit_line(cost: float, peak: float) -> float:
    """离场线：>100% → 峰值×0.80；[15%,100%] → max(梯子线, 峰值×0.85)；<15% → 梯子保底线。"""
    if peak_dd_active(peak, cost):
        return float(peak) * (1.0 - PEAK_DD_PCT)
    band = give_band(peak, cost)
    give = GIVE_BASE + GIVE_STEP * band
    line = float(peak) - float(cost) * give
    gain = floor_gain(peak, cost)
    if gain is not None:
        line = max(line, float(cost) * (1.0 + gain))
    if mid_peak_dd_active(peak, cost):
        line = max(line, float(peak) * (1.0 - MID_PEAK_DD_PCT))
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
    """突破首买 = 整基（引擎 breakout_day 执行）。"""
    return float(name_budget)


def record_strategy6_12_params(st, *, stop_pct: float) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["ladder_band_width"] = float(BAND_WIDTH)
    st.stats["ladder_give_base"] = float(GIVE_BASE)
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["ladder_unbounded"] = True
    st.stats["floor_steps"] = [list(x) for x in FLOOR_STEPS]
    st.stats["mid_peak_dd_rise"] = float(MID_PEAK_DD_RISE)
    st.stats["mid_peak_dd_pct"] = float(MID_PEAK_DD_PCT)
    st.stats["peak_dd_rise"] = float(PEAK_DD_RISE)
    st.stats["peak_dd_pct"] = float(PEAK_DD_PCT)
    st.stats["allow_add"] = bool(ALLOW_ADD)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["step_frac"] = float(STEP_FRAC)
    st.stats["add_offset"] = int(ADD_OFFSET)
    st.stats["tranche_max"] = int(TRANCHE_MAX)
    st.stats["breakout_mult"] = float(BREAKOUT_MULT)
    st.stats["cost_anchor"] = "first_lot"


HELP_LOCK = """
策略 6.11（--strategy version6_11，人裁 2026-10-02；突破买侧）：
  买侧：T0 名单日只记 A0 = 当日 14:55 收盘（不买入）；自 T+1 起每日 14:55 检查，
  价格 ≥ A0×1.2 → 以该 14:55 成交价买入 1 个基数（100 万，reason breakout）；
  信号无限期有效（突破窗口不加）；突破日 14:55 涨停则不买、继续等；
  开组后 A0×1.25/1.30/1.35/1.40 各加 1 个基数（每日 14:55 评、每档一笔，封顶 4 个）；
  名单再现 = 新信号新 A0。
  止损 10 个点（T+1 起，锚 A0）。T+1 日起评止盈；峰值 = 组内 bar high。
  离场线分三段：峰值涨幅 > 100% → 峰值×0.80（回撤 20% 落袋）；[15%,100%] →
  max(梯子线, 峰值×0.85)（中段保护线，约 A>23% 起绑定）；<15% → 梯子
  max(峰值 − 首仓成本×B, 保底)，B = 5% + 3%×档号（档 0/1/2/3… = 5%/8%/11%/14%…
  无上限），保底按峰值涨幅 [0,3%) 成本价、[3,5%) +1%、[5,10%) +1%、[10,15%) +3%。
  触价 bar 与创新高 bar 间隔 ≥ 15 分钟（=15 允许；隔夜/午休 gap<0 视为满足）。
  同进同出：+10% step 加仓（相对首仓成本每满一档加一笔整基 100 万）并入首次仓，
  但止损/梯子锚首仓买入价（step 不进成本基数）、峰值锚组首；单票（同一代码、
  所有组共享）step 总额 400 万 = 最多 8 笔，触顶跳过；名单再现 = 新独立组，
  输赢都加、各自止损止盈。
  单股预算 100 万 / 每笔整基；全局现金 --cash-total。无指数闸。
  T+1 09:45 追买：市价 > 开盘 买入；市价 < 开盘 或涨停 弃买（引擎既有合同）。
  落盘：backtest_output/csv_minute_v6_12_{start}_{end}/
"""
