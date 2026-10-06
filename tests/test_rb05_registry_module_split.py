"""RB-05 import and registry contracts, without market data."""

import importlib
import inspect
from pathlib import Path

import pytest

from backtest.research.csv_strategy_books import (
    BOOKS,
    MINUTE_ONLY_BOOKS,
    apply_csv_strategy,
    csv_strategy_names,
    get_book,
    get_minute_book,
    normalize_csv_strategy,
)

# Freeze the live registry once at collection, as required by RB-05.
FROZEN_NAMES = tuple(BOOKS)


def test_registry_names_and_aliases():
    assert FROZEN_NAMES
    assert csv_strategy_names() == FROZEN_NAMES == tuple(BOOKS)
    assert len(csv_strategy_names()) == len(BOOKS)
    for name, book in BOOKS.items():
        assert callable(book.apply)
        assert get_book(name).name == name
        for alias in book.aliases:
            assert normalize_csv_strategy(alias) == name
            assert get_book(alias) is book
    assert "version7" not in BOOKS
    assert tuple(MINUTE_ONLY_BOOKS) == ("version7",)
    assert get_minute_book("version7") is MINUTE_ONLY_BOOKS["version7"]


@pytest.mark.parametrize("name", ("version6_1", "version6_47", "version8", "version1"))
def test_default_apply_keys(name):
    hooks = apply_csv_strategy(name)
    assert isinstance(hooks, dict)
    assert {"stop_pct", "take_profit", "record_params", "name", "sizing"} <= hooks.keys()
    assert hooks["name"] == name
    if name != "version1":
        assert hooks["sizing"] == "per_name"
        assert callable(hooks["name_lot_budget"])
        assert hooks["name_budget"] == 1_000_000.0


def test_import_identity_and_helper_location():
    registry = importlib.import_module("backtest.research.csv_strategy_books")
    original_books = registry.BOOKS
    family = importlib.import_module("backtest.research.csv_strategy_books_v6_family")
    assert registry.BOOKS is original_books is BOOKS
    for i in range(1, 48):
        for prefix in ("_apply_version6_", "_run_kwargs_version6_"):
            helper = getattr(family, f"{prefix}{i}")
            assert getattr(registry, f"{prefix}{i}") is helper
    assert Path(inspect.getsourcefile(get_book("version6_45").apply)).name == (
        "csv_strategy_books_v6_family.py"
    )
