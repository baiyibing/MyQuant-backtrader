# -*- coding: utf-8 -*-
"""策略 6.53 卖点纯函数 — 6.52 栈 + 上证闸门减半持仓、收复买回。

6.52 全部（均价减仓、停泊、抽离、加仓先闲置后锁仓）不变。
上证连续两个交易日收在 MA10 下方：停止进新筹码（含加仓），并把策略持仓减半，
每组至少留 100 股；上证收复 MA10 后按记忆买回减仓筹码。不停泊仓。
"""

from __future__ import annotations

from backtest.research import strategy_book_helpers as _book_helpers

from typing import Optional

BOOK_TAG = "v6_53"
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
INDEX_BLOCKS_S8_ADD = True
INDEX_CUT = True
INDEX_CUT_FRAC = 0.50
INDEX_CUT_MIN_KEEP = 100

PARKING_SYMBOL = "600036.SH"
PARKING_FRAC = 0.80
PARKING_BUFFER = 1_000_000
PARKING_EXECUTE = True
PARKING_OPEN_COVER = True
SCALE_OUT_STEP = 0.05
SCALE_OUT_FRAC = 0.05
SCALE_OUT_ANCHOR = "weighted"
PEAK_DD_EXIT = 0.15
PEAK_DD_SESSIONS = 15
CONT_FROM_RISE = ADD_SCHEDULE[2][0]
CONT_STOP_REBUY = True
CONT_STOP_REBUY_LIFT = 0.20
CONT_STOP_REBUY_FRAC = 1.0
CONT_STOP_REBUY_OPEN_FRAC = OPEN_FRAC
CONT_STOP_REBUY_WITH_SCHEDULE = True
MIN_LOT_TOP_UP = True
PROFIT_SKIM = True
PROFIT_SKIM_STEP = 0.20
PROFIT_SKIM_FRAC = 0.20
PROFIT_SKIM_PRO_RATA = True
PROFIT_SKIM_KEEP_IDLE = True
PROFIT_SKIM_TO_PARKING = True


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


def index_cut_shares(
    held: int,
    *,
    frac: float = INDEX_CUT_FRAC,
    min_keep: int = INDEX_CUT_MIN_KEEP,
    board: int = 100,
) -> int:
    """Board-lot shares to sell so the group is halved and keeps at least min_keep."""
    held = int(held)
    min_keep = int(min_keep)
    board = int(board)
    if held <= min_keep or board <= 0 or float(frac) <= 0:
        return 0
    sell = (int(held * float(frac)) // board) * board
    if held - sell < min_keep:
        sell = ((held - min_keep) // board) * board
    return max(0, int(sell))


def record_strategy6_53_params(st, *, stop_pct: float) -> None:
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
    st.stats["scale_out_anchor"] = str(SCALE_OUT_ANCHOR)
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
    st.stats["profit_skim"] = bool(PROFIT_SKIM)
    st.stats["profit_skim_step"] = float(PROFIT_SKIM_STEP)
    st.stats["profit_skim_frac"] = float(PROFIT_SKIM_FRAC)
    st.stats["profit_skim_pro_rata"] = bool(PROFIT_SKIM_PRO_RATA)
    st.stats["profit_skim_keep_idle"] = bool(PROFIT_SKIM_KEEP_IDLE)
    st.stats["profit_skim_to_parking"] = bool(PROFIT_SKIM_TO_PARKING)
    st.stats["index_cut"] = bool(INDEX_CUT)
    st.stats["index_cut_frac"] = float(INDEX_CUT_FRAC)
    st.stats["index_cut_min_keep"] = int(INDEX_CUT_MIN_KEEP)
    st.stats["index_blocks_s8_add"] = bool(INDEX_BLOCKS_S8_ADD)


def load_sse_ma10_block_new(start, end, *, root=None):
    from backtest.research.strategy8_4_rules import load_sse_ma10_block_new as _load
    return _load(start, end, root=root)


HELP_LOCK = """
策略 6.53 卖点（--strategy version6_53，人裁 2026-10-08；6.52 + 上证闸门减半）：
  6.52 全部（均价减仓、停泊 80%/100 万、开盘补缺口、延续档止损买回、补一手默认开、
  总收益抽离锁进 600036、加仓先闲置后锁仓）不变。
  补一手可用 --no-min-lot-top-up 关。
  上证连续两个交易日收在 MA10 下方：当日开盘停止进新筹码（含加仓），
  策略持仓减半（整手），每组至少留 100 股；同一段闸门只减一次。
  上证收复后开盘按记忆买回减仓筹码（reason add:index_rebuy）。不停泊仓。
  落盘：backtest_output/csv_minute_v6_53_{start}_{end}/
"""
