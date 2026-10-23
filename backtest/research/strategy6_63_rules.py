# -*- coding: utf-8 -*-
"""策略 6.63 — 6.55 栈 + 上证闸门两段式减半 + 延续档前移至 +35% 起。

6.55 全部（give 5%+4%×档、均价减仓、停泊、抽离、上证闸门减半、收复买回、
现金分红买 600036）不变。闸门 episode 内：确认后首个 blocked 日开盘减半（同 6.53+），
连续四日收 MA10 下方（episode 第 3 个 blocked 日）开盘对剩余持仓再减半，
仍保底 100 股。收复买回不变：闸门解除日开盘买回全部被切股数（两段合计）。
延续档阈值 +40%/+60%/… 前移为 +35%/+55%/…（人裁 2026-10-23 四次），
步距 20%、每档 name_budget×42、建仓档 +10%/+20% 不变。
"""

from __future__ import annotations

from backtest.research.strategy6_55_rules import (  # noqa: F401
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
    record_strategy6_55_params,
    take_profit_reason,
)

BOOK_TAG = "v6_63"
INDEX_BELOW_SESSIONS_2 = 4
INDEX_CUT2_FRAC = 0.50
INDEX_CUT2_BLOCKED_DAY = INDEX_BELOW_SESSIONS_2 - INDEX_BELOW_SESSIONS + 1
# 人裁 2026-10-23 四次：延续档 +40%/+60%/… 前移为 +35%/+55%/…（步距 20% 不变，
# 建仓档 +10%/+20% 不变，每档仍是 name_budget×42）。
ADD_SCHEDULE = [(0.10, 0.30), (0.20, 0.50)] + [
    (round(0.35 + 0.20 * i, 2), 42.0) for i in range(50)
]
CONT_FROM_RISE = ADD_SCHEDULE[2][0]


def record_strategy6_63_params(st, *, stop_pct: float) -> None:
    record_strategy6_55_params(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["index_below_sessions_2"] = int(INDEX_BELOW_SESSIONS_2)
    st.stats["index_cut2_frac"] = float(INDEX_CUT2_FRAC)
    st.stats["index_cut2_blocked_day"] = int(INDEX_CUT2_BLOCKED_DAY)
    st.stats["add_schedule_head"] = [list(x) for x in ADD_SCHEDULE[:4]]
    st.stats["add_schedule_len"] = int(len(ADD_SCHEDULE))
    st.stats["cont_from_rise"] = float(CONT_FROM_RISE)


HELP_LOCK = """
策略 6.63 卖点（--strategy version6_63，人裁 2026-10-23；6.55 + 上证闸门两段式减半
+ 延续档前移 +35% 起（同日四次人裁））：
  6.55 全部（give 5%+4%×档、均价减仓每 +5% 减 5%、停泊 80%/100 万、开盘补缺口、
  延续档止损买回、补一手默认开、总收益抽离锁进 600036、加仓先闲置后锁仓、
  上证连续两日 MA10 下方减半、现金分红入账后买 600036）不变。不改 6.55 书。
  上证闸门两段式：连续两日收 MA10 下方 → 确认后首个开盘持仓减半（同前）；
  连续四日收 MA10 下方 → episode 第 3 个 blocked 日开盘对剩余持仓再减半
  （仍保底 100 股、百股取整、最老 lot 优先）；收复买回不变——闸门解除日开盘
  买回全部被切股数（两段合计，同组回补）。
  建仓梯改动：+40%/+60%/… 延续档前移为 +35%/+55%/…（步距 20%、每档
  name_budget×42 不变；建仓档 +10%(0.30)/+20%(0.50) 不变）。
  官方章：backtest_output/csv_minute_v6_63_20251023_20260909_industry
  落盘：backtest_output/csv_minute_v6_63_{start}_{end}/
  已归档（2026-10-23）。不锁 golden。
"""
