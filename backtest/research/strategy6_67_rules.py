# -*- coding: utf-8 -*-
"""策略 6.67 — 6.65 栈 + 深档三倍（涨幅 ≥115% 的延续档 42→126 万）。

6.65 全部（give 5%+4%×档、均价减仓、停泊、抽离、上证闸门减半、收复买回、
现金分红买 600036、+35%/+55%/… 档程）不变。延续档在 ≥+115% 起三倍
（人裁 2026-10-24，与 v14 终稿同构剂量 ×3）：浅档 42 万控长尾，
深档 126 万对已翻倍者加码。不改 6.65 书。
"""

from __future__ import annotations

from backtest.research.strategy6_65_rules import (  # noqa: F401
    ADD_STEP,
    ALLOW_ADD,
    BAND_WIDTH,
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
    record_strategy6_65_params,
    take_profit_reason,
)

BOOK_TAG = "v6_67"
# 深档三倍（人裁 2026-10-24）：阈值 ≥+100%（首个 1.15）的延续档 ×3。
ADD_SCHEDULE = [(0.10, 0.30), (0.20, 0.50)] + [
    (round(0.35 + 0.20 * i, 2), 126.0 if 0.35 + 0.20 * i >= 1.0 else 42.0)
    for i in range(50)
]
CONT_FROM_RISE = ADD_SCHEDULE[2][0]
DEEP_RUNG_MULT = 3.0
DEEP_RUNG_FROM_RISE = 1.0


def record_strategy6_67_params(st, *, stop_pct: float) -> None:
    record_strategy6_65_params(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["add_schedule_head"] = [list(x) for x in ADD_SCHEDULE[:4]]
    st.stats["add_schedule_len"] = int(len(ADD_SCHEDULE))
    st.stats["cont_from_rise"] = float(CONT_FROM_RISE)
    st.stats["deep_rung_mult"] = float(DEEP_RUNG_MULT)
    st.stats["deep_rung_from_rise"] = float(DEEP_RUNG_FROM_RISE)


HELP_LOCK = """
策略 6.67 卖点（--strategy version6_67，人裁 2026-10-24；6.65 + 深档三倍）：
  6.65 全部（give 5%+4%×档、均价减仓每 +5% 减 5%、+35%/+55%/… 延续档、
  停泊 80%/100 万、开盘补缺口、延续档止损买回、补一手默认开、总收益抽离
  锁进 600036、上证连续两日 MA10 下方减半、收复买回、现金分红入账后买
  600036）不变。不改 6.65 书。
  深档三倍：涨幅 ≥+115% 的延续档 42→126 万（与 v14 终稿同构剂量 ×3）；
  浅档（<+100%）维持 42 万控长尾。同窗剂量实证：+75.15%/−18.15%（×1）
  → +76.45%/−23.07%（×3）——满仓账户上深档加倍近似纯杠杆，人裁知悉
  采纳（绝对收益 +1.30pp）。
  官方章：backtest_output/csv_minute_v6_67_20251023_20260909_industry
  落盘：backtest_output/csv_minute_v6_67_{start}_{end}/
  已归档（2026-10-24）。不锁 golden。
"""
