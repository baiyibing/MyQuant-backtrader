# -*- coding: utf-8 -*-
"""策略 6.1 卖点纯函数 — 无上限步进回撤梯子（人裁 2026-10-02）。

止损 5 个点（T+1 起）。止盈梯子：峰值涨幅 A 每 5% 一档（无上限档），离场回撤
B = 5% + 2%×档号，离场价 = 峰值 − 成本×B（Q1=G），允许在成本下方触发（Q2）。
峰值从 T+1 起算。买侧（14:55 名单、涨停 T+1 09:45 追买 / 涨停弃买）、+20% step
加仓、名单再现独立组共用 csv 引擎；单股预算 100 万；全局现金 40 亿由 CLI 给定。

组语义（同策略 8 独立组）：step 加仓并入首次仓同进同出，组成本 = 加权均价、
峰值锚在组首 lot；名单再现 = 新独立组，输赢都加、各自止损止盈。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v6_1"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.05
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05  # 峰值涨幅 A 每档 5%
GIVE_BASE = 0.05  # 首档 B = 5%
GIVE_STEP = 0.02  # 每加一档 B + 2%，无上限（Q3）
NAME_BUDGET = 1_000_000.0
ADD_STEP = 0.20


def give_band(peak: float, cost: float) -> int:
    """峰值涨幅落入的第几档（[0,5%)=0、[5,10%)=1、…），无上限。"""
    if float(cost) <= 0 or float(peak) <= float(cost):
        raise ValueError("peak must be above positive cost")
    rise = float(peak) / float(cost) - 1.0
    return int((rise + 1e-12) / BAND_WIDTH)


def exit_line(cost: float, peak: float) -> float:
    """离场价 = 峰值 − 成本×B；可在成本下方（Q2）。"""
    band = give_band(peak, cost)
    give = GIVE_BASE + GIVE_STEP * band
    return float(peak) - float(cost) * give


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
    **_ignored,
) -> Optional[str]:
    """T+0（n_days<1）不评。T+1 起按无上限梯子回撤；峰值 ≤ 成本不评。"""
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
    """每笔都是整笔 name_budget（新组 / step / 再现组同口径）。"""
    return float(name_budget)


def record_strategy6_1_params(st, *, stop_pct: float) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["ladder_band_width"] = float(BAND_WIDTH)
    st.stats["ladder_give_base"] = float(GIVE_BASE)
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["ladder_unbounded"] = True
    st.stats["tp_below_cost"] = True
    st.stats["allow_add"] = bool(ALLOW_ADD)
    st.stats["peak_gap_min"] = int(PEAK_GAP_MIN)
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["add_cap"] = 0.0


HELP_LOCK = """
策略 6.1 卖点（--strategy version6_1，人裁 2026-10-02；Q1=G / Q2 允许成本下方
止盈 / Q3、Q4 无上限）：
  止损 5 个点（T+1 起）。T+1 日起评止盈；峰值 = 组内 bar high（T+0 固定买入价）。
  峰值涨幅 A 每 5% 一档：[0,5%) 档 0 → B=5%，[5,10%) → 7%，[10,15%) → 9%，
  以此类推 B = 5% + 2%×档号，无上限档。离场价 = 峰值 − 组内加权成本×B，
  允许在成本下方触发（小赚也护）。触价 bar 与创新高 bar 间隔 ≥ 15 分钟
  （=15 允许；隔夜/午休 gap<0 视为满足）。
  同进同出：+20% step 加仓（相对组首成本，每满一档加一笔）并入首次仓，
  组成本 = 加权均价、峰值锚组首；名单再现 = 新独立组，输赢都加、
  各自止损止盈，同日可与 step 并存（两笔各 100 万）。
  单股预算 100 万 / 每笔整基；全局现金 --cash-total（人裁 40 亿）。无指数闸。
  T+1 09:45 追买：市价 > 开盘 买入；市价 < 开盘 或涨停 弃买（引擎既有合同）。
  落盘：backtest_output/csv_minute_v6_1_{start}_{end}/
"""
