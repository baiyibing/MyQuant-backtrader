# -*- coding: utf-8 -*-
"""策略 6.50 卖点纯函数 — 6.47 栈 + 延续档止损买回（人裁 2026-10-08）。

6.47 全部（-5% 止损、上证闸门、多档建仓梯 42.0 平档、三腿卖出、涨停 Defer）
基础上：延续档（+40% 起）被 step 止损清仓后，股价回到该档阈值 +20 个百分点时，
同组再加 1 个基数，并同时买回 1 个首仓；若建仓梯该日也到期则按日程批准执行。
停泊比例 80% / 缓冲 100 万由分钟/日线引擎在策略日终后真实买卖 600036。
"""

from __future__ import annotations

from backtest.research import strategy_book_helpers as _book_helpers

from typing import Optional

BOOK_TAG = "v6_50"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.05
TP_MIN_DAYS = 1
BAND_WIDTH = 0.05
GIVE_BASE = 0.05
GIVE_STEP = 0.03
NAME_BUDGET = 1_000_000.0
OPEN_FRAC = 0.20
ADD_STEP = 0.20
STEP_FRAC = 1.0
STEP_CAP_PER_CODE = None
STEP_STOP_PCT = 0.10
ADD_SCHEDULE = [(0.10, 0.30), (0.20, 0.50)] + [(0.20 * i, 42.0) for i in range(2, 52)]
INDEX_GATE_ON = True
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = False

PARKING_SYMBOL = "600036.SH"
PARKING_FRAC = 0.80
PARKING_BUFFER = 1_000_000
PARKING_EXECUTE = True
PARKING_OPEN_COVER = True
SCALE_OUT_STEP = 0.05
SCALE_OUT_FRAC = 0.05
PEAK_DD_EXIT = 0.15
PEAK_DD_SESSIONS = 15
CONT_FROM_RISE = ADD_SCHEDULE[2][0]
CONT_STOP_REBUY = True
CONT_STOP_REBUY_LIFT = 0.20
CONT_STOP_REBUY_FRAC = 1.0
CONT_STOP_REBUY_OPEN_FRAC = OPEN_FRAC
CONT_STOP_REBUY_WITH_SCHEDULE = True
MIN_LOT_TOP_UP = True


def give_band(peak: float, cost: float) -> int:
    return _book_helpers.give_band(peak, cost, BAND_WIDTH=BAND_WIDTH)


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


def lot_budget(name_budget: float, _lots) -> float:
    return float(name_budget) * OPEN_FRAC


def is_continuation_rise(rise: float, *, from_rise: float = CONT_FROM_RISE) -> bool:
    return float(rise) + 1e-12 >= float(from_rise)


def due_cont_rebuy_rise(
    armed: list[float],
    px: float,
    cost: float,
    *,
    lift: float = CONT_STOP_REBUY_LIFT,
) -> float | None:
    if not armed or cost <= 0 or px <= 0:
        return None
    trig = float(px) / float(cost) - 1.0
    for rise in armed:
        if float(rise) + float(lift) <= trig + 1e-12:
            return float(rise)
    return None


def record_strategy6_50_params(st, *, stop_pct: float) -> None:
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
    st.stats["open_frac"] = float(OPEN_FRAC)
    st.stats["add_schedule_head"] = [list(x) for x in ADD_SCHEDULE[:4]]
    st.stats["cont_stop_rebuy"] = bool(CONT_STOP_REBUY)
    st.stats["cont_from_rise"] = float(CONT_FROM_RISE)
    st.stats["cont_stop_rebuy_lift"] = float(CONT_STOP_REBUY_LIFT)
    st.stats["cont_stop_rebuy_frac"] = float(CONT_STOP_REBUY_FRAC)
    st.stats["cont_stop_rebuy_open_frac"] = float(CONT_STOP_REBUY_OPEN_FRAC)
    st.stats["cont_stop_rebuy_with_schedule"] = bool(CONT_STOP_REBUY_WITH_SCHEDULE)
    st.stats["parking_frac"] = float(PARKING_FRAC)
    st.stats["parking_buffer"] = float(PARKING_BUFFER)
    st.stats["parking_execute"] = bool(PARKING_EXECUTE)
    st.stats["parking_open_cover"] = bool(PARKING_OPEN_COVER)
    st.stats["min_lot_top_up"] = bool(MIN_LOT_TOP_UP)


def load_sse_ma10_block_new(start, end, *, root=None):
    from backtest.research.strategy8_4_rules import load_sse_ma10_block_new as _load
    return _load(start, end, root=root)


HELP_LOCK = """
策略 6.50 卖点（--strategy version6_50，人裁 2026-10-08；6.47 + 延续档止损买回）：
  6.47 全部（-5% 止损、上证闸门、多档建仓梯、三腿卖出、涨停 Defer）不变。
  停泊：闲置（现金+停泊市值）高于 100 万时，80% 买 600036；否则清仓。
  停泊 lot 不走 6.50 止盈/止损/减仓；净值含停泊市值。T+1 / 涨跌停随引擎。
  开盘评估现金：低于 100 万则按开盘价卖停泊补到 100 万（reason parking:open_cover），再做策略买入。
  策略买单仍不足时，再卖停泊（reason parking:unpark）；补完仍不够则跳过该笔（skip_cash），不停跑。
  补一手：预算整百不足 100 股时，从资金池补到 100 股（industry 亦开；差额记 supplementary）。
  延续档止损买回：+40% 起的建仓梯 lot 被 step 止损清仓后，股价回到该档阈值
  +20 个百分点（例：A0×1.60 加仓后止损，涨到 A0×1.80）时，同组再加 1 个基数
  （reason add:cont_rebuy；不推进该笔的 executed_steps；每档一次），并同时买回
  1 个首仓（reason add:cont_rebuy_open，OPEN_FRAC，非 step）。若建仓梯当日也到期，
  按日程批准后同一日执行 add:tranche（推进 executed_steps）。
  落盘：backtest_output/csv_minute_v6_50_{start}_{end}/
"""
