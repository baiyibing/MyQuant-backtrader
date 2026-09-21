"""Data-free pins for the archived ma_chip rules and entry-close FSM."""

from math import nan
from types import SimpleNamespace

import pytest

from backtest.research import strategy11_rules as rules
from backtest.research.ma_infra import sma_series


def _edges(*, last_close=11, high=12, upper=11, cyqk=0.8, weekly=10,
           previous_cyqk=0.6):
    return rules.edge_condition(
        [10.0] * 60 + [last_close], [12.0] * 60 + [high],
        [11.0] * 60 + [upper], [previous_cyqk] * 60 + [cyqk],
        [10.0] * 60 + [weekly],
    )


def test_edge_and_nan_predecessor_are_distinct():
    assert _edges() == [False] * 60 + [True]
    assert not any(_edges(previous_cyqk=nan))
    assert not any(_edges(cyqk=nan))
    assert not any(rules.edge_condition([10] * 59 + [11], [12] * 60,
                                       [11] * 60, [0.8] * 60, [9] * 60))


@pytest.mark.parametrize("overrides", [
    {"last_close": 10}, {"weekly": 11}, {"high": 11}, {"cyqk": 0.70},
    {"upper": nan}, {"weekly": float("inf")},
])
def test_buy_comparisons_are_strict_and_nonfinite_fail_closed(overrides):
    assert not any(_edges(**overrides))


def test_condition_staying_true_does_not_repeat_edge():
    edges = rules.edge_condition([10] * 60 + [11, 12], [13] * 62,
                                [11] * 62, [0.8] * 62, [9] * 62)
    assert edges[-2:] == [True, False]


def test_lengths_must_match():
    with pytest.raises(ValueError):
        rules.edge_condition([10], [], [10], [0.8], [10])


@pytest.mark.parametrize("close", [9, 10])
def test_entry_red_or_equal_schedules_next_open(close):
    result = rules.exit_signal(close, 10, 8)
    assert result == rules.ExitDecision(rules.EXIT, "ma_signal:entry_nonpositive")


def test_entry_green_tests_sma5_on_entry_day_including_today():
    closes = [20, 20, 20, 9, 10]
    sma5 = sma_series(closes, 5)[-1]
    assert sma5 == 15.8  # today=10 is included, not yesterday's SMA
    assert rules.exit_signal(10, 9, sma5).reason == "ma_signal:SMA5"
    assert rules.exit_signal(11, 10, 11) == rules.ExitDecision(rules.HOLD)


def test_hold_mode_does_not_retest_red_day_and_pending_persists():
    result = rules.exit_signal(11, 10, 10)
    assert result.hold_mode == rules.HOLD
    assert rules.exit_signal(10.5, 11, 10, hold_mode=result.hold_mode) == result
    assert rules.exit_signal(9, 10.5, 10, hold_mode=rules.HOLD).reason == "ma_signal:SMA5"
    assert rules.exit_signal(20, 10, 10, hold_mode=rules.EXIT).hold_mode == rules.EXIT
    assert rules.exit_signal(11, 10, None).hold_mode == rules.HOLD
    with pytest.raises(ValueError):
        rules.exit_signal(11, 10, 10, hold_mode="unknown")


def test_help_records_and_no_intraday_sell():
    for text in ("非已验证多头", "D-1 NaN≠边缘", "等号 fail-closed", "买入日禁卖"):
        assert text in rules.HELP_LOCK
    assert rules.take_profit_reason(1, 100, 200, 0) is None
    st = SimpleNamespace(stats={})
    rules.record_strategy11_params(st)
    assert st.stats["limit_up_chase"] is False
    assert st.stats["sma5_includes_today"] is True
