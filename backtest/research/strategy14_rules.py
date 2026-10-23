# -*- coding: utf-8 -*-
"""策略 14 — 大资金宽基书（人裁 2026-10-23）。

总资金 5000 万、单票底仓 1 万（人裁八次 2026-10-23 定稿）；底仓 −10% 止损、加仓档 −10% 止损；
底仓价 ×1.15 起每 +20% 加仓 42 万固定档（=基数×42，66 档；保底 100 股——预算不足一手现金池补足），同组在场加仓档 ≤10（人裁七次）；持有时长 ≤180 交易日；涨幅 <100% 峰值回撤 ≥25% 清、涨幅 ≥100% 峰值回撤 ≥15% 清（跨 1 日，两档）；每 +10% 减仓持有筹码 10%（加权均价锚）；
上证闸（单段：连续两日收 MA10 下方停新开+减半、收复买回）；
闲置资金（现金+停泊市值−200 万）×95% 买 600036；现金不足 200 万开盘卖 600036 补足；
总收益每 +总资金 10% 抽出该增量锁定买 600036；现金分红计入收益（入账后买 600036）。无梯子 trail、无延续档买回、
分红计入（DIV_TO_PARKING，人裁二次；GIVE_BASE=99 禁用梯子）。
"""

from __future__ import annotations

from backtest.research.strategy6_55_rules import (  # noqa: F401
    ADD_STEP,
    ALLOW_ADD,
    BAND_WIDTH,
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
    PARKING_EXECUTE,
    PARKING_OPEN_COVER,
    PARKING_SYMBOL,
    PEAK_GAP_MIN,
    PROFIT_SKIM_KEEP_IDLE,
    PROFIT_SKIM_PRO_RATA,
    TP_MIN_DAYS,
    due_cont_rebuy_rise,
    give_band,
    index_cut_shares,
    load_sse_ma10_block_new,
    record_strategy6_55_params,
)

BOOK_TAG = "v14"
NAME_BUDGET = 10_000.0
OPEN_FRAC = 1.0
STOP_PCT = 0.10
STEP_STOP_PCT = 0.10
ADD_SCHEDULE = [(round(0.15 + 0.20 * i, 2), 42.0) for i in range(66)]
ADD_STEP = 99.0  # 禁用通用 +20% 步进梯（due1），加仓只走 schedule（+35% 起）
GIVE_BASE = 99.0  # 禁用梯子 trail（spec 无梯子；exit_line 永不可达）
SCALE_OUT_STEP = 0.10
SCALE_OUT_FRAC = 0.10
SCALE_OUT_ANCHOR = "weighted"
PEAK_DD_EXIT = 0.25  # 涨幅 <100% 档（人裁五次；优化选 2 的 20% 实测 −1.84pp 弃用）
PEAK_DD_SESSIONS = 1
PEAK_DD_EXIT2 = 0.15  # 涨幅 ≥100% 档（人裁五次）
PEAK_DD_MIN_RISE = 1.0
MAX_HOLD_SESSIONS = 180
MAX_LIVE_ADD_LOTS = 10  # 同组在场加仓档上限（人裁七次）
CONT_STOP_REBUY = False
PARKING_FRAC = 0.95  # spec 全量；FRAC=1.0 单变量实证：5亿/100万档下档位 56% 缩至 1/10（unpark 供款不足），留 5% 工作现金
PARKING_BUFFER = 2_000_000.0
PROFIT_SKIM = True
PROFIT_SKIM_STEP = 0.10
PROFIT_SKIM_FRAC = 1.0
PROFIT_SKIM_TO_PARKING = True
DIV_TO_PARKING = True  # 人裁二次：分红计入收益（入账后入停泊 600036）


def lot_budget(name_budget: float, _lots) -> float:
    return float(name_budget)  # 底仓=全额预算（OPEN_FRAC=1.0）


def record_strategy14_params(st, *, stop_pct: float) -> None:
    record_strategy6_55_params(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(STOP_PCT)
    st.stats["step_stop_pct"] = float(STEP_STOP_PCT)
    st.stats["open_frac"] = float(OPEN_FRAC)
    st.stats["add_schedule_head"] = [list(x) for x in ADD_SCHEDULE[:4]]
    st.stats["add_schedule_len"] = int(len(ADD_SCHEDULE))
    st.stats["add_step"] = float(ADD_STEP)
    st.stats["ladder_give_base"] = float(GIVE_BASE)
    st.stats["scale_out_step"] = float(SCALE_OUT_STEP)
    st.stats["scale_out_frac"] = float(SCALE_OUT_FRAC)
    st.stats["peak_dd_exit"] = float(PEAK_DD_EXIT)
    st.stats["peak_dd_sessions"] = int(PEAK_DD_SESSIONS)
    st.stats["max_hold_sessions"] = int(MAX_HOLD_SESSIONS)
    st.stats["max_live_add_lots"] = int(MAX_LIVE_ADD_LOTS)
    st.stats["cont_stop_rebuy"] = bool(CONT_STOP_REBUY)
    st.stats["parking_frac"] = float(PARKING_FRAC)
    st.stats["parking_buffer"] = float(PARKING_BUFFER)
    st.stats["profit_skim"] = bool(PROFIT_SKIM)
    st.stats["peak_dd_exit2"] = float(PEAK_DD_EXIT2)
    st.stats["peak_dd_min_rise"] = float(PEAK_DD_MIN_RISE)
    st.stats["profit_skim_step"] = float(PROFIT_SKIM_STEP)
    st.stats["profit_skim_frac"] = float(PROFIT_SKIM_FRAC)
    st.stats["profit_skim_to_parking"] = bool(PROFIT_SKIM_TO_PARKING)
    st.stats["div_to_parking"] = bool(DIV_TO_PARKING)
    st.stats["index_gate_on"] = bool(INDEX_GATE_ON)
    st.stats["index_cut"] = bool(INDEX_CUT)


HELP_LOCK = """
策略 14 大资金宽基书（--strategy version14，人裁 2026-10-23 一至四次）：
  名单 stock_pool/（A 类同 6.x）；sizing=per_name。
  资金：总 20 亿（运行参数 --cash-total）；单票底仓 10 万（OPEN_FRAC=1.0，预算=底仓）。
  加仓：底仓价 ×1.15 起每 +20% 加仓 42 万固定档（schedule 66 档至 +1315%，
        同组在场加仓档 ≤10）；px/锚成本 14:55 快照触发，每日一档；
        保底 100 股（MIN_LOT_TOP_UP：预算不足一手现金池补足）。
  止损：底仓 −10%；每笔加仓独立 −10%；两档峰撤（跨 1 日）——涨幅 <100% 峰值
        回撤 ≥25% 清仓、涨幅 ≥100% 峰值回撤 ≥15% 清仓；持有 ≤180 交易日到点
        清仓（max_hold:sessions，次日开盘）。
  减仓：每 +10% 减持有筹码 10%（加权均价锚，百股取整）。
  上证闸（单段）：连续两日收 MA10 下方停新开+开盘减半；收复日开盘买回。
  停泊：闲置（现金+停泊市值−200 万）×95% 买 600036（FRAC=1.0 实证档位缩量
        56%，留 5% 工作现金）；现金低于 200 万次日开盘卖 600036 补足；停泊 lot
        不走策略止损/减仓。
  抽离：总收益每 +总资金 10%，该增量全额锁定买 600036。
  分红：现金分红计入收益，入账当日买 600036（DIV_TO_PARKING）。
  无梯子 trail（GIVE_BASE=99 禁用）、无延续档止损买回。
  官方章：backtest_output/csv_minute_v14_20251023_20260909_industry
  落盘：backtest_output/csv_minute_v14_{start}_{end}/
"""
