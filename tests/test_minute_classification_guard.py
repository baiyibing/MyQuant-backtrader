"""Registry additions fail in a named test, never during catalog collection."""

from dataclasses import replace
from itertools import product
import runpy

import pytest

from backtest.research import csv_strategy_books as registry
from backtest.research import minute_true_core_wire as wire
from backtest.research.bar_scan_exit import OhlcBar


def test_every_registered_book_is_minute_classified():
    assert {entry.name for entry in wire.minute_strategy_entries()} == set(wire.minute_strategy_names())


@pytest.mark.parametrize("name", sorted(wire._PERCENT_STOP.keys() | wire._BOOK_TAKE.keys()))
def test_registered_defaults_match_literal_percent_and_take_tables(name):
    # TopK defaults require scores; their wire uses separately supplied sell flags.
    kwargs = {"scores_by_day": {"20260101": {"000001": 1.0}}} if name.startswith("topk_") else {}
    hooks = registry.apply_csv_strategy(name, **kwargs)
    if name not in wire._AUTO_DERIVE_EXCLUDED and name in wire._PERCENT_STOP:
        stop, take = wire.derive_percent_stop(name)
        assert stop == hooks["stop_pct"]
        hooks = dict(hooks, take_profit=take)
    if name in wire._PERCENT_STOP:
        assert hooks["stop_pct"] == wire._PERCENT_STOP[name]
    if name in wire._BOOK_TAKE:
        for px, cost, peak, n_days in product((8.0, 10.0, 10.5, 12.0, 20.0), (10.0, 12.0), (12.0, 20.0), (1, 4, 20, 60)):
            assert hooks["take_profit"](px, cost, peak, n_days) == wire._BOOK_TAKE[name](px, cost, peak, n_days)


def register_fake(monkeypatch, **hooks):
    name = "version_fake"
    defaults = dict(stop_pct=0.05, take_profit=lambda px, cost, peak, n_days: "take" if px >= cost * 1.2 else None,
                    record_params=lambda st: None)
    defaults.update(hooks)
    book = replace(registry.BOOKS["version6"], name=name, aliases=(name,), apply=lambda **kwargs: defaults)
    monkeypatch.setitem(registry.BOOKS, name, book)
    return name


def test_new_percent_book_is_derived_without_mutating_literal_tables(monkeypatch):
    name = register_fake(monkeypatch)
    assert name in wire.wired_names()
    assert name not in wire._PERCENT_STOP and name not in wire._BOOK_TAKE
    result = wire.invoke_minute_strategy(name, OhlcBar(10, 10, 9, 10), cost=10, peak=10)
    assert result.decision == "fill" and result.fill_price == 9.5
    result = wire.invoke_minute_strategy(name, OhlcBar(12, 12, 12, 12), cost=10, peak=12)
    assert result.reason == "take"


@pytest.mark.parametrize("hooks", [
    {"stop_pct": None}, {"stop_pct": "0.05"}, {"stop_pct": True}, {"stop_pct": float("nan")},
    {"take_profit": None}, {"take_profit": 42}, {"take_profit": lambda px: None},
    {"stop_range": lambda: None}, {"drawdown_take_profit": 0.1}, {"stage": "trial"},
])
def test_non_derivable_book_names_the_book_and_edit_location(monkeypatch, hooks):
    name = register_fake(monkeypatch, **hooks)
    with pytest.raises(RuntimeError, match=f"{name}.*minute_true_core_wire.py.*_PERCENT_STOP/_BOOK_TAKE"):
        wire.minute_strategy_entries()


def test_special_book_cannot_fall_back_when_literal_is_missing(monkeypatch):
    monkeypatch.delitem(wire._DRAWDOWN, "version1")
    with pytest.raises(RuntimeError, match="version1: requires a special wire"):
        wire.minute_strategy_entries()


def test_gate_reports_failure_and_success(monkeypatch, capsys):
    gate = runpy.run_path("scripts/check_minute_classification.py")
    assert gate["main"]() == 0
    register_fake(monkeypatch, stop_pct=None)
    assert gate["main"]() == 1
    assert "version_fake" in capsys.readouterr().err


def test_test_modules_import_with_an_unclassified_book(monkeypatch):
    register_fake(monkeypatch, stop_pct=None)
    for path in ("tests/test_minute_bar_scan_host.py", "tests/test_minute_true_core_wire.py"):
        runpy.run_path(path)
