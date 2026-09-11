# -*- coding: utf-8 -*-
from datetime import date, timedelta

import pytest

from backtest.research.strategy7_rules import (
    NINE,
    SEVEN_AFTER_READD,
    SEVEN_NORMAL,
    THREE_AFTER_CHOP,
    TRIAL,
    alternate_tp_decision,
    build_index_gate,
    drawdown_threshold,
    drawdown_tp_triggered,
    ladder_decision,
    next_add_target,
    stop_decision,
    timer_due,
    validate_index_symbol,
)


def test_1_locked_stop_lines_and_actions():
    assert stop_decision(TRIAL, entry_a=100, average_cost=100).line == pytest.approx(96)
    seven = stop_decision(SEVEN_NORMAL, entry_a=100, average_cost=102, trial_lot_present=True)
    assert (seven.action, seven.line, seven.fraction) == pytest.approx(("chop_trial", 99, 4 / 7))
    nine = stop_decision(NINE, entry_a=100, average_cost=108)
    assert nine.action == "clear_nine"
    assert nine.line == pytest.approx(109.08)


def test_2_chop_readd_paths_and_no_invented_stops():
    add1 = ladder_decision(TRIAL, 104, entry_a=100)
    assert add1.action == "add_a104"
    chop = stop_decision(SEVEN_NORMAL, entry_a=100, average_cost=101.7)
    assert chop.action == "chop_trial"
    assert chop.line == pytest.approx(99)
    # A price below avg*0.99 but above A*0.99 must not cause a full clear.
    assert 99 < 100.2 < 101.7 * 0.99
    assert chop.action != "clear_nine"

    readd = ladder_decision(THREE_AFTER_CHOP, 104 * 1.04, entry_a=100, add1_a1=104)
    assert readd.action == "readd_a1_104"
    assert stop_decision(SEVEN_AFTER_READD, entry_a=100, average_cost=104, add1_a1=104).action == "none"
    # H-R12: even a crash after 3a creates no new stop band.
    assert stop_decision(SEVEN_AFTER_READD, entry_a=100, average_cost=104, add1_a1=104).line is None
    final_add = ladder_decision(SEVEN_AFTER_READD, 104 * 1.10, entry_a=100, add1_a1=104)
    assert final_add.action == "readd_a1_110"

    clear_three = stop_decision(THREE_AFTER_CHOP, entry_a=100, average_cost=104, add1_a1=104)
    assert (clear_three.action, clear_three.line) == ("clear_three", pytest.approx(99.84))


def test_3_gap_goes_directly_to_one_jump_nine_action():
    decision = ladder_decision(TRIAL, 112, entry_a=100)
    assert decision.action == "jump_nine"
    assert decision.fraction == pytest.approx(0.50)


def test_4_alternate_bands_and_three_drawdown_thresholds():
    assert alternate_tp_decision(129, 100).action == "none"
    assert alternate_tp_decision(130, 100).fraction == pytest.approx(0.30)
    assert alternate_tp_decision(181, 100).fraction == pytest.approx(1 - 0.7 * 0.8 * 0.7)
    assert drawdown_threshold(0.20) == pytest.approx(0.50)
    assert drawdown_threshold(0.21) == pytest.approx(0.40)
    assert drawdown_threshold(0.51) == pytest.approx(0.20)
    assert drawdown_tp_triggered(NINE, price=110, peak=120, cost=100)
    assert not drawdown_tp_triggered(SEVEN_NORMAL, price=110, peak=120, cost=100)


def test_5_timer_day_zero_nine_disabled_and_chop_target():
    sessions = [date(2026, 9, 1) + timedelta(days=i) for i in range(8)]
    assert not timer_due(sessions, sessions[0], sessions[4], TRIAL)
    assert timer_due(sessions, sessions[0], sessions[5], TRIAL)
    assert not timer_due(sessions, sessions[0], sessions[7], NINE)
    assert next_add_target(THREE_AFTER_CHOP, entry_a=100, add1_a1=104) == pytest.approx(108.16)


def test_6_index_gate_is_lagged_blocks_and_recovers_next_session():
    days = [date(2026, 8, 1) + timedelta(days=i) for i in range(15)]
    values = [100.0] * 9 + [90.0, 89.0, 120.0, 120.0, 120.0, 120.0]
    gate = build_index_gate(dict(zip(days, values)))
    # Day 10's second weak close is only known after that close: day 11 blocks.
    assert gate[days[11]] is True
    # Recovery close on day 11 cannot affect that day's gate, only day 12.
    assert gate[days[12]] is False
    changed_today = values.copy()
    changed_today[12] = 1.0
    assert build_index_gate(dict(zip(days, changed_today)))[days[12]] is False

    with pytest.raises(ValueError, match="11 warmup"):
        build_index_gate(dict(zip(days[:11], values[:11])))
    for bad_symbol in ("000001", "000001.SZ"):
        with pytest.raises(ValueError, match="exactly 000001.SH"):
            validate_index_symbol(bad_symbol)
