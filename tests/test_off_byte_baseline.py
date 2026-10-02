"""Historical CSV/account + #205 quota and the scoped S8 correction overlay.

After mandatory canonical and full structured assertions, compare exact raw
writer/library SHA-256 on the golden's pandas major.minor. A different version
pytest.skips only at that final byte phase, naming golden/runtime versions.
Thus a skipped case has already passed canonical; semantic drift still fails.
"""

import json
from hashlib import sha256

import pytest
from backtest.research.csv_strategy_books import BOOKS
from scripts.research.generate_off_byte_baseline import (
    BOOK_NAMES,
    CANONICAL_GOLDEN,
    CASES,
    GOLDEN,
    HISTORICAL_CANONICAL_SHA256,
    HISTORICAL_GOLDEN_SHA256,
    S8_BOOK_NAMES,
    S8_CASES,
    SOURCE,
    assert_case_bytes,
    assert_case_canonical,
    byte_skip_reason,
    capture_case,
    expected_case,
    load_canonical_golden,
    load_s8_golden,
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


def test_s8_overlay_only_replaces_authorized_cases_and_preserves_historical_files():
    assert sha256(GOLDEN.read_bytes()).hexdigest() == HISTORICAL_GOLDEN_SHA256
    assert sha256(CANONICAL_GOLDEN.read_bytes()).hexdigest() == HISTORICAL_CANONICAL_SHA256
    golden = load_s8_golden()
    assert len(S8_CASES) == len(golden["cases"]) == 12
    assert golden["captured_environment"]["pandas"] == "3.0.6"
    assert set(S8_BOOK_NAMES) == {
        "version8", "version8_2", "version8_3", "version8_4", "version8_5", "version8_6",
    }
    assert len(set(CASES) - set(S8_CASES)) == 27
    historical = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for book, engine in set(CASES) - set(S8_CASES):
        actual, _, _ = expected_case(book, engine)
        frozen = historical["cases"][f"{book}/{engine}"]
        assert actual["sha256_csv_bytes"] == frozen["sha256_csv_bytes"]
        assert actual["library_sha256_csv_bytes"] == frozen["library_sha256_csv_bytes"]


@pytest.mark.parametrize("explicit_false", [False, True], ids=["omitted", "explicit-off"])
@pytest.mark.parametrize("book,engine", CASES, ids=[f"{book}-{engine}" for book, engine in CASES])
def test_off_byte_baseline_trades_equity_and_account(book, engine, explicit_false, tmp_path):
    expected, canonical, recorded_pandas = expected_case(book, engine)
    actual = capture_case(book, engine, tmp_path, explicit_false=explicit_false)
    assert actual["fill_counts"]["BUY"] > 0, (book, engine, "no real BUY")
    assert actual["fill_counts"]["SELL"] > 0, (book, engine, "no real SELL")
    assert len(actual["structured"]["fills"]) == sum(actual["fill_counts"].values())
    assert all(row["shares"] > 0 and row["price"] > 0 for row in actual["structured"]["fills"])
    assert_case_canonical(book, actual, expected, canonical)
    reason = byte_skip_reason(recorded_pandas)
    if reason:
        pytest.skip(reason)
    assert_case_bytes(actual, expected)
