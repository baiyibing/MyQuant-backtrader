"""Full registry OFF bytes, frozen on eff77f3 before any X-01 behavior change."""

import json

import pytest
from backtest.research.csv_strategy_books import BOOKS
from scripts.research.generate_off_byte_baseline import (
    BOOK_NAMES,
    CASES,
    GOLDEN,
    SOURCE,
    capture_case,
)


def test_off_byte_baseline_covers_current_registry_and_standalone_v7():
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert expected["source"] == SOURCE
    assert len(BOOK_NAMES) == 19
    assert set(expected["books"]) == set(BOOK_NAMES) == set(BOOKS)
    assert set(expected["cases"]) == {f"{book}/{engine}" for book, engine in CASES}
    assert len(expected["cases"]) == 39
    assert sum(len(case["sha256_csv_bytes"]) for case in expected["cases"].values()) == 78


@pytest.mark.parametrize("explicit_false", [False, True], ids=["omitted", "explicit-off"])
@pytest.mark.parametrize("book,engine", CASES, ids=[f"{book}-{engine}" for book, engine in CASES])
def test_off_byte_baseline_trades_equity_and_account(book, engine, explicit_false, tmp_path):
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"][f"{book}/{engine}"]
    actual = capture_case(book, engine, tmp_path, explicit_false=explicit_false)
    assert actual["sha256_csv_bytes"] == expected["sha256_csv_bytes"]
    assert actual["library_sha256_csv_bytes"] == expected["library_sha256_csv_bytes"]
    assert actual["fill_counts"] == expected["fill_counts"]
    assert actual["structured"] == expected["structured"]
