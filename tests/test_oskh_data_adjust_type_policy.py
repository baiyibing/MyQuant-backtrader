"""Hermetic host-wrapper adjustment policy checks (knife 18 / S22 / B01)."""

from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def reader(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    # Pin the import-time mode so the host's reader.yaml is never consulted
    # (mirrors the OSkhQuant1.3 twin test).
    monkeypatch.setenv("OSKH_DATA_READER_MODE", "parquet")
    from oskh_data import reader

    # Exercise the guard without sending violations to real logging sinks.
    monkeypatch.setattr(reader, "logger", Mock())
    return reader


def test_live_trading_non_none_adjust_is_rejected(monkeypatch: pytest.MonkeyPatch, reader: ModuleType) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "live_trading.something")

    with pytest.raises(RuntimeError, match="DataAccessPolicyError") as exc_info:
        reader._enforce_adjust_type_policy("front")

    assert "must use adjust_type='none'" in str(exc_info.value)


def test_trade_decision_non_none_adjust_is_rejected(monkeypatch: pytest.MonkeyPatch, reader: ModuleType) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "trade_decision.something")

    with pytest.raises(RuntimeError, match="DataAccessPolicyError") as exc_info:
        reader._enforce_adjust_type_policy("back")

    assert "must use adjust_type='none'" in str(exc_info.value)


def test_unknown_caller_non_none_adjust_is_rejected(monkeypatch: pytest.MonkeyPatch, reader: ModuleType) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "")

    with pytest.raises(
        RuntimeError, match="^DataAccessPolicyError: cannot verify caller module"
    ):
        reader._enforce_adjust_type_policy("front")


def test_restricted_caller_none_adjust_is_allowed(monkeypatch: pytest.MonkeyPatch, reader: ModuleType) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "live_trading.something")

    assert reader._enforce_adjust_type_policy("none") is None


def test_whitelisted_caller_non_none_adjust_is_allowed(monkeypatch: pytest.MonkeyPatch, reader: ModuleType) -> None:
    monkeypatch.setattr(
        reader, "_get_caller_module", lambda: "live_trading.indicators.ma_provider"
    )

    assert reader._enforce_adjust_type_policy("front") is None


def test_research_caller_non_none_adjust_is_allowed(monkeypatch: pytest.MonkeyPatch, reader: ModuleType) -> None:
    monkeypatch.setattr(reader, "_get_caller_module", lambda: "scripts.analysis.foo")

    assert reader._enforce_adjust_type_policy("front") is None
