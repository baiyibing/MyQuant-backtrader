# -*- coding: utf-8 -*-
"""策略 6.55 — 6.54 栈 + 梯子 give 改为 5%+4%×档。

6.54 全部（均价减仓、停泊、抽离、上证闸门、现金分红买 600036）不变。
exit_line / 分钟扫描用本模块 GIVE_STEP，不沿用 6.53 的 3%。
"""

from __future__ import annotations

from typing import Optional

from backtest.research.strategy6_54_rules import (  # noqa: F401
    ADD_SCHEDULE,
    ADD_STEP,
    ALLOW_ADD,
    BAND_WIDTH,
    CONT_FROM_RISE,
    CONT_STOP_REBUY,
    CONT_STOP_REBUY_FRAC,
    CONT_STOP_REBUY_LIFT,
    CONT_STOP_REBUY_OPEN_FRAC,
    CONT_STOP_REBUY_WITH_SCHEDULE,
    DIV_TO_PARKING,
    GIVE_BASE,
    INDEX_BLOCKS_ADD,
    INDEX_BLOCKS_S8_ADD,
    INDEX_BELOW_SESSIONS,
    INDEX_CUT,
    INDEX_CUT_FRAC,
    INDEX_CUT_MIN_KEEP,
    INDEX_GATE_ON,
    INDEX_MA,
    INDEX_SYMBOL,
    MIN_LOT_TOP_UP,
    NAME_BUDGET,
    OPEN_FRAC,
    PARKING_BUFFER,
    PARKING_EXECUTE,
    PARKING_FRAC,
    PARKING_OPEN_COVER,
    PARKING_SYMBOL,
    PEAK_DD_EXIT,
    PEAK_DD_SESSIONS,
    PEAK_GAP_MIN,
    PROFIT_SKIM,
    PROFIT_SKIM_FRAC,
    PROFIT_SKIM_KEEP_IDLE,
    PROFIT_SKIM_PRO_RATA,
    PROFIT_SKIM_STEP,
    PROFIT_SKIM_TO_PARKING,
    SCALE_OUT_ANCHOR,
    SCALE_OUT_FRAC,
    SCALE_OUT_STEP,
    STEP_CAP_PER_CODE,
    STEP_FRAC,
    STEP_STOP_PCT,
    STOP_PCT,
    TP_MIN_DAYS,
    due_cont_rebuy_rise,
    give_band,
    index_cut_shares,
    is_continuation_rise,
    load_sse_ma10_block_new,
    lot_budget,
    record_strategy6_54_params,
)

BOOK_TAG = "v6_55"
GIVE_STEP = 0.04


def exit_line(cost: float, peak: float) -> float:
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
    if int(n_days) < TP_MIN_DAYS:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(peak) <= float(cost):
        return None
    if float(px) <= exit_line(cost, peak):
        return f"trail:ladder:{give_band(peak, cost) * 5}"
    return None


def record_strategy6_55_params(st, *, stop_pct: float) -> None:
    record_strategy6_54_params(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["div_to_parking"] = bool(DIV_TO_PARKING)


HELP_LOCK = """
策略 6.55 卖点（--strategy version6_55，人裁 2026-10-10；6.54 + give 5%+4%×档）：
  6.54 全部（均价减仓、停泊 80%/100 万、开盘补缺口、延续档止损买回、补一手默认开、
  总收益抽离锁进 600036、加仓先闲置后锁仓、上证连续两日 MA10 下方减半、收复买回、
  现金分红入账后买 600036）不变。
  梯子回撤 give 从 5%+3%×档 改为 5%+4%×档。
  落盘：backtest_output/csv_minute_v6_55_{start}_{end}/
  已归档（2026-10-10）。当前书。不锁 golden。
"""
