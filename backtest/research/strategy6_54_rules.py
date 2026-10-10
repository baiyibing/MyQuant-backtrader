# -*- coding: utf-8 -*-
"""策略 6.54 — 6.53 栈 + 现金分红入账后买入 600036。

6.53 全部（均价减仓、停泊、抽离、上证闸门减半、收复买回、补一手）不变。
隔夜持仓的现金红利在派息日入账，当日按停泊报价全部买进招商银行（600036.SH），
reason=parking:cash_div。涨停/无行情未买完的留到下一交易日。不停策略仓。
"""

from __future__ import annotations

from backtest.research.strategy6_53_rules import (  # noqa: F401
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
    record_strategy6_53_params,
    take_profit_reason,
)

BOOK_TAG = "v6_54"
DIV_TO_PARKING = True


def record_strategy6_54_params(st, *, stop_pct: float) -> None:
    record_strategy6_53_params(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["div_to_parking"] = bool(DIV_TO_PARKING)


HELP_LOCK = """
策略 6.54 卖点（--strategy version6_54，人裁 2026-10-10；6.53 + 现金分红买 600036）：
  6.53 全部（均价减仓、停泊 80%/100 万、开盘补缺口、延续档止损买回、补一手默认开、
  总收益抽离锁进 600036、加仓先闲置后锁仓、上证连续两日 MA10 下方减半、收复买回）不变。
  隔夜持仓现金红利派息日入账，当日按停泊价买入 600036（reason parking:cash_div），
  不预留停车缓冲；涨停或无行情未买完留待次日。招行两笔用实施公告每股现金，
  其余名字用湖 dr 隐含现金（dr<=1.12 且每股>=0.30）。引擎仍不加送股。
  落盘：backtest_output/csv_minute_v6_54_{start}_{end}/
  已归档（2026-10-10）。当前书。不锁 golden。
"""
