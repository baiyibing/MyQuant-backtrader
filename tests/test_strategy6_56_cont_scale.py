# -*- coding: utf-8 -*-
"""6.56：7500 万 / 建仓 +20% 保留 / 延续档 +40% 起 42 万 / 同进同出 / 峰值>100%；6.55 书不变。"""

from __future__ import annotations

import pytest

from backtest.research.cash_div_events import bind_book_cash_div_economics
from backtest.research.csv_simulate_loop import extra_load_codes_for_strategy
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy6_55_rules import (
    ADD_SCHEDULE as ADD_655,
    GIVE_STEP as GIVE_STEP_655,
    INDEX_CUT_MIN_KEEP as KEEP_655,
    MIN_LOT_TOP_UP as TOP_UP_655,
    OPEN_FRAC as OPEN_655,
    PROFIT_SKIM_FRAC as SKIM_FRAC_655,
    PROFIT_SKIM_STEP as SKIM_STEP_655,
    SCALE_OUT_FRAC as SCALE_FRAC_655,
    SCALE_OUT_STEP as SCALE_STEP_655,
    STEP_STOP_PCT as STEP_STOP_655,
    STOP_PCT as STOP_655,
    exit_line as exit_line_655,
)
from backtest.research.strategy6_56_rules import (
    ADD_SCHEDULE,
    CASH_TOTAL,
    CONT_FRAC,
    CONT_FROM_RISE,
    CONT_MAX,
    CONT_RIDE_TRIAL,
    CONT_STEP_STOP_PCT,
    DIV_TO_PARKING,
    GIVE_STEP,
    INDEX_CUT_MIN_KEEP,
    MIN_LOT_TOP_UP,
    OPEN_FRAC,
    PARKING_FRAC,
    PARKING_SYMBOL,
    PEAK_DD_EXIT,
    PEAK_DD_MIN_RISE,
    POST_EXIT_CONT,
    POST_EXIT_CONT_BYPASS_INDEX,
    PROFIT_SKIM_FRAC,
    PROFIT_SKIM_STEP,
    SCALE_OUT_FRAC,
    SCALE_OUT_STEP,
    STEP_STOP_PCT,
    STOP_PCT,
    exit_line,
    is_continuation_rise,
    last_continuation_rise,
    post_exit_schedule_floor,
)


class _Group:
    def __init__(self, executed_steps=0, cont_open=None, armed=None, done=None):
        self.executed_steps = executed_steps
        self.cont_open = cont_open or {}
        self.cont_rebuy_armed = armed or []
        self.cont_rebuy_done = done or []


def test_schedule_stop_skim_and_655_unchanged():
    assert STOP_PCT == pytest.approx(0.10)
    assert STOP_655 == pytest.approx(0.05)
    assert PROFIT_SKIM_STEP == PROFIT_SKIM_FRAC == pytest.approx(0.10)
    assert SKIM_STEP_655 == SKIM_FRAC_655 == pytest.approx(0.20)
    assert OPEN_FRAC == pytest.approx(OPEN_655) == pytest.approx(0.20)
    assert CONT_FRAC == pytest.approx(42.0)
    assert CASH_TOTAL == 75_000_000
    assert STEP_STOP_PCT == pytest.approx(0.10)
    assert STEP_STOP_655 == pytest.approx(0.10)
    assert CONT_STEP_STOP_PCT in (None, False, 0, 0.0)
    assert CONT_RIDE_TRIAL is True
    assert SCALE_OUT_STEP is None
    assert SCALE_OUT_FRAC is None
    assert SCALE_STEP_655 == SCALE_FRAC_655 == pytest.approx(0.05)
    assert CONT_FROM_RISE == pytest.approx(0.40)
    assert PEAK_DD_EXIT == pytest.approx(0.15)
    assert PEAK_DD_MIN_RISE == pytest.approx(1.0)
    assert PARKING_FRAC == pytest.approx(0.95)
    assert is_continuation_rise(0.40, frac=42.0)
    assert is_continuation_rise(0.20, frac=42.0)
    assert not is_continuation_rise(0.20, frac=0.50)
    assert not is_continuation_rise(0.10, frac=0.30)
    assert ADD_SCHEDULE[0] == (0.10, 0.30)
    assert ADD_SCHEDULE[1] == (0.20, 0.50)
    assert ADD_SCHEDULE[2] == (0.40, 42.0)
    assert ADD_SCHEDULE[3] == (0.60, 42.0)
    assert ADD_SCHEDULE[4] == (0.80, 42.0)
    assert CONT_MAX in (None, False, 0)
    assert len(ADD_SCHEDULE) == 53
    assert ADD_655[0] == (0.10, 0.30)
    assert ADD_655[1] == (0.20, 0.50)
    assert ADD_655[2] == (0.40, 42.0)
    assert len(ADD_655) == 52
    assert all(frac == 42.0 for _, frac in ADD_SCHEDULE[2:])
    assert all(frac == 42.0 for _, frac in ADD_655[2:])
    assert GIVE_STEP == pytest.approx(0.04)
    assert GIVE_STEP_655 == pytest.approx(0.04)
    assert exit_line(10.0, 15.0) == pytest.approx(exit_line_655(10.0, 15.0))
    assert INDEX_CUT_MIN_KEEP == KEEP_655 == 100
    assert MIN_LOT_TOP_UP is TOP_UP_655 is True
    assert POST_EXIT_CONT is True
    assert POST_EXIT_CONT_BYPASS_INDEX is False
    assert post_exit_schedule_floor(ADD_SCHEDULE, 0.20) == 2
    assert post_exit_schedule_floor(ADD_SCHEDULE, 0.40) == 2
    assert last_continuation_rise(_Group(executed_steps=0), ADD_SCHEDULE) is None
    assert last_continuation_rise(_Group(executed_steps=2), ADD_SCHEDULE) is None
    assert last_continuation_rise(_Group(executed_steps=3), ADD_SCHEDULE) == pytest.approx(0.40)
    assert last_continuation_rise(_Group(executed_steps=4), ADD_SCHEDULE) == pytest.approx(0.60)


def test_hooks_wire_restored_schedule():
    assert DIV_TO_PARKING is True
    hooks56 = apply_csv_strategy("version6_56")
    hooks55 = apply_csv_strategy("version6_55")
    assert hooks56["name"] == "version6_56"
    assert hooks56["stop_pct"] == pytest.approx(0.10)
    assert hooks55["stop_pct"] == pytest.approx(0.05)
    assert hooks56["profit_skim_step"] == hooks56["profit_skim_frac"] == pytest.approx(0.10)
    assert hooks55["profit_skim_step"] == hooks55["profit_skim_frac"] == pytest.approx(0.20)
    assert hooks55["peak_dd_exit"] == pytest.approx(0.15)
    assert hooks56["step_stop_pct"] == pytest.approx(0.10)
    assert hooks56["cont_step_stop_pct"] in (None, False, 0, 0.0)
    assert hooks56["cont_ride_trial"] is True
    assert hooks56["scale_out_step"] is None
    assert hooks56["scale_out_frac"] is None
    assert hooks56["cont_from_rise"] == pytest.approx(0.40)
    assert hooks56["cont_frac"] == pytest.approx(42.0)
    assert hooks56["peak_dd_min_rise"] == pytest.approx(1.0)
    assert hooks56["peak_dd_exit"] == pytest.approx(0.15)
    assert hooks56["parking_frac"] == pytest.approx(0.95)
    assert hooks56["parking_buffer"] == pytest.approx(1_000_000)
    assert hooks55["parking_frac"] == pytest.approx(0.80)
    assert hooks55["scale_out_step"] == hooks55["scale_out_frac"] == pytest.approx(0.05)
    assert hooks55.get("cont_step_stop_pct") in (None, False, 0, 0.0)
    assert hooks55.get("peak_dd_min_rise") in (None, False, 0, 0.0)
    assert hooks55.get("cont_from_rise") == pytest.approx(0.40)
    assert hooks55.get("cont_step_stop_pct") in (None, False, 0, 0.0)
    assert hooks56["div_to_parking"] is True
    assert hooks56["index_cut"] is True
    assert hooks56["index_cut_min_keep"] == 100
    assert hooks56["min_lot_top_up"] is True
    assert hooks56["add_schedule"][0] == (0.10, 0.30)
    assert hooks56["add_schedule"][1] == (0.20, 0.50)
    assert hooks56["add_schedule"][2] == (0.40, 42.0)
    assert hooks56["add_schedule"][3] == (0.60, 42.0)
    assert len(hooks56["add_schedule"]) == 53
    assert len(hooks55["add_schedule"]) == 52
    assert hooks56.get("cont_live_max") in (None, False, 0)
    assert hooks55.get("cont_live_max") in (None, False, 0)
    assert hooks56["post_exit_cont"] is True
    assert hooks56["post_exit_cont_bypass_index"] is False
    assert hooks55["add_schedule"][2] == (0.40, 42.0)
    assert hooks55.get("post_exit_cont") is not True
    assert hooks55.get("post_exit_cont_bypass_index") is not True
    assert extra_load_codes_for_strategy("version6_56") == {PARKING_SYMBOL}
    stats = {}
    hooks56["record_params"](type("S", (), {"stats": stats})())
    assert stats["sell_book"] == "v6_56"
    assert stats["stop_pct"] == pytest.approx(0.10)
    assert stats["ladder_give_step"] == pytest.approx(0.04)
    assert stats["add_schedule_head"][2] == [0.40, 42.0]
    assert stats["add_schedule_len"] == 53
    assert stats.get("cont_max") in (None, False, 0)
    assert stats.get("cont_live_max") in (None, False, 0)
    assert stats["profit_skim_step"] == stats["profit_skim_frac"] == pytest.approx(0.10)
    assert stats["step_stop_pct"] == pytest.approx(0.10)
    assert stats["cont_step_stop_pct"] in (None, False, 0, 0.0)
    assert stats["cont_ride_trial"] is True
    assert stats["scale_out_step"] is None
    assert stats["scale_out_frac"] is None
    assert stats["cont_from_rise"] == pytest.approx(0.40)
    assert stats["peak_dd_min_rise"] == pytest.approx(1.0)
    assert stats["parking_frac"] == pytest.approx(0.95)
    assert stats["post_exit_cont"] is True
    assert stats["post_exit_cont_bypass_index"] is False
    lock = __import__("backtest.research.strategy6_56_rules", fromlist=["HELP_LOCK"]).HELP_LOCK
    assert "延续档" in lock
    assert "42 万" in lock
    assert "100 股" in lock
    assert "75000000" in lock
    assert "均价减仓关闭" in lock
    assert "同进同出" in lock
    assert "不单独按自身成交价止损" in lock
    assert "同时最多 10 笔" not in lock
    assert "闲置现金 ×95%" in lock
    assert "闲置现金 ×80%" not in lock
    assert "+20%" in lock
    assert "大于 100%" in lock
    assert "+220%" not in lock
    assert "不改 6.55" in lock
    assert "清仓前延续档" in lock
    assert "抽本金 10%" in lock
    assert "上证加仓闸开" in lock
    assert "2700000" not in lock
    assert (
        "已归档"
        in __import__("backtest.research.strategy6_56_rules", fromlist=["HELP_LOCK"]).HELP_LOCK
    )
    assert (
        "version6_55"
        in __import__("backtest.research.strategy6_56_rules", fromlist=["HELP_LOCK"]).HELP_LOCK
    )
    assert (
        "已归档"
        in __import__("backtest.research.strategy6_55_rules", fromlist=["HELP_LOCK"]).HELP_LOCK
    )
    assert (
        "_industry"
        in __import__("backtest.research.strategy6_55_rules", fromlist=["HELP_LOCK"]).HELP_LOCK
    )
    assert (
        "当前书"
        not in __import__("backtest.research.strategy6_55_rules", fromlist=["HELP_LOCK"]).HELP_LOCK
    )


def test_peak_dd_requires_more_than_100_percent_rise():
    from backtest.research.csv_ledger import configure_s8, execute_buy, exit_positions
    from backtest.research.csv_simulate_loop import init_sim_state
    from backtest.research.minute_cash_order import peak_dd_clear_exits

    hooks = apply_csv_strategy("version6_56", name_budget=10_000.0)
    min_rise = float(hooks.get("peak_dd_min_rise") or 0.0)
    assert min_rise == pytest.approx(1.0)
    st = init_sim_state(hooks, total_cash=2_000_000.0, bars_loaded=1, pool_days={})[0]
    configure_s8(st, hooks)
    execute_buy(st, "600000.SH", 10.0, 2_000.0, 0, "2025-11-03")
    (pos,) = exit_positions(st, "600000.SH", 2)
    limits = (100.0, 5.0)
    pos.peak = 19.0
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            16.0,
            "2025-11-05",
            2,
            limits,
            peak_dd_exit=0.15,
            peak_dd_sessions=15,
            peak_dd_min_rise=min_rise,
        )
        == 0
    )
    assert pos.group.peak_dd_start is None
    pos.group.first_lot.peak = 21.0
    pos.peak = 21.0
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            17.0,
            "2025-11-05",
            2,
            limits,
            peak_dd_exit=0.15,
            peak_dd_sessions=15,
            peak_dd_min_rise=min_rise,
        )
        == 0
    )
    assert pos.group.peak_dd_start == 2
    assert (
        peak_dd_clear_exits(
            st,
            "600000.SH",
            pos,
            17.0,
            "2025-11-20",
            17,
            limits,
            peak_dd_exit=0.15,
            peak_dd_sessions=15,
            peak_dd_min_rise=min_rise,
        )
        == 1
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells
    assert all(t["reason"] == "peak_dd_clear" for t in sells)
    assert not st.positions.get("600000.SH")


def test_product_bind_includes_656(monkeypatch):
    from backtest.research import cash_div_events

    monkeypatch.setattr(cash_div_events, "load_cash_div_lookup", lambda *a, **k: {"ok": True})
    assert bind_book_cash_div_economics("6.56", "20251023", "20260909", None) == {"ok": True}
    assert bind_book_cash_div_economics("version6_55", "20251023", "20260909", None) == {"ok": True}
    assert bind_book_cash_div_economics("version6_53", "20251023", "20260909", None) is None
