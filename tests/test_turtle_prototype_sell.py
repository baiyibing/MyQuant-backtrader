"""Prototype sells run with runtime risk switches disabled by default."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from trade_decision.presets import evaluate_sell_preset
from trade_decision.presets_protocol import SellPresetContext, SellPresetDecision
from trade_decision.turtle.runtime_flags import (
    is_turtle_risk_enhancements_enabled,
    is_turtle_risk_ma10_exit_enabled,
)
from trade_decision.turtle.sell import _eval_prototype_sell

FLAGS = (
    ("TURTLE_RISK_ENHANCEMENTS_ENABLED", is_turtle_risk_enhancements_enabled),
    ("TURTLE_RISK_MA10_EXIT_ENABLED", is_turtle_risk_ma10_exit_enabled),
)


@pytest.fixture(autouse=True)
def _clear_runtime_flags(monkeypatch):
    for variable, _ in FLAGS:
        monkeypatch.delenv(variable, raising=False)


def _band_context() -> SellPresetContext:
    return SellPresetContext(
        cost_price=10,
        current_price=13,
        holding_high=13,
        units=3,
        hold_days=1,
        is_limit_up=False,
        now_local=datetime(2026, 9, 1, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
    )


def _board_break_context() -> SellPresetContext:
    return SellPresetContext(
        cost_price=None,
        current_price=90,
        holding_high=100,
        hold_days=1,
        is_limit_up=False,
        now_local=datetime(2026, 9, 1, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
        indicators={"was_limit_up": True},
    )


def _assert_band_decision(decision: SellPresetDecision) -> None:
    assert isinstance(decision, SellPresetDecision)
    assert decision.should_sell is True
    assert decision.reason == "bucket_preset:prototype:band:1"
    assert decision.sell_fraction == 0.30


def test_runtime_flags_default_off():
    for _, enabled in FLAGS:
        assert enabled() is False


def test_runtime_flags_reject_zero_and_false_strings(monkeypatch):
    for variable, enabled in FLAGS:
        for value in ("", " ", "0", "false", " FALSE ", "no", " NO ", "off", " Off ", "2", "enabled"):
            monkeypatch.setenv(variable, value)
            assert enabled() is False, (variable, value)
        monkeypatch.delenv(variable)


def test_runtime_flags_accept_true_strings(monkeypatch):
    for variable, enabled in FLAGS:
        for value in ("1", "true", "TRUE", "yes", "on", " 1 ", " True ", " YES ", " On "):
            monkeypatch.setenv(variable, value)
            assert enabled() is True, (variable, value)
            for other_variable, other_enabled in FLAGS:
                if other_variable != variable:
                    assert other_enabled() is False
        monkeypatch.delenv(variable)


def test_prototype_sell_band_runs_with_flags_off():
    decision = _eval_prototype_sell({}, _band_context())

    _assert_band_decision(decision)


def test_prototype_sell_risk_stays_off_without_param_or_env():
    decision = _eval_prototype_sell({}, _board_break_context())

    assert isinstance(decision, SellPresetDecision)
    assert decision.should_sell is False
    assert decision.reason is None


def test_prototype_sell_risk_param_still_board_breaks():
    decision = _eval_prototype_sell(
        {"risk_enhancements_enabled": True}, _board_break_context()
    )

    assert isinstance(decision, SellPresetDecision)
    assert decision.should_sell is True
    assert decision.reason == "bucket_preset:prototype:board_break"


def test_evaluate_sell_preset_prototype_reaches_band():
    decision = evaluate_sell_preset("prototype", {}, _band_context())

    _assert_band_decision(decision)
