# -*- coding: utf-8 -*-
"""CSV 策略书注册表：必须显式指定，无缺省策略 6。"""

from __future__ import annotations

import argparse

import pytest

from backtest.research.csv_strategy_books import (
    BOOKS,
    apply_csv_strategy,
    csv_strategy_names,
    engine_book,
    get_book,
    normalize_csv_strategy,
)


def test_registered_books_are_explicit():
    assert csv_strategy_names() == ("version1", "version2", "version6", "version8")
    assert get_book("version1").allow_add is False
    assert get_book("version1").peak_gap_min == 0
    assert get_book("version2").allow_add is False
    assert get_book("version2").peak_gap_min == 0
    assert get_book("version6").allow_add is False
    assert get_book("version8").allow_add is True
    assert engine_book("v6") == "v6"
    assert engine_book("v8") == "v8"


@pytest.mark.parametrize("strategy", ["version1", "version2"])
def test_apply_early_books(strategy):
    hooks = apply_csv_strategy(strategy)
    assert hooks["stop_pct"] == pytest.approx(0.02)
    assert hooks["allow_add"] is False
    assert hooks["peak_gap_min"] == 0
    assert hooks["take_profit"](10.5, 10.0, 11.0, 1).startswith(
        "profit_take:drawdown"
    )
    assert hooks["take_profit"](9.9, 10.0, 11.0, 1) is None


def test_normalize_requires_strategy():
    with pytest.raises(ValueError, match="required"):
        normalize_csv_strategy("")
    with pytest.raises(ValueError, match="required"):
        normalize_csv_strategy("   ")
    with pytest.raises(ValueError, match="unsupported"):
        normalize_csv_strategy("version7")


def test_apply_version6_is_not_a_silent_fallback():
    hooks = apply_csv_strategy("version6")
    assert hooks["name"] == "version6"
    assert hooks["book"] == "v6"
    assert hooks["allow_add"] is False
    assert hooks["take_profit"] is not None
    assert hooks["stop_pct"] == pytest.approx(0.06)
    assert hooks["take_profit"](10.218, 10.0, 10.50, 1) == "trail:T+1"
    assert hooks["take_profit"](10.222, 10.0, 10.50, 1) is None


def test_missing_cli_strategy_exits():
    ap = argparse.ArgumentParser()
    from backtest.research.csv_strategy_books import add_csv_strategy_arg

    add_csv_strategy_arg(ap)
    with pytest.raises(SystemExit):
        ap.parse_args([])


def test_books_are_separate_modules():
    assert BOOKS["version1"].apply is not BOOKS["version2"].apply
    assert BOOKS["version6"].apply is not BOOKS["version8"].apply
    assert "策略 6" in BOOKS["version6"].help_lock
    assert "策略 8" in BOOKS["version8"].help_lock


@pytest.mark.parametrize("strategy", ["version1", "version2"])
def test_early_book_run_kwargs_stop_override(strategy):
    book = get_book(strategy)
    assert book.run_kwargs(argparse.Namespace(stop_pct=None)) == {
        "strategy": strategy,
        "stop_pct": None,
    }
    assert book.run_kwargs(argparse.Namespace(stop_pct=0.03))["stop_pct"] == pytest.approx(
        0.03
    )
    with pytest.raises(SystemExit, match="in \\(0, 1\\)"):
        book.run_kwargs(argparse.Namespace(stop_pct=1.0))
