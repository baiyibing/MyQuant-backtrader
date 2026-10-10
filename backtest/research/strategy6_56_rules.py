# -*- coding: utf-8 -*-
"""策略 6.56 — 6.55 栈 + 7500 万 / 建仓 +20% 保留 / 延续档 +40% 起 42 万 / 同进同出。

6.55 全部（give 5%+4%×档、上证闸门、现金分红买 600036）除下列外不变。
试错仓 / 建仓档金额同 6.55（+10%→0.30、+20%→0.50）。试错仓与建仓档止损 10%。
延续档从 +40%（含）起每 +20% 加 42 万，与试错仓同进同出（不单独止损）。
无同时在仓笔数上限。均价减仓关闭。
峰值相对首仓大于 100% 才走 15%/15 日回撤。闲置现金 ×95% 买 600036，缓冲 100 万。不改 6.55 书。
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
    PARKING_OPEN_COVER,
    PARKING_SYMBOL,
    PEAK_DD_SESSIONS,
    PEAK_GAP_MIN,
    PROFIT_SKIM,
    PROFIT_SKIM_KEEP_IDLE,
    PROFIT_SKIM_PRO_RATA,
    PROFIT_SKIM_TO_PARKING,
    SCALE_OUT_ANCHOR,
    STEP_CAP_PER_CODE,
    STEP_FRAC,
    TP_MIN_DAYS,
    due_cont_rebuy_rise,
    exit_line,
    give_band,
    index_cut_shares,
    load_sse_ma10_block_new,
    lot_budget,
    record_strategy6_55_params,
    take_profit_reason,
)

BOOK_TAG = "v6_56"
STOP_PCT = 0.10
STEP_STOP_PCT = 0.10
CONT_STEP_STOP_PCT = None
CONT_RIDE_TRIAL = True
PROFIT_SKIM_STEP = 0.10
PROFIT_SKIM_FRAC = 0.10
SCALE_OUT_STEP = None
SCALE_OUT_FRAC = None
CONT_FRAC = 42.0
CONT_MAX = None
CONT_FROM_RISE = 0.40
PEAK_DD_EXIT = 0.15
PEAK_DD_MIN_RISE = 1.0
PARKING_FRAC = 0.95
ADD_SCHEDULE = [(0.10, 0.30), (0.20, 0.50)] + [
    (round(0.20 * i, 2), CONT_FRAC) for i in range(2, 53)
]
POST_EXIT_CONT = True
POST_EXIT_CONT_BYPASS_INDEX = False
CASH_TOTAL = 75_000_000


def is_continuation_rise(
    rise: float, *, from_rise: float = CONT_FROM_RISE, frac: float | None = None
) -> bool:
    """42 万档才是延续档；建仓 +20%→0.50 用 frac 排除，延续档从 +40% 起。"""
    if frac is not None:
        return float(frac) + 1e-12 >= float(CONT_FRAC)
    return float(rise) + 1e-12 >= float(from_rise)


def post_exit_schedule_floor(schedule, rise: float) -> int:
    """First continuation ADD_SCHEDULE index at/above the remembered trigger."""
    for i, (threshold, frac) in enumerate(schedule):
        if float(threshold) + 1e-12 >= float(rise) and is_continuation_rise(
            threshold, frac=frac
        ):
            return i
    return len(schedule)


def last_continuation_rise(group, schedule, *, from_rise: float = CONT_FROM_RISE):
    """Highest continuation threshold the group actually opened before a full clear."""
    rises: list[float] = []
    if schedule:
        taken = min(int(getattr(group, "executed_steps", 0) or 0), len(schedule))
        for i in range(taken):
            threshold, frac = schedule[i]
            if is_continuation_rise(threshold, from_rise=from_rise, frac=frac):
                rises.append(float(threshold))
    rises.extend(float(v) for v in getattr(group, "cont_open", {}).values())
    rises.extend(float(v) for v in getattr(group, "cont_rebuy_done", []) or [])
    rises.extend(float(v) for v in getattr(group, "cont_rebuy_armed", []) or [])
    return max(rises) if rises else None


def record_strategy6_56_params(st, *, stop_pct: float) -> None:
    record_strategy6_55_params(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["ladder_give_step"] = float(GIVE_STEP)
    st.stats["div_to_parking"] = bool(DIV_TO_PARKING)
    st.stats["add_schedule_head"] = [list(x) for x in ADD_SCHEDULE[:4]]
    st.stats["add_schedule_len"] = int(len(ADD_SCHEDULE))
    st.stats["cont_max"] = CONT_MAX
    st.stats["cont_live_max"] = CONT_MAX
    st.stats["index_cut_min_keep"] = int(INDEX_CUT_MIN_KEEP)
    st.stats["min_lot_top_up"] = bool(MIN_LOT_TOP_UP)
    st.stats["profit_skim_step"] = float(PROFIT_SKIM_STEP)
    st.stats["profit_skim_frac"] = float(PROFIT_SKIM_FRAC)
    st.stats["step_stop_pct"] = float(STEP_STOP_PCT)
    st.stats["cont_step_stop_pct"] = CONT_STEP_STOP_PCT
    st.stats["cont_ride_trial"] = bool(CONT_RIDE_TRIAL)
    st.stats["scale_out_step"] = SCALE_OUT_STEP
    st.stats["scale_out_frac"] = SCALE_OUT_FRAC
    st.stats["cont_from_rise"] = float(CONT_FROM_RISE)
    st.stats["cont_frac"] = float(CONT_FRAC)
    st.stats["peak_dd_exit"] = float(PEAK_DD_EXIT)
    st.stats["peak_dd_min_rise"] = float(PEAK_DD_MIN_RISE)
    st.stats["parking_frac"] = float(PARKING_FRAC)
    st.stats["post_exit_cont"] = bool(POST_EXIT_CONT)
    st.stats["post_exit_cont_bypass_index"] = bool(POST_EXIT_CONT_BYPASS_INDEX)
    st.stats["cash_total_recipe"] = float(CASH_TOTAL)


HELP_LOCK = """
策略 6.56 卖点（--strategy version6_56，人裁 2026-10-10；建仓+20%保留 / 延续档+40%起42万 / 同进同出 / 峰值>100%）：
  6.55 全部（give 5%+4%×档、开盘补缺口、延续档止损买回、
  补一手默认开、加仓先闲置后锁仓、上证连续两日 MA10 下方减半、收复买回、
  现金分红入账后买 600036）除下列外不变。不改 6.55 书。
  试错仓 OPEN_FRAC 20%（name-budget 10000 → 2000）；建仓档 +10%→0.30、+20%→0.50 保留。
  延续档从 +40%（含）起每 +20% 加 42 万（42.0 × 10000）。
  延续档与试错仓同进同出：试错仓不在仓则不开 42 万；清仓后买回或补档时先补试错仓再开 42 万；
  延续档不单独按自身成交价止损，随组级止损 / 阶梯 / 峰值清仓 / 指数减半一起出。
  无同时在仓笔数上限。上证加仓闸开（含清仓后买回）。
  试错仓与建仓档相对自身成交价止损 10%。
  均价减仓关闭。组级 give 5% + 4%×档。
  峰值相对首仓成本大于 100% 时，回撤 15% 且 15 个交易日未收复才全清。
  总收益每满 10% 抽本金 10% 锁进 600036。闲置现金 ×95% 买 600036，缓冲 100 万。
  最低买入与指数减半保留仍是 100 股。
  组全部清仓后，仅当清仓前开过延续档，现价回到清仓前延续档相对原首仓成本的涨幅时
  先补试错仓再按 42 万买回；只做过试错/建仓就清仓的，不买回。涨停当日仍不买。
  配方资金总额 7500 万（--cash-total 75000000）。
  落盘：backtest_output/csv_minute_v6_56_{start}_{end}/
  已归档（2026-10-10）。version6_55 已归档回官方 _industry（减仓 +5%/5%）。
"""
