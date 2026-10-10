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

# Literal order frozen from origin/master tip b1c1080 (pre-RB-05) plus the 6.48/6.49
# admissions, which register next to 6.47; not a live self-compare.
FROZEN_NAMES = (
    "version1", "version2", "version3", "version4", "version5", "version6",
    "version6_1", "version6_2", "version6_3", "version6_4", "version6_5",
    "version6_6", "version6_7", "version6_8", "version6_9", "version6_10",
    "version6_11", "version6_12", "version6_13", "version6_14", "version6_15",
    "version6_16", "version6_17", "version6_18", "version6_19", "version6_20",
    "version6_21", "version6_22", "version6_23", "version6_24", "version6_25",
    "version6_26", "version6_27", "version6_28", "version6_29", "version6_30",
    "version6_31", "version6_32", "version6_33", "version6_34", "version6_35",
    "version6_36", "version6_37", "version6_38", "version6_39", "version6_40",
    "version6_41", "version6_42", "version6_43", "version6_44", "version6_45",
    "version6_46", "version6_47", "version6_48", "version6_49",
    "version6_50", "version6_51", "version6_52", "version6_53",
    "version6_54", "version6_55",
    "version8", "version8_1", "version8_2",
    "version8_3", "version8_4", "version8_5", "version8_6", "version9",
    "version9_2", "version9_3", "version10", "version11", "version12", "topk_dropout",
    "topk_score_exit", "version9_1",
)


def test_registry_names_and_aliases():
    assert csv_strategy_names() == FROZEN_NAMES == tuple(BOOKS)
    assert len(csv_strategy_names()) == len(BOOKS) == len(FROZEN_NAMES)
    for name, book in BOOKS.items():
        assert callable(book.apply)
        assert get_book(name).name == name
        for alias in book.aliases:
            assert normalize_csv_strategy(alias) == name
            assert get_book(alias) is book
    assert "version7" not in BOOKS
    assert tuple(MINUTE_ONLY_BOOKS) == ("version7",)
    assert get_minute_book("version7") is MINUTE_ONLY_BOOKS["version7"]


@pytest.mark.parametrize(
    "name",
    ("version6_1", "version6_11", "version6_45", "version6_46", "version6_47",
     "version6_48", "version6_49", "version6_50", "version6_51",
     "version6_52", "version6_53", "version6_54", "version6_55", "version8", "version1"),
)
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
    family = importlib.import_module("backtest.research.csv_strategy_books_v6_family")
    assert registry.BOOKS is BOOKS
    family_src = Path(inspect.getsourcefile(family)).read_text(encoding="utf-8")
    assert "register(" not in family_src
    assert Path(inspect.getsourcefile(get_book("version6").apply)).name == "csv_strategy_books.py"
    for i in range(1, 56):
        for prefix in ("_apply_version6_", "_run_kwargs_version6_"):
            helper = getattr(family, f"{prefix}{i}")
            assert getattr(registry, f"{prefix}{i}") is helper
        apply_path = Path(inspect.getsourcefile(get_book(f"version6_{i}").apply)).name
        assert apply_path == "csv_strategy_books_v6_family.py"
        run_kwargs = getattr(family, f"_run_kwargs_version6_{i}")
        assert Path(inspect.getsourcefile(run_kwargs)).name == "csv_strategy_books_v6_family.py"
