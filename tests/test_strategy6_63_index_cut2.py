# -*- coding: utf-8 -*-
"""6.63：上证闸门两段式——第 2 日减半、第 4 日（episode 第 3 个 blocked 日）再减半，收复买回。"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research.csv_ledger import execute_buy, is_parking_lot
from backtest.research.csv_simulate_loop import init_sim_state, run_index_gate_cut_day
from backtest.research.csv_strategy_books import apply_csv_strategy

CODE = "600000.SH"
BUDGET = 10_000.0


def test_index_cut2_hooks_and_scope():
    hooks = apply_csv_strategy("version6_63")
    assert hooks["index_cut"] is True
    assert hooks["index_cut_frac"] == pytest.approx(0.50)
    assert hooks["index_cut2_blocked_day"] == 3
    assert hooks["index_cut2_frac"] == pytest.approx(0.50)
    assert hooks["div_to_parking"] is True
    sibling = apply_csv_strategy("version6_55")
    assert sibling.get("index_cut2_blocked_day") is None
    assert sibling.get("index_cut2_frac") is None
    legacy = apply_csv_strategy("version6_53")
    assert legacy.get("index_cut2_blocked_day") is None


def _state(book="version6_63", cash=2_000_000.0, per=4_000.0):
    hooks = apply_csv_strategy(book, name_budget=BUDGET)
    st = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})[0]
    assert execute_buy(st, CODE, 10.0, per, 0, "2025-11-03")
    return st, hooks


def _bars(px: float = 10.0, days=("2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07", "2025-11-10", "2025-11-11", "2025-11-12", "2025-11-13")):
    idx = pd.to_datetime(list(days))
    return {
        CODE: pd.DataFrame(
            {"open": px, "high": px, "low": px, "close": px, "volume": 1_000_000},
            index=idx,
        )
    }


def _gate(st, hooks, day, ds, bars, blocked):
    hooks["allow_new_name"] = (lambda _d, flag=blocked: not flag)
    run_index_gate_cut_day(
        st,
        hooks,
        day_i=int(ds[-2:]) - 3,
        day=pd.Timestamp(day),
        ds=ds,
        names={},
        daily_bars=bars,
        qlib_limit_pct=0.50,
    )


def _held(st, code=CODE) -> int:
    return sum(int(lot.shares) for lot in st.positions.get(code, []) if not is_parking_lot(st, lot))


def _reasons(st, reason: str) -> list:
    return [t for t in st.trades if t["reason"] == reason]


def test_two_stage_cut_then_rebuy_all_on_recover():
    st, hooks = _state()
    bars = _bars()
    assert _held(st) == 400
    # episode 第 1 个 blocked 日：减半 400 → 200
    _gate(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    stage1 = _reasons(st, "index_cut")
    assert len(stage1) == 1
    assert stage1[0]["shares"] == 200
    assert stage1[0]["price_rule"] == "index_cut_open"
    assert _held(st) == 200
    assert st.stats["index_cut_shares"] == 200
    assert st.stats["index_cut_events"] == 1
    # 第 2 个 blocked 日：未到第二段阈值，不动
    _gate(st, hooks, "2025-11-05", "20251105", bars, blocked=True)
    assert len(_reasons(st, "index_cut")) == 1
    assert _held(st) == 200
    # 第 3 个 blocked 日（连续四日收 MA10 下方）：再减半 200 → 100
    # （成交 reason 两段同为 index_cut，分段只体现在 index_cut2_* 统计）
    _gate(st, hooks, "2025-11-06", "20251106", bars, blocked=True)
    cuts = _reasons(st, "index_cut")
    assert len(cuts) == 2
    assert cuts[1]["shares"] == 100
    assert cuts[1]["date"] == "20251106"
    assert st.stats["index_cut_shares"] == 200  # stage-1 统计不含第二段
    assert st.stats["index_cut2_shares"] == 100
    assert st.stats["index_cut2_events"] == 1
    assert _held(st) == 100
    # 第 4 个 blocked 日：每段每 episode 一次，不再切
    hooks["allow_new_name"] = (lambda _d: False)
    run_index_gate_cut_day(
        st, hooks, day_i=4, day=pd.Timestamp("2025-11-07"), ds="20251107",
        names={}, daily_bars=bars, qlib_limit_pct=0.50,
    )
    assert _held(st) == 100
    assert st.stats["index_cut2_events"] == 1
    # 收复：开盘买回全部被切股数（两段合计 300）
    _gate(st, hooks, "2025-11-07", "20251107", bars, blocked=False)
    rebuys = _reasons(st, "add:index_rebuy")
    assert len(rebuys) == 1
    assert rebuys[0]["shares"] == 300
    assert _held(st) == 400
    assert st.stats["index_rebuy_shares"] == 300


def test_short_episode_cuts_once_only():
    st, hooks = _state()
    bars = _bars()
    _gate(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    assert _held(st) == 200
    # 只 blocked 一日即收复：仅 stage-1
    _gate(st, hooks, "2025-11-05", "20251105", bars, blocked=False)
    assert st.stats.get("index_cut2_shares", 0) == 0
    assert st.stats["index_rebuy_shares"] == 200
    assert _held(st) == 400


def test_new_episode_re_arms_both_stages():
    st, hooks = _state()
    bars = _bars()
    _gate(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    _gate(st, hooks, "2025-11-05", "20251105", bars, blocked=True)
    _gate(st, hooks, "2025-11-06", "20251106", bars, blocked=True)
    _gate(st, hooks, "2025-11-07", "20251107", bars, blocked=False)
    assert _held(st) == 400
    # 第二个 episode：两段重新武装（第一段 400 → 200；用更晚日期避开 rebuy lot 的 T+1）
    _gate(st, hooks, "2025-11-10", "20251110", bars, blocked=True)
    assert st.stats["index_cut_events"] == 2
    assert _held(st) == 200
    _gate(st, hooks, "2025-11-11", "20251111", bars, blocked=True)
    _gate(st, hooks, "2025-11-12", "20251112", bars, blocked=True)
    assert st.stats["index_cut2_events"] == 2
    assert _held(st) == 100


def test_stage2_respects_min_keep_100():
    st, hooks = _state(per=2_000.0)
    bars = _bars()
    assert _held(st) == 200
    _gate(st, hooks, "2025-11-04", "20251104", bars, blocked=True)
    assert _held(st) == 100  # 200 → 100（保底一手）
    _gate(st, hooks, "2025-11-05", "20251105", bars, blocked=True)
    _gate(st, hooks, "2025-11-06", "20251106", bars, blocked=True)
    assert st.stats.get("index_cut2_shares", 0) == 0
    assert _held(st) == 100


def test_version6_55_has_no_stage2():
    st, hooks = _state(book="version6_55")
    bars = _bars()
    for day, ds in (("2025-11-04", "20251104"), ("2025-11-05", "20251105"), ("2025-11-06", "20251106")):
        _gate(st, hooks, day, ds, bars, blocked=True)
    assert len(_reasons(st, "index_cut")) == 1
    assert _held(st) == 200
    assert st.stats.get("index_cut2_shares", 0) == 0
