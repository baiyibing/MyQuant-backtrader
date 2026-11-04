"""Hermetic host-wrapper adjustment policy checks (knife 18 / S22 / B01)."""

import pytest

import oskh_data.reader as reader


def test_live_trading_non_none_adjust_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "live_trading.something")

    with pytest.raises(RuntimeError, match="DataAccessPolicyError") as exc_info:
        reader._enforce_adjust_type_policy("front")

    assert "must use adjust_type='none'" in str(exc_info.value)


def test_trade_decision_non_none_adjust_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "trade_decision.something")

    with pytest.raises(RuntimeError, match="DataAccessPolicyError") as exc_info:
        reader._enforce_adjust_type_policy("back")

    assert "must use adjust_type='none'" in str(exc_info.value)


def test_unknown_caller_non_none_adjust_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "")

    with pytest.raises(
        RuntimeError, match="^DataAccessPolicyError: cannot verify caller module"
    ):
        reader._enforce_adjust_type_policy("front")


def test_restricted_caller_none_adjust_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "live_trading.something")

    assert reader._enforce_adjust_type_policy("none") is None


def test_whitelisted_caller_non_none_adjust_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        reader, "_get_caller_module", lambda: "live_trading.indicators.ma_provider"
    )

    assert reader._enforce_adjust_type_policy("front") is None


def test_research_caller_non_none_adjust_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "scripts.analysis.foo")

    assert reader._enforce_adjust_type_policy("front") is None
