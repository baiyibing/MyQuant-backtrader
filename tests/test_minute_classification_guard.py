"""Registry additions fail with a named registration error in the CI gate."""

from dataclasses import replace
import runpy

import pytest

from backtest.research import csv_strategy_books as registry
from backtest.research import minute_classification as classification


def register_fake(monkeypatch, **hooks):
    name = "version_fake"
    defaults = dict(stop_pct=0.05, take_profit=lambda px, cost, peak, n_days: None,
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
    assert {"version4", "version5", "version9_1", "version9_3"} <= set(
        classification.wired_names()
    )
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


@pytest.mark.parametrize("hooks", [
    {"bind_absolute_exit": lambda *args: None},
    {"force_sell_hm": "14:55"},
    {"buy_gate": lambda *args: True},
])
def test_main_engine_hook_is_wired(monkeypatch, hooks):
    name = register_fake(monkeypatch, stop_pct=None, **hooks)
    assert name in classification.wired_names()


@pytest.mark.parametrize("field", classification._SPECIAL_HOOKS)
def test_special_hook_is_wired(monkeypatch, field):
    name = register_fake(monkeypatch, stop_pct=None, take_profit=42, **{field: object()})
    assert name in classification.wired_names()


@pytest.mark.parametrize("hooks", [
    {"stop_pct": None, "take_profit": lambda *a: None},
    {"stop_pct": None},
    {"stop_pct": float("nan")},
    {"stop_pct": float("inf")},
    {"stop_pct": True},
    {"stop_pct": "0.05"},
    {"take_profit": lambda px, cost, peak: None},
    {"take_profit": lambda px, cost, peak, n_days, extra: None},
    {"stop_pct": None, "bind_absolute_exit": 42},
    {"stop_pct": None, "buy_gate": 42},
    {"stop_pct": None, "buy_gate": lambda *args: True, "take_profit": 42},
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


def test_v7_and_app_classification_inspects_registered_execution_hooks(monkeypatch):
    book = registry.get_minute_book('version7')
    calls = []
    def apply(**kwargs):
        calls.append(kwargs)
        return book.apply(**kwargs)
    monkeypatch.setitem(registry.MINUTE_ONLY_BOOKS, 'version7', replace(book, apply=apply))
    entries = classification.minute_strategy_entries()
    assert len(calls) == 2
    assert [(entry.name, entry.cli) for entry in entries[-2:]] == [
        ('version7', classification.CLI_V7), ('topk_app_dropout', classification.CLI_TOPK_APP)]
    monkeypatch.setitem(registry.MINUTE_ONLY_BOOKS, 'version7', replace(book, apply=lambda **kw: {}))
    with pytest.raises(RuntimeError) as error:
        classification.minute_strategy_entries()
    assert 'version7: missing minute exit hooks' in str(error.value)
    assert 'topk_app_dropout: missing minute exit hooks' in str(error.value)
