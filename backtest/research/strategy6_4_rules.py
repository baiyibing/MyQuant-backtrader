# -*- coding: utf-8 -*-
"""策略 6.4 卖点纯函数 — 6.3 之上：档1/2 保底 + 单票 step 总额 400 万（人裁 2026-10-02）。

相对 6.3 的两处修改（人裁修订版：保底 1%/3%）：(1) 离场线保底——档 1（峰值
涨幅 [5%,10%)）保底 +1%、档 2（[10%,15%)）保底 +3%，档 0 与档 ≥3 不加保底
（离场线 = 峰值 − 首仓成本×B 原样）；(2) step 加仓单票（同一代码、所有组
共享）总额 400 万 = 最多 4 笔整基。
其余与 6.3 完全一致：止损 5%（T+1 起）、B = 5%+3%×档号、首仓成本锚
（step 不进基数）、Q1=G、允许成本下方、+20% step、再现独立组、15 分钟峰差。
"""

from __future__ import annotations

from backtest.research import strategy_book_helpers as _book_helpers

from typing import Optional

BOOK_TAG = "v6_4"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.05
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05  # 峰值涨幅 A 每档 5%
GIVE_BASE = 0.05  # 首档 B = 5%
GIVE_STEP = 0.03  # 每加一档 B + 3%，无上限（6.3 同款）
# 档 → 保底涨幅（离场线下限 = 首仓成本×(1+floor)）；档 0 与 ≥3 无保底。
FLOOR_BANDS = {1: 0.01, 2: 0.03}
NAME_BUDGET = 1_000_000.0
ADD_STEP = 0.20
STEP_FRAC = 1.0
STEP_CAP_PER_CODE = 4  # 单票 step 总额 400 万 = 4 笔 × 整基 100 万


def give_band(peak: float, cost: float) -> int:
    """峰值涨幅落入的第几档（[0,5%)=0、[5,10%)=1、…），无上限。"""
    return _book_helpers.give_band(peak, cost, BAND_WIDTH=BAND_WIDTH)


def exit_line(cost: float, peak: float) -> float:
    """离场价 = max(峰值 − 首仓成本×B, 档内保底)；档 0 与 ≥3 无保底。"""
    band = give_band(peak, cost)
    give = GIVE_BASE + GIVE_STEP * band
    line = float(peak) - float(cost) * give
    floor_gain = FLOOR_BANDS.get(band)
    if floor_gain is not None:
        line = max(line, float(cost) * (1.0 + floor_gain))
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
    """开仓每笔仍是整笔 name_budget；step 半基/票上限由引擎参数控制。"""
    return _book_helpers.lot_budget(name_budget, _lots)


def record_strategy6_4_params(st, *, stop_pct: float) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["ladder_band_width"] = float(BAND_WIDTH)
    st.stats["ladder_give_base"] = float(GIVE_BASE)
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["ladder_unbounded"] = True
    st.stats["floor_bands"] = dict(FLOOR_BANDS)
    st.stats["tp_below_cost"] = True
    st.stats["allow_add"] = bool(ALLOW_ADD)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["step_frac"] = float(STEP_FRAC)
    st.stats["step_cap_per_code"] = int(STEP_CAP_PER_CODE)
    st.stats["cost_anchor"] = "first_lot"


HELP_LOCK = """
策略 6.4 卖点（--strategy version6_4，人裁 2026-10-02；6.3 之上改两处）：
  止损 5 个点（T+1 起）。T+1 日起评止盈；峰值 = 组内 bar high（T+0 固定买入价）。
  梯子：峰值涨幅 A 每 5% 一档，B = 5% + 3%×档号（档 0/1/2/3/4… = 5%/8%/11%/14%/17%…，
  无上限档）；离场价 = max(峰值 − 首仓成本×B, 保底)：
    档 0（A<5%）无保底（允许成本下方）；档 1 保底 +1%；档 2 保底 +3%；
    档 ≥3 无保底（离场线 = 峰值 − 首仓成本×B 原样）。
  触价 bar 与创新高 bar 间隔 ≥ 15 分钟（=15 允许；隔夜/午休 gap<0 视为满足）。
  同进同出：+20% step 加仓（相对首仓成本每满一档加一笔整基 100 万）并入首次仓，
  但止损/梯子锚首仓买入价（step 不进成本基数）、峰值锚组首；单票（同一代码、
  所有组共享）step 总额 400 万 = 最多 4 笔，触顶跳过；名单再现 = 新独立组，
  输赢都加、各自止损止盈。
  单股预算 100 万 / 每笔整基；全局现金 --cash-total。无指数闸。
  T+1 09:45 追买：市价 > 开盘 买入；市价 < 开盘 或涨停 弃买（引擎既有合同）。
  落盘：backtest_output/csv_minute_v6_4_{start}_{end}/
"""
