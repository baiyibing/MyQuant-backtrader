# -*- coding: utf-8 -*-
"""策略 8 里程碑书（8.1/8.2/8.3）冻结语义 pin。

8.1 = 8fecf5b「20% 绝对地板阶梯」；8.2 = 241b607「v2 比例回撤阶梯」；
8.3 = 9b4b7e2「利弗莫尔宿主包」（卖点委托 livermore_exit_rules，不重冻）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from backtest.research import (
    livermore_exit_rules,
    strategy8_1_rules,
    strategy8_2_rules,
    strategy8_3_rules,
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
    assert get_book("version8_1").sizing == "daily_quota"
    assert get_book("version8_2").sizing == "per_name"
    assert get_book("version8_3").sizing == "per_name"
    assert get_book("version8_1").peak_gap_min == 0
    assert get_book("version8_2").peak_gap_min == 0
    assert get_book("version8_3").peak_gap_min == 15
    assert strategy8_1_rules.STOP_PCT == pytest.approx(0.20)
    assert strategy8_2_rules.STOP_PCT == pytest.approx(0.30)
    assert strategy8_3_rules.STOP_PCT == pytest.approx(0.10)


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
    hooks = apply_csv_strategy(
        "version8_3", index_block_new={date(2026, 1, 5): True}
    )
    allow = hooks["allow_new_name"]
    assert callable(allow)
    assert allow(date(2026, 1, 5)) is False
    assert allow(date(2026, 1, 6)) is True
    assert hooks["index_blocks_add"] is True
    assert callable(hooks["add_gate"])
    assert callable(hooks["name_lot_budget"])
    # 无闸门表时不拦。
    assert apply_csv_strategy("version8_3")["allow_new_name"] is None


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

    st = SimpleNamespace(stats={})
    strategy8_1_rules.record_strategy8_1_params(st)
    assert st.stats["sell_book"] == "v8_1"
    strategy8_2_rules.record_strategy8_2_params(st)
    assert st.stats["sell_book"] == "v8_2"
    strategy8_3_rules.record_strategy8_3_params(st)
    assert st.stats["sell_book"] == "v8_3"
    assert st.stats["probe_frac"] == pytest.approx(0.50)
    assert st.stats["index_blocks_add"] is True
