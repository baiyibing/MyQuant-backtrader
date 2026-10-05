# -*- coding: utf-8 -*-
"""策略 6.1 卖点纯函数 — 无上限步进回撤梯子（人裁 2026-10-02）。

止损 5 个点（T+1 起）。止盈梯子：峰值涨幅 A 每 5% 一档（无上限档），离场回撤
B = 5% + 2%×档号，离场价 = 峰值 − 成本×B（Q1=G），允许在成本下方触发（Q2）。
峰值从 T+1 起算。买侧（14:55 名单、涨停 T+1 09:45 追买 / 涨停弃买）、+20% step
加仓、名单再现独立组共用 csv 引擎；单股预算 100 万；全局现金 40 亿由 CLI 给定。

组语义：step 加仓并入首次仓同进同出，但**不进成本基数**——止损线与梯子
（A、B、离场线）一律锚首仓买入价（首 lot 成本），峰值锚组首；名单再现 =
新独立组，输赢都加、各自止损止盈。（人裁 2026-10-02 纠偏：step 不进成本基数，止损/梯子锚首仓买入价）
"""

from __future__ import annotations

from backtest.research import strategy_book_helpers as _book_helpers

from typing import Optional

BOOK_TAG = "v6_15"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.05
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05  # 峰值涨幅 A 每档 5%
GIVE_BASE = 0.05  # 首档 B = 5%
GIVE_STEP = 0.03  # 每加一档 B + 3%，无上限（6.13 修改③）
NAME_BUDGET = 1_000_000.0
ADD_STEP = 0.20
STEP_FRAC = 1.0  # step 每笔整基
STEP_CAP_PER_CODE = None  # 无票级上限（6.1 语义）
STEP_STOP_PCT = 0.10  # step lot 独立止损（引擎侧执行，修改①）
SCALE_OUT_STEP = 0.05  # 每涨 5% 一档（回退 6.14 拉宽实验）
SCALE_OUT_FRAC = 0.05  # 卖出当时剩余持仓的 5%
PEAK_DD_EXIT = 0.15  # 峰值回撤阈值（6.14 修改②）
PEAK_DD_SESSIONS = 15  # 收复窗口（交易日）


def give_band(peak: float, cost: float) -> int:
    """峰值涨幅落入的第几档（[0,5%)=0、[5,10%)=1、…），无上限。"""
    return _book_helpers.give_band(peak, cost, BAND_WIDTH=BAND_WIDTH)


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
    return _book_helpers.lot_budget(name_budget, _lots)


def record_strategy6_15_params(st, *, stop_pct: float) -> None:
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
    st.stats["step_stop_pct"] = float(STEP_STOP_PCT)
    st.stats["scale_out_step"] = float(SCALE_OUT_STEP)
    st.stats["scale_out_frac"] = float(SCALE_OUT_FRAC)
    st.stats["peak_dd_exit"] = float(PEAK_DD_EXIT)
    st.stats["peak_dd_sessions"] = int(PEAK_DD_SESSIONS)
    st.stats["cost_anchor"] = "first_lot"


HELP_LOCK = """
策略 6.15 卖点（--strategy version6_15，人裁 2026-10-06；6.13 + 峰值兜底）：
  止损 5 个点（T+1 起）。T+1 日起评止盈；峰值 = 组内 bar high（T+0 固定买入价）。
  峰值涨幅 A 每 5% 一档：[0,5%) 档 0 → B=5%，[5,10%) → 8%，[10,15%) → 11%，
  以此类推 B = 5% + 3%×档号，无上限档。离场价 = 峰值 − 首仓成本×B，
  允许在成本下方触发（小赚也护）。分批减仓：相对首仓买入价每满 +5%（1.05/1.10/…
  无上限）卖出当时剩余持仓的 10%（整百向下、FIFO 切 lot、每档一次、逐分钟
  close 触发按该 close 成交；lot 级 T+1；跌停顺延；不重算锚与峰值）。
  峰值回撤兜底：从峰值回撤 >15% 且 15 个交易日内未收复峰值 → 全组清仓
  （reason peak_dd_clear；与梯子/减仓并行，先到先出）。
  step lot 独立止损 −10%（相对自身买价、只卖该 lot、T+1、跌停顺延）。
  触价 bar 与创新高 bar 间隔 ≥ 15 分钟
  （=15 允许；隔夜/午休 gap<0 视为满足）。
  同进同出：+20% step 加仓（相对首仓成本，每满一档加一笔）并入首次仓，
  止损/梯子锚首仓买入价（step 不进成本基数）、峰值锚组首；名单再现 = 新独立组，输赢都加、
  各自止损止盈，同日可与 step 并存（两笔各 100 万）。
  单股预算 100 万 / 每笔整基；全局现金 --cash-total（人裁 40 亿）。无指数闸。
  T+1 09:45 追买：市价 > 开盘 买入；市价 < 开盘 或涨停 弃买（引擎既有合同）。
  落盘：backtest_output/csv_minute_v6_15_{start}_{end}/
"""
