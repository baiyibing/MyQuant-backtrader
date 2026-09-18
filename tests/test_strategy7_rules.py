# -*- coding: utf-8 -*-
from datetime import date, timedelta

import pytest

from backtest.research.strategy7_rules import (
    ADD_FRACTION,
    ADD_HM_END,
    ADD_HM_START,
    EIGHT,
    FOUR,
    FULL,
    SIX,
    TIMER_SESSIONS,
    TRIAL,
    TRIAL_FRACTION,
    alternate_tp_decision,
    build_index_gate,
    drawdown_threshold,
    drawdown_tp_triggered,
    in_add_window,
    ladder_decision,
    next_add_target,
    stop_decision,
    timer_due,
    validate_index_symbol,
)


def test_1_locked_stop_lines_and_actions():
    assert TRIAL_FRACTION == pytest.approx(0.20)
    assert ADD_FRACTION == pytest.approx(0.20)
    trial = stop_decision(TRIAL, entry_a=100, average_cost=100)
    assert (trial.action, trial.line) == ("dump_trial", pytest.approx(90))
    four = stop_decision(FOUR, entry_a=100, average_cost=102)
    assert (four.action, four.line) == ("clear_four", pytest.approx(96.9))
    six = stop_decision(SIX, entry_a=100, average_cost=104)
    assert (six.action, six.line) == ("clear_six", pytest.approx(100.36))
    eight = stop_decision(EIGHT, entry_a=100, average_cost=106)
    assert (eight.action, eight.line) == ("clear_eight", pytest.approx(103.35))
    full = stop_decision(FULL, entry_a=100, average_cost=108)
    assert (full.action, full.line) == ("clear_full", pytest.approx(105.84))


def test_2_ladder_is_next_rung_only():
    assert ladder_decision(TRIAL, 104, entry_a=100).action == "add_a104"
    assert ladder_decision(TRIAL, 104, entry_a=100).fraction == pytest.approx(0.20)
    assert ladder_decision(FOUR, 108, entry_a=100).action == "add_a108"
    assert ladder_decision(SIX, 112, entry_a=100).action == "add_a112"
    assert ladder_decision(EIGHT, 116, entry_a=100).action == "add_a116"
    assert ladder_decision(FULL, 120, entry_a=100).action == "none"
    assert next_add_target(TRIAL, entry_a=100) == pytest.approx(104)
    assert next_add_target(FOUR, entry_a=100) == pytest.approx(108)
    assert next_add_target(SIX, entry_a=100) == pytest.approx(112)
    assert next_add_target(EIGHT, entry_a=100) == pytest.approx(116)
    assert next_add_target(FULL, entry_a=100) is None


def test_3_gap_from_trial_still_only_adds_first_rung():
    decision = ladder_decision(TRIAL, 116, entry_a=100)
    assert decision.action == "add_a104"
    assert decision.fraction == pytest.approx(0.20)


def test_4_alternate_bands_and_three_drawdown_thresholds():
    assert alternate_tp_decision(129, 100).action == "none"
    assert alternate_tp_decision(130, 100).fraction == pytest.approx(0.30)
    assert alternate_tp_decision(181, 100).fraction == pytest.approx(1 - 0.7 * 0.8 * 0.7)
    assert drawdown_threshold(0.20) == pytest.approx(0.50)
    assert drawdown_threshold(0.21) == pytest.approx(0.40)
    assert drawdown_threshold(0.51) == pytest.approx(0.20)
    assert drawdown_tp_triggered(FULL, price=110, peak=120, cost=100)
    assert not drawdown_tp_triggered(SIX, price=110, peak=120, cost=100)


def test_5_timer_day_zero_only_trial():
    sessions = [date(2026, 9, 1) + timedelta(days=i) for i in range(12)]
    assert TIMER_SESSIONS == 10
    assert not timer_due(sessions, sessions[0], sessions[9], TRIAL)
    assert timer_due(sessions, sessions[0], sessions[10], TRIAL)
    assert not timer_due(sessions, sessions[0], sessions[10], FOUR)
    assert not timer_due(sessions, sessions[0], sessions[10], SIX)
    assert not timer_due(sessions, sessions[0], sessions[10], EIGHT)
    assert not timer_due(sessions, sessions[0], sessions[10], FULL)
    assert ADD_HM_START == 885
    assert ADD_HM_END == 895
    assert in_add_window(885) and in_add_window(895)
    assert not in_add_window(884) and not in_add_window(896)


def test_6_index_gate_is_lagged_blocks_and_recovers_next_session():
    days = [date(2026, 8, 1) + timedelta(days=i) for i in range(15)]
    values = [100.0] * 9 + [90.0, 89.0, 120.0, 120.0, 120.0, 120.0]
    gate = build_index_gate(dict(zip(days, values)))
    assert gate[days[11]] is True
    assert gate[days[12]] is False
    changed_today = values.copy()
    changed_today[12] = 1.0
    assert build_index_gate(dict(zip(days, changed_today)))[days[12]] is False

    with pytest.raises(ValueError, match="11 warmup"):
        build_index_gate(dict(zip(days[:11], values[:11])))
    for bad_symbol in ("000001", "000001.SZ"):
        with pytest.raises(ValueError, match="exactly 000001.SH"):
            validate_index_symbol(bad_symbol)
