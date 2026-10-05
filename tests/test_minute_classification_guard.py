"""Registry additions fail with a named registration error in the CI gate."""

from dataclasses import replace
import runpy

import pytest

from backtest.research import csv_strategy_books as registry
from backtest.research import minute_classification as classification


def register_fake(monkeypatch, **hooks):
    name = "version_fake"
    defaults = dict(stop_pct=0.05, take_profit=lambda *args: None,
                    record_params=lambda st: None)
    defaults.update(hooks)
    book = replace(registry.BOOKS["version6"], name=name, aliases=(name,), apply=lambda **kwargs: defaults)
    monkeypatch.setitem(registry.BOOKS, name, book)
    return name


def test_every_registered_book_is_minute_classified():
    names = registry.csv_strategy_names() + classification.EXTRA_MINUTE_STRATEGIES
    entries = classification.minute_strategy_entries()
    assert classification.minute_strategy_names() == names
    assert tuple(entry.name for entry in entries) == names
    assert classification.wired_names() == names
    assert classification.blocked_entries() == ()
    for entry in entries:
        expected_cli = {
            "version7": classification.CLI_V7,
            "topk_app_dropout": classification.CLI_TOPK_APP,
        }.get(entry.name, classification.CLI_MINUTE)
        assert entry == classification.MinuteStrategyEntry(entry.name, expected_cli, "wired", None)


def test_extra_books_cannot_overlap_registry(monkeypatch):
    monkeypatch.setitem(registry.BOOKS, "version7", registry.BOOKS["version6"])
    with pytest.raises(RuntimeError, match="extra minute strategy already registered.*version7"):
        classification.minute_strategy_names()


def test_new_percent_book_is_wired(monkeypatch):
    name = register_fake(monkeypatch)
    assert name in classification.wired_names()


@pytest.mark.parametrize("stop", [None, float("nan"), True, "0.05"])
def test_callable_take_alone_is_wired(monkeypatch, stop):
    name = register_fake(monkeypatch, stop_pct=stop)
    assert name in classification.wired_names()


@pytest.mark.parametrize("field", classification._SPECIAL_HOOKS)
def test_special_hook_is_wired(monkeypatch, field):
    name = register_fake(monkeypatch, stop_pct=None, take_profit=42, **{field: object()})
    assert name in classification.wired_names()


@pytest.mark.parametrize("hooks", [
    {"stop_pct": None, "take_profit": None},
    {"take_profit": 42},
    {"stop_pct": float("nan"), "take_profit": 42},
    {"stop_pct": True, "take_profit": 42},
    {"stop_pct": "0.05", "take_profit": 42},
    dict(stop_pct=None, take_profit=42, **{field: None for field in classification._SPECIAL_HOOKS}),
])
def test_invalid_book_names_the_book_and_registration(monkeypatch, hooks):
    name = register_fake(monkeypatch, **hooks)
    with pytest.raises(RuntimeError, match=f"{name}.*csv_strategy_books"):
        classification.minute_strategy_entries()


def test_gate_reports_failure_and_success(monkeypatch, capsys):
    gate = runpy.run_path("scripts/check_minute_classification.py")
    assert gate["main"]() == 0
    captured = capsys.readouterr()
    assert captured.out == f"Minute classification gate OK: {len(classification.minute_strategy_names())} strategies\n"
    assert captured.err == ""
    register_fake(monkeypatch, stop_pct=None, take_profit=None)
    assert gate["main"]() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Minute classification gate FAILED:\n")
    assert "version_fake" in captured.err
    assert "csv_strategy_books" in captured.err
