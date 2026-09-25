"""eff77f3 canonical CSV/account + #205 quota, on every pandas version.

After mandatory canonical and full structured assertions, compare exact raw
writer/library SHA-256 on the golden's pandas major.minor. A different version
pytest.skips only at that final byte phase, naming golden/runtime versions.
Thus a skipped case has already passed canonical; semantic drift still fails.
"""

import json

import pytest
from backtest.research.csv_strategy_books import BOOKS
from scripts.research.generate_off_byte_baseline import (
    BOOK_NAMES,
    CASES,
    GOLDEN,
    SOURCE,
    assert_case_bytes,
    assert_case_canonical,
    byte_skip_reason,
    capture_case,
    load_canonical_golden,
    post205_expected_case,
)


def test_off_byte_baseline_covers_current_registry_and_standalone_v7():
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert expected["source"] == SOURCE
    assert expected["captured_environment"]["pandas"] == "3.0.6"
    canonical = load_canonical_golden()
    assert canonical["captured_environment"] == expected["captured_environment"]
    assert all(set(case) == {"trades", "equity"} for case in canonical["cases"].values())
    assert len(BOOK_NAMES) == 19
    assert set(expected["books"]) == set(BOOK_NAMES) == set(BOOKS)
    registered_cases = {(book, engine) for book in BOOKS for engine in ("daily", "minute")}
    assert set(CASES) == registered_cases | {("version7", "minute")}
    assert len(CASES) == len(expected["cases"]) == 39
    assert set(expected["cases"]) == {f"{book}/{engine}" for book, engine in CASES}
    for case in expected["cases"].values():
        assert set(case["sha256_csv_bytes"]) == {"trades", "equity"}
        assert set(case["library_sha256_csv_bytes"]) == {"trades", "equity"}
        assert case["fill_counts"]["BUY"] > 0
        assert case["fill_counts"]["SELL"] > 0
    assert sum(len(expected["cases"][f"{book}/{engine}"]["sha256_csv_bytes"])
               for book, engine in registered_cases) == 76
    assert len(expected["cases"]["version7/minute"]["sha256_csv_bytes"]) == 2


@pytest.mark.parametrize("explicit_false", [False, True], ids=["omitted", "explicit-off"])
@pytest.mark.parametrize("book,engine", CASES, ids=[f"{book}-{engine}" for book, engine in CASES])
def test_off_byte_baseline_trades_equity_and_account(book, engine, explicit_false, tmp_path):
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    expected = golden["cases"][f"{book}/{engine}"]
    expected = post205_expected_case(book, expected)
    actual = capture_case(book, engine, tmp_path, explicit_false=explicit_false)
    assert actual["fill_counts"]["BUY"] > 0, (book, engine, "no real BUY")
    assert actual["fill_counts"]["SELL"] > 0, (book, engine, "no real SELL")
    assert len(actual["structured"]["fills"]) == sum(actual["fill_counts"].values())
    assert all(row["shares"] > 0 and row["price"] > 0 for row in actual["structured"]["fills"])
    canonical = load_canonical_golden()["cases"][f"{book}/{engine}"]
    assert_case_canonical(book, actual, expected, canonical)
    reason = byte_skip_reason(golden["captured_environment"]["pandas"])
    if reason:
        pytest.skip(reason)
    assert_case_bytes(actual, expected)
