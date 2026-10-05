"""Historical CSV/account + #205 quota and scoped S8 / version6_1 / version12 / version9 / version9_1 / version9_2 overlays.

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
    HISTORICAL_BOOK_NAMES,
    HISTORICAL_CASES,
    HISTORICAL_CANONICAL_SHA256,
    HISTORICAL_GOLDEN_SHA256,
    S9_CASES,
    load_s9_golden,
    S12_CASES,
    load_s12_golden,
    S8_BOOK_NAMES,
    S8_CASES,
    SOURCE,
    V6F_BOOK_NAMES,
    V61_BOOK_NAMES,
    V61_CASES,
    V91_BOOK_NAMES,
    V91_CASES,
    V92_BOOK_NAMES,
    V92_CASES,
    assert_case_bytes,
    assert_case_canonical,
    byte_skip_reason,
    capture_case,
    expected_case,
    load_canonical_golden,
    load_s8_golden,
    load_v61_golden,
    load_v91_golden,
    load_v92_golden,
)


def test_off_byte_baseline_covers_current_registry_and_standalone_v7():
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert expected["source"] == SOURCE
    assert expected["captured_environment"]["pandas"] == "3.0.6"
    canonical = load_canonical_golden()
    assert canonical["captured_environment"] == expected["captured_environment"]
    assert all(set(case) == {"trades", "equity"} for case in canonical["cases"].values())
    # Historical golden stays frozen at 19 books / 39 cases; version6_1/version9_1/version9_2 are overlay-only.
    assert len(HISTORICAL_BOOK_NAMES) == 19 and len(HISTORICAL_CASES) == 39
    assert set(expected["books"]) == set(HISTORICAL_BOOK_NAMES)
    assert set(expected["cases"]) == {f"{book}/{engine}" for book, engine in HISTORICAL_CASES}
    assert len(BOOK_NAMES) == 46 and len(CASES) == 93
    assert set(BOOK_NAMES) == set(BOOKS) == set(HISTORICAL_BOOK_NAMES) | set(V61_BOOK_NAMES) | set(V91_BOOK_NAMES) | set(V92_BOOK_NAMES) | set(V6F_BOOK_NAMES)
    registered_cases = {(book, engine) for book in BOOKS for engine in ("daily", "minute")}
    assert set(CASES) == registered_cases | {("version7", "minute")}
    for case in expected["cases"].values():
        assert set(case["sha256_csv_bytes"]) == {"trades", "equity"}
        assert set(case["library_sha256_csv_bytes"]) == {"trades", "equity"}
        assert case["fill_counts"]["BUY"] > 0
        assert case["fill_counts"]["SELL"] > 0
    historical_registered = {
        (book, engine) for book in HISTORICAL_BOOK_NAMES for engine in ("daily", "minute")
    }
    assert sum(len(expected["cases"][f"{book}/{engine}"]["sha256_csv_bytes"])
               for book, engine in historical_registered) == 76
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
    historical_non_overlay = set(HISTORICAL_CASES) - set(S8_CASES) - set(S12_CASES) - set(S9_CASES)
    assert len(historical_non_overlay) == 23
    historical = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for book, engine in historical_non_overlay:
        actual, _, _ = expected_case(book, engine)
        frozen = historical["cases"][f"{book}/{engine}"]
        assert actual["sha256_csv_bytes"] == frozen["sha256_csv_bytes"]
        assert actual["library_sha256_csv_bytes"] == frozen["library_sha256_csv_bytes"]


def test_v61_overlay_only_adds_authorized_cases_and_preserves_historical_files():
    from scripts.research.generate_off_byte_baseline import V61_GOLDEN
    if not V61_GOLDEN.exists():
        pytest.skip("v61 v2 overlay pending first-lot-anchor re-record (--record-v61-v2)")
    assert sha256(GOLDEN.read_bytes()).hexdigest() == HISTORICAL_GOLDEN_SHA256
    assert sha256(CANONICAL_GOLDEN.read_bytes()).hexdigest() == HISTORICAL_CANONICAL_SHA256
    golden = load_v61_golden()
    assert len(V61_CASES) == len(golden["cases"]) == 2
    assert golden["captured_environment"]["pandas"] == "3.0.6"
    assert set(V61_BOOK_NAMES) == {"version6_1"}
    assert set(golden["cases"]) == {"version6_1/daily", "version6_1/minute"}
    historical = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert "version6_1" not in historical["books"]
    assert "version6_1/daily" not in historical["cases"]
    assert "version6_1/minute" not in historical["cases"]
    for book, engine in V61_CASES:
        actual, _, _ = expected_case(book, engine)
        assert actual["sha256_csv_bytes"] == golden["cases"][f"{book}/{engine}"]["sha256_csv_bytes"]
        assert actual["fill_counts"]["BUY"] > 0
        assert actual["fill_counts"]["SELL"] > 0


def test_v91_overlay_only_adds_authorized_cases_and_preserves_historical_files():
    assert sha256(GOLDEN.read_bytes()).hexdigest() == HISTORICAL_GOLDEN_SHA256
    assert sha256(CANONICAL_GOLDEN.read_bytes()).hexdigest() == HISTORICAL_CANONICAL_SHA256
    golden = load_v91_golden()
    assert len(V91_CASES) == len(golden["cases"]) == 2
    assert golden["captured_environment"]["pandas"] == "3.0.6"
    assert set(V91_BOOK_NAMES) == {"version9_1"}
    assert set(golden["cases"]) == {"version9_1/daily", "version9_1/minute"}
    historical = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert "version9_1" not in historical["books"]
    assert "version9_1/daily" not in historical["cases"]
    assert "version9_1/minute" not in historical["cases"]
    for book, engine in V91_CASES:
        actual, _, _ = expected_case(book, engine)
        assert actual["sha256_csv_bytes"] == golden["cases"][f"{book}/{engine}"]["sha256_csv_bytes"]
        assert actual["fill_counts"]["BUY"] > 0
        assert actual["fill_counts"]["SELL"] > 0


def test_v92_overlay_only_adds_authorized_cases_and_preserves_historical_files():
    assert sha256(GOLDEN.read_bytes()).hexdigest() == HISTORICAL_GOLDEN_SHA256
    assert sha256(CANONICAL_GOLDEN.read_bytes()).hexdigest() == HISTORICAL_CANONICAL_SHA256
    golden = load_v92_golden()
    assert len(V92_CASES) == len(golden["cases"]) == 2
    assert golden["captured_environment"]["pandas"] == "3.0.6"
    assert set(V92_BOOK_NAMES) == {"version9_2"}
    assert set(golden["cases"]) == {"version9_2/daily", "version9_2/minute"}
    historical = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert "version9_2" not in historical["books"]
    assert "version9_2/daily" not in historical["cases"]
    assert "version9_2/minute" not in historical["cases"]
    for book, engine in V92_CASES:
        actual, _, _ = expected_case(book, engine)
        assert actual["sha256_csv_bytes"] == golden["cases"][f"{book}/{engine}"]["sha256_csv_bytes"]
        assert actual["fill_counts"]["BUY"] > 0
        assert actual["fill_counts"]["SELL"] > 0
        assert all(row.get("reason") != "stop_loss:turtle_tier"
                   for row in actual["canonical_csv"]["trades"]["rows"])


def test_version12_overlay_only_replaces_ma10_stop_cases():
    golden = load_s12_golden()
    assert golden["captured_environment"]["pandas"] == "3.0.6"
    assert set(golden["cases"]) == {"version12/daily", "version12/minute"}
    for book, engine in S12_CASES:
        actual, canonical, recorded = expected_case(book, engine)
        case = golden["cases"][f"{book}/{engine}"]
        assert actual == case
        assert_case_canonical(book, actual, case, canonical)
        assert recorded == "3.0.6"
        assert case["structured"]["positions"] == {}
        sells = [t for t in case["structured"]["fills"] if t["side"] == "SELL"]
        assert [(t["reason"], t["shares"]) for t in sells] == [
            ("ma_signal:MA10-stop", n) for n in (93000, 100000, 108100)]


def test_version9_overlay_only_replaces_range_stop_cases():
    golden = load_s9_golden()
    assert golden["captured_environment"]["pandas"] == "3.0.6"
    assert set(golden["cases"]) == {"version9/daily", "version9/minute"}
    for book, engine in S9_CASES:
        actual, canonical, recorded = expected_case(book, engine)
        case = golden["cases"][f"{book}/{engine}"]
        assert actual == case
        assert_case_canonical(book, actual, case, canonical)
        assert recorded == "3.0.6"
        assert case["structured"]["stats"]["profit_target"] == 0.10
        assert case["structured"]["stats"]["max_hold"] == 20
        assert case["fill_counts"]["BUY"] > 0
        assert case["fill_counts"]["SELL"] > 0
        sells = [t for t in case["structured"]["fills"] if t["side"] == "SELL"]
        assert all(t["reason"] in {"stop_loss:gap_open", "stop_loss:touch", "stop_loss:close"}
                   for t in sells if t["reason"].startswith("stop_loss"))


@pytest.mark.parametrize("explicit_false", [False, True], ids=["omitted", "explicit-off"])
@pytest.mark.parametrize("book,engine", CASES, ids=[f"{book}-{engine}" for book, engine in CASES])
def test_off_byte_baseline_trades_equity_and_account(book, engine, explicit_false, tmp_path):
    from scripts.research.generate_off_byte_baseline import (
        V61_CASES, V61_GOLDEN, V6F_CASES, V6F_GOLDEN,
    )
    if (book, engine) in V6F_CASES and not V6F_GOLDEN.exists():
        pytest.skip("v6f overlay pending authorized pandas-3.0.6/Linux recording (--record-v6f)")
    if (book, engine) in V61_CASES and not V61_GOLDEN.exists():
        pytest.skip("v61 v2 overlay pending first-lot-anchor re-record (--record-v61-v2)")
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
