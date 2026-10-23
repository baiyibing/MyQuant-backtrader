# -*- coding: utf-8 -*-
"""策略 6.64 — 6.55 栈 + 两档止损 ATR 反向自适应。

6.55 全部（give 5%+4%×档、均价减仓、停泊、抽离、上证闸门减半、收复买回、
现金分红买 600036、40/60 档程）不变。底仓 −5% 硬止损与档位 −10% 止损按
入场日 ATR14% 相对池中位 3.8% 反向缩放（人裁 2026-10-23，移植策略13 机制）：
高波动快砍、低波动容忍、中位票等同固定值；无 ATR 回退固定值。
梯子 give、峰值 15%/15 日、闸门均不缩放。分钟引擎生效；日线引擎不缩放。
"""

from __future__ import annotations

from backtest.research.strategy6_55_rules import (  # noqa: F401
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
    GIVE_STEP,
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
    exit_line,
    give_band,
    index_cut_shares,
    is_continuation_rise,
    load_sse_ma10_block_new,
    lot_budget,
    record_strategy6_55_params,
    take_profit_reason,
)

BOOK_TAG = "v6_64"
ATR_STOP_WINDOW = 14
ATR_STOP_ANCHOR = 0.038
# 与策略13 hard 档同比例（base×2/3, base×5/3）：底仓 5% → 3.33%–8.33%
ATR_CLAMP_HARD = (0.0333, 0.0833)
# 与策略13 add 档一致：档位 10% → 7%–16%
ATR_CLAMP_STEP = (0.07, 0.16)


def atr_inverse_threshold(base: float, atr_pct: float, *, anchor: float = ATR_STOP_ANCHOR,
                          clamp: tuple = ATR_CLAMP_STEP) -> float:
    """ATR 反向缩放：threshold = base × anchor/atr，夹到 clamp。"""
    if not atr_pct or atr_pct <= 0:
        return float(base)
    return min(clamp[1], max(clamp[0], float(base) * (anchor / float(atr_pct))))


def record_strategy6_64_params(st, *, stop_pct: float) -> None:
    record_strategy6_55_params(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["atr_stop_window"] = int(ATR_STOP_WINDOW)
    st.stats["atr_stop_anchor"] = float(ATR_STOP_ANCHOR)
    st.stats["atr_clamp_hard"] = list(ATR_CLAMP_HARD)
    st.stats["atr_clamp_step"] = list(ATR_CLAMP_STEP)


HELP_LOCK = """
策略 6.64 卖点（--strategy version6_64，人裁 2026-10-23；6.55 + 两档止损 ATR 反向自适应）：
  6.55 全部（give 5%+4%×档、均价减仓每 +5% 减 5%、40/60 档程、停泊 80%/100 万、
  开盘补缺口、延续档止损买回、补一手默认开、总收益抽离锁进 600036、
  上证连续两日 MA10 下方减半、收复买回、现金分红入账后买 600036）不变。
  不改 6.55 书。
  ATR 反向自适应（移植策略13 机制）：底仓 −5% 硬止损与档位 −10% 止损按入场日
  ATR14% 相对池中位 3.8% 反向缩放并锁定——底仓 3.33%–8.33%、档位 7%–16%；
  高波动快砍、低波动容忍、中位票等同固定值；ATR 不足 15 日回退固定值
  （记 atr_stop_fixed_fallback）。梯子 give、峰值 15%/15 日、上证闸门不缩放。
  仅分钟引擎生效；日线引擎不缩放（官方章为分钟口径）。
  官方章：backtest_output/csv_minute_v6_64_20251023_20260909_industry
  落盘：backtest_output/csv_minute_v6_64_{start}_{end}/
  已归档（2026-10-23）。不锁 golden。
"""
