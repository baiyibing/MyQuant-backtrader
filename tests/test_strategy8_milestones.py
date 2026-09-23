# -*- coding: utf-8 -*-
"""策略 8 里程碑书（8.1/8.2/8.3/8.4）冻结语义 pin。

8.1 = 8fecf5b「20% 绝对地板阶梯」；8.2 = 241b607「v2 比例回撤阶梯」；
8.3 = 9b4b7e2「利弗莫尔宿主包」（卖点委托 livermore_exit_rules，不重冻）；
8.4 = 2026-09-18「stop10-tp10-reserve」；
8.5 = 8.4 止盈改 4%、峰差 30 分钟、未到 +4% 的 T+4 收盘清；
8.6 = 8.5 止损改 6%、T+2 收盘清、关掉 +20% 台阶。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest

from backtest.research import (
    livermore_exit_rules,
    strategy8_1_rules,
    strategy8_2_rules,
    strategy8_3_rules,
    strategy8_4_rules,
    strategy8_5_rules,
    strategy8_6_rules,
)
from backtest.research.csv_strategy_books import (
    apply_csv_strategy,
    get_book,
    normalize_csv_strategy,
)


@dataclass
class _Lot:
    cost: float
    peak: float


def test_milestone_books_registered():
    assert normalize_csv_strategy("8.1") == "version8_1"
    assert normalize_csv_strategy("8.2") == "version8_2"
    assert normalize_csv_strategy("8.3") == "version8_3"
    assert normalize_csv_strategy("8.4") == "version8_4"
    assert normalize_csv_strategy("8.5") == "version8_5"
    assert normalize_csv_strategy("8.6") == "version8_6"
    assert get_book("version8_1").sizing == "daily_quota"
    assert get_book("version8_2").sizing == "per_name"
    assert get_book("version8_3").sizing == "per_name"
    assert get_book("version8_4").sizing == "per_name"
    assert get_book("version8_1").peak_gap_min == 0
    assert get_book("version8_2").peak_gap_min == 0
    assert get_book("version8_3").peak_gap_min == 15
    assert get_book("version8_4").peak_gap_min == 0
    assert get_book("version8_5").sizing == "per_name"
    assert get_book("version8_5").peak_gap_min == 30
    assert get_book("version8_6").sizing == "per_name"
    assert get_book("version8_6").peak_gap_min == 15
    assert strategy8_1_rules.STOP_PCT == pytest.approx(0.20)
    assert strategy8_2_rules.STOP_PCT == pytest.approx(0.30)
    assert strategy8_3_rules.STOP_PCT == pytest.approx(0.10)
    assert strategy8_4_rules.STOP_PCT == pytest.approx(0.10)
    assert strategy8_4_rules.PROFIT_TARGET == pytest.approx(0.20)
    assert strategy8_5_rules.PROFIT_TARGET == pytest.approx(0.04)
    assert strategy8_6_rules.STOP_PCT == pytest.approx(0.02)
    assert strategy8_6_rules.FLOOR_MULT == pytest.approx(1.004)
    assert strategy8_6_rules.KEEP_FRAC == pytest.approx(0.80)
    assert strategy8_6_rules.ADD_STEP == pytest.approx(0.0)
    assert strategy8_6_rules.T1_CLOSE_DAYS == 1


def test_v8_1_absolute_band_floors():
    tp = strategy8_1_rules.take_profit_reason
    # 2% 小档：峰值 +8%（须先摸到 +6%）回撤到 ×1.02。
    assert tp(10.2, 10.0, 10.8) == "trail:band:2"
    assert tp(10.21, 10.0, 10.8) is None
    # 未摸到 +6% 不评小档。
    assert tp(10.2, 10.0, 10.5) is None
    # 15/30 绝对地板档（30% 档须峰值涨幅 ∈ (40%,60%]）。
    assert tp(11.5, 10.0, 12.0) == "trail:band:15"
    assert tp(13.0, 10.0, 14.5) == "trail:band:30"
    # >120% 走峰回撤 20%。
    assert tp(20.0, 10.0, 25.0) == "trail:peak_dd"
    assert tp(20.01, 10.0, 25.0) is None
    # 现价低于成本不止盈。
    assert tp(9.99, 10.0, 12.0) is None


def test_v8_2_proportional_ladder_t1_gate():
    tp = strategy8_2_rules.take_profit_reason
    # T+1（n_days<2）只评止损不评止盈。
    assert tp(10.2, 10.0, 11.0, 1) is None
    # 档2 [6%,15%) 绝对底 ×1.02。
    assert tp(10.2, 10.0, 11.0, 2) == "trail:band:2"
    # 档1 (0,6%) 保留 30%：线 = 10 + 0.3×0.5 = 10.15。
    assert tp(10.15, 10.0, 10.5, 2) == "trail:band:1"
    # 档3 [15%,50%]：max(×1.15, 保留 60%) → 11.5。
    assert tp(11.5, 10.0, 12.0, 2) == "trail:band:3"
    # 档5 >100% 保留 80%：线 = 10 + 0.8×11 = 18.8。
    assert tp(18.8, 10.0, 21.0, 2) == "trail:band:5"
    assert tp(18.81, 10.0, 21.0, 2) is None
    # 现价低于成本不止盈。
    assert tp(9.99, 10.0, 12.0, 2) is None


def test_v8_3_exit_delegates_to_livermore():
    assert (
        strategy8_3_rules.take_profit_reason is livermore_exit_rules.take_profit_reason
    )
    tp = strategy8_3_rules.take_profit_reason
    # 档2 [6%,15%)：×1.02。
    assert tp(10.2, 10.0, 11.0) == "trail:band:2"
    # 满 8 日且峰值从未到 +6% → 僵持平仓。
    assert tp(10.5, 10.0, 10.5, 8) == "force_sell:stale"
    # 峰值 (0,6%] 不评档位回撤。
    assert tp(10.05, 10.0, 10.5) is None
    # T+0 不评。
    assert tp(10.2, 10.0, 11.0, 0) is None


def test_v8_3_probe_and_add_gate():
    lot_budget = strategy8_3_rules.lot_budget
    assert lot_budget(1_000_000.0, []) == pytest.approx(500_000.0)
    assert lot_budget(1_000_000.0, [_Lot(10.0, 10.4)]) == pytest.approx(500_000.0)
    may_add = strategy8_3_rules.may_add
    assert may_add([], 10.0) is True
    # 赢家（现价≥成本）且该码峰值已到 +3% 才加。
    assert may_add([_Lot(10.0, 10.4)], 10.05) is True
    assert may_add([_Lot(10.0, 10.4)], 9.95) is False
    assert may_add([_Lot(10.0, 10.2)], 10.05) is False


def test_v8_3_index_gate_blocks_new_and_add():
    hooks = apply_csv_strategy("version8_3", index_block_new={date(2026, 1, 5): True})
    allow = hooks["allow_new_name"]
    assert callable(allow)
    assert allow(date(2026, 1, 5)) is False
    assert allow(date(2026, 1, 6)) is True
    assert hooks["index_blocks_add"] is True
    assert callable(hooks["add_gate"])
    assert callable(hooks["name_lot_budget"])
    # 无闸门表时不拦。
    assert apply_csv_strategy("version8_3")["allow_new_name"] is None


def test_v8_4_hard_target_and_buy_side():
    tp = strategy8_4_rules.take_profit_reason
    assert strategy8_4_rules.stop_hits(9.01, 10.0) is False
    assert strategy8_4_rules.stop_hits(8.99, 10.0) is True
    assert tp(12.0, 10.0, 12.0, 0) is None
    assert tp(11.99, 10.0, 15.0, 1) is None
    assert tp(12.0, 10.0, 12.0, 1) == "profit_take:target"
    assert tp(12.0, 10.0, 20.0, 30) == "profit_take:target"
    lot0 = SimpleNamespace(lot_id=0, cost=10.0, is_step=False)
    assert strategy8_4_rules.may_add([], 10.0) is False
    assert strategy8_4_rules.may_add([lot0], 9.0) is True
    assert strategy8_4_rules.step_add_due([lot0], 12.0) is True
    assert strategy8_4_rules.step_add_due([lot0], 11.99) is False
    assert strategy8_4_rules.lot_budget(1_000_000.0, [lot0]) == pytest.approx(
        1_000_000.0
    )


def test_v8_4_index_gate_blocks_new_not_add():
    hooks = apply_csv_strategy("version8_4", index_block_new={date(2026, 1, 5): True})
    allow = hooks["allow_new_name"]
    assert callable(allow)
    assert allow(date(2026, 1, 5)) is False
    assert allow(date(2026, 1, 6)) is True
    assert hooks["index_blocks_add"] is False
    assert hooks["reserve_limit_up"] is True
    assert hooks["defer_limit_up"] is False
    assert hooks["peak_gap_min"] == 0
    assert callable(hooks["add_gate"])
    assert callable(hooks["step_add"])
    assert hooks["name_budget"] == pytest.approx(1_000_000.0)
    assert apply_csv_strategy("version8_4")["allow_new_name"] is None


def test_milestone_apply_hooks_and_records():
    h1 = apply_csv_strategy("8.1")
    assert h1["stop_pct"] == pytest.approx(0.20)
    assert h1["sizing"] == "daily_quota"
    assert h1["take_profit"](10.2, 10.0, 10.8) == "trail:band:2"

    h2 = apply_csv_strategy("8.2")
    assert h2["stop_pct"] == pytest.approx(0.30)
    assert h2["sizing"] == "per_name"
    assert h2["name_budget"] == pytest.approx(1_000_000.0)
    assert h2["take_profit"](10.2, 10.0, 11.0, 1) is None

    h3 = apply_csv_strategy("8.3")
    assert h3["stop_pct"] == pytest.approx(0.10)
    assert h3["take_profit"](10.2, 10.0, 11.0) == "trail:band:2"

    h4 = apply_csv_strategy("8.4")
    assert h4["stop_pct"] == pytest.approx(0.10)
    assert h4["take_profit"](12.0, 10.0, 12.0, 1) == "profit_take:target"
    assert h4["take_profit"](11.99, 10.0, 15.0, 1) is None
    assert h4["sizing"] == "per_name"

    st = SimpleNamespace(stats={})
    strategy8_1_rules.record_strategy8_1_params(st)
    assert st.stats["sell_book"] == "v8_1"
    strategy8_2_rules.record_strategy8_2_params(st)
    assert st.stats["sell_book"] == "v8_2"
    strategy8_3_rules.record_strategy8_3_params(st)
    assert st.stats["sell_book"] == "v8_3"
    assert st.stats["probe_frac"] == pytest.approx(0.50)
    assert st.stats["index_blocks_add"] is True
    strategy8_4_rules.record_strategy8_4_params(st)
    assert st.stats["sell_book"] == "v8_4"
    assert st.stats["profit_target"] == pytest.approx(0.20)
    assert st.stats["stale_days"] == 0
    assert st.stats["reserve_limit_up"] is True
    assert st.stats["index_blocks_add"] is False
    assert h4["close_clear"] is None

    h5 = apply_csv_strategy("8.5")
    assert h5["stop_pct"] == pytest.approx(0.10)
    assert h5["peak_gap_min"] == 30
    assert h5["take_profit"](10.40, 10.0, 10.40, 1) == "profit_take:target"
    assert h5["take_profit"](10.39, 10.0, 12.0, 1) is None
    assert h5["close_clear"](10.0, 10.39, 4) == "force_sell:t4_close"
    assert h5["close_clear"](10.0, 10.40, 4) is None
    assert h5["close_clear"](10.0, 10.20, 3) is None
    assert "force_sell:t4_close" in h5["daily_same_bar_prefixes"]
    strategy8_5_rules.record_strategy8_5_params(st)
    assert st.stats["sell_book"] == "v8_5"
    assert st.stats["profit_target"] == pytest.approx(0.04)


def test_v8_5_minute_t4_sells_at_close_not_open():
    from backtest.research.csv_minute_backtest import scan_held_day

    hooks = apply_csv_strategy("version8_5")
    o = np.array([10.2, 10.2])
    h = np.array([10.3, 10.3])
    c = np.array([10.2, 10.2])
    hm = np.array([9 * 60 + 30, 15 * 60])
    idx, px, reason, peak, _ = scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=4,
        can_sell=True,
        stop_pct=hooks["stop_pct"],
        profit_base=0.0,
        trail_ratio=0.0,
        hm=hm,
        peak_gap_min=hooks["peak_gap_min"],
        take_profit=hooks["take_profit"],
        close_clear=hooks["close_clear"],
    )
    assert idx == 1
    assert px == pytest.approx(10.2)
    assert reason == "force_sell:t4_close"
    assert peak == pytest.approx(10.3)

    early, _, early_reason, _, _ = scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=3,
        can_sell=True,
        stop_pct=hooks["stop_pct"],
        profit_base=0.0,
        trail_ratio=0.0,
        hm=hm,
        peak_gap_min=hooks["peak_gap_min"],
        take_profit=hooks["take_profit"],
        close_clear=hooks["close_clear"],
    )
    assert early == -1
    assert early_reason == ""


def test_v8_5_minute_uses_last_bar_when_close_missing():
    from backtest.research.csv_minute_backtest import scan_held_day

    hooks = apply_csv_strategy("version8_5")
    idx, px, reason, _, _ = scan_held_day(
        np.array([10.2, 10.2]),
        np.array([10.25, 10.25]),
        np.array([10.2, 10.21]),
        cost=10.0,
        peak=10.0,
        n_days=4,
        can_sell=True,
        stop_pct=0.10,
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([9 * 60 + 30, 14 * 60 + 55]),
        peak_gap_min=30,
        take_profit=hooks["take_profit"],
        close_clear=hooks["close_clear"],
    )
    assert idx == 1
    assert px == pytest.approx(10.21)
    assert reason == "force_sell:t4_close"


def test_v8_5_peak_gap_blocks_target_not_t4_clear():
    from backtest.research.csv_minute_backtest import scan_held_day

    hooks = apply_csv_strategy("version8_5")
    held, _, held_reason, _, _ = scan_held_day(
        np.array([10.40]),
        np.array([10.50]),
        np.array([10.40]),
        cost=10.0,
        peak=10.0,
        n_days=4,
        can_sell=True,
        stop_pct=0.10,
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([15 * 60]),
        peak_gap_min=30,
        take_profit=hooks["take_profit"],
        close_clear=hooks["close_clear"],
    )
    assert held == -1
    assert held_reason == ""

    idx, _, reason, _, _ = scan_held_day(
        np.array([10.30, 10.40]),
        np.array([10.50, 10.45]),
        np.array([10.30, 10.40]),
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.10,
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([10 * 60, 15 * 60]),
        peak_gap_min=30,
        take_profit=hooks["take_profit"],
        close_clear=hooks["close_clear"],
    )
    assert idx == 1
    assert reason == "profit_take:target"


def test_v8_6_stop2_floor1004_gap15_armexit():
    assert strategy8_6_rules.stop_hits(9.81, 10.0) is False
    assert strategy8_6_rules.stop_hits(9.79, 10.0) is True
    assert strategy8_6_rules.trail_line(10.0, 11.0) == pytest.approx(10.80)
    assert strategy8_6_rules.trail_line(10.0, 10.04) == pytest.approx(10.04)
    assert strategy8_6_rules.take_profit_reason(10.03, 10.0, 10.03, 1) is None
    assert strategy8_6_rules.take_profit_reason(10.04, 10.0, 10.04, 1) == (
        "trail:max1004_80"
    )
    assert strategy8_6_rules.take_profit_reason(10.90, 10.0, 11.0, 1) is None
    assert strategy8_6_rules.take_profit_reason(10.80, 10.0, 11.0, 1) == (
        "trail:max1004_80"
    )
    assert strategy8_6_rules.take_profit_reason(9.90, 10.0, 10.02, 1) is None
    assert strategy8_6_rules.take_profit_reason(9.90, 10.0, 11.0, 1) == (
        "trail:max1004_80"
    )
    assert strategy8_6_rules.take_profit_reason(10.04, 10.0, 10.04, 0) is None
    assert strategy8_6_rules.t1_close_reason(10.0, 10.03, 0) is None
    assert strategy8_6_rules.t1_close_reason(10.0, 10.03, 1) == "force_sell:t1_close"
    assert strategy8_6_rules.t1_close_reason(10.0, 10.04, 1) is None
    hooks = apply_csv_strategy("version8_6")
    assert hooks["stop_pct"] == pytest.approx(0.02)
    assert hooks["step_add"] is None
    assert callable(hooks["add_gate"])
    assert hooks["add_gate"]([SimpleNamespace()], 9.0) is True
    assert "force_sell:t1_close" in hooks["daily_same_bar_prefixes"]
    assert apply_csv_strategy("version8_5")["close_clear"](10.0, 10.2, 2) is None
    assert apply_csv_strategy("version8_5")["close_clear"](10.0, 10.2, 4) == (
        "force_sell:t4_close"
    )


def test_v8_6_minute_clears_on_t1_close():
    from backtest.research.csv_minute_backtest import scan_held_day

    hooks = apply_csv_strategy("version8_6")
    idx, px, reason, _, _ = scan_held_day(
        np.array([10.01, 10.01]),
        np.array([10.02, 10.02]),
        np.array([10.01, 10.01]),
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=hooks["stop_pct"],
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([9 * 60 + 30, 15 * 60]),
        peak_gap_min=hooks["peak_gap_min"],
        take_profit=hooks["take_profit"],
        close_clear=hooks["close_clear"],
    )
    assert idx == 1
    assert px == pytest.approx(10.01)
    assert reason == "force_sell:t1_close"

    early, _, early_reason, _, _ = scan_held_day(
        np.array([10.01, 10.01]),
        np.array([10.02, 10.02]),
        np.array([10.01, 10.01]),
        cost=10.0,
        peak=10.0,
        n_days=0,
        can_sell=False,
        stop_pct=hooks["stop_pct"],
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([9 * 60 + 30, 15 * 60]),
        peak_gap_min=15,
        take_profit=hooks["take_profit"],
        close_clear=hooks["close_clear"],
    )
    assert early == -1
    assert early_reason == ""
