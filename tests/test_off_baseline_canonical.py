"""Mutations must fail before a pandas-version skip can hide economic drift."""

from copy import deepcopy
from decimal import InvalidOperation

import pytest
from scripts.research import generate_off_byte_baseline as baseline

from tests import test_off_byte_baseline as matrix


def test_canonical_preserves_precision_text_and_exact_large_integer():
    left = baseline.canonical_csv(
        b"date,code,side,reason,shares,price,commission,equity\r\n"
        b'20251029,000001.SZ,buy,"reason, raw",9007199254740993,9.625,0.12345678,5000000.000000001\r\n'
    )
    right = baseline.canonical_csv(
        b"date,code,side,reason,shares,price,commission,equity\n"
        b'20251029,000001.SZ,buy,"reason, raw",9007199254740993.0,9.62500000,0.123456780,5000000\n'
    )
    assert left == right
    assert left["rows"][0] == {
        "date": "20251029", "code": "000001.SZ", "side": "buy", "reason": "reason, raw",
        "shares": 9007199254740993, "price": "9.62500000", "commission": "0.12345678",
        "equity": "5000000.00000000",
    }


@pytest.mark.parametrize("blob", [
    b"shares\n100.5\n", b"price\nNaN\n", b"equity\nInfinity\n",
    b"date,price\n20251029\n", b"date,date\n20251029,20251029\n",
    b"date,price\n20251029,10,extra\n",
])
def test_invalid_csv_cannot_be_canonicalized(blob):
    with pytest.raises((AssertionError, InvalidOperation)):
        baseline.canonical_csv(blob)


@pytest.fixture
def captured_case(tmp_path, monkeypatch):
    actual = baseline.capture_case("version3", "daily", tmp_path)
    monkeypatch.setattr(matrix, "capture_case", lambda *args, **kwargs: actual)
    return actual


@pytest.mark.parametrize("version", ["2.3.3", "3.0.6"])
@pytest.mark.parametrize("mutation", ["shares", "price", "reason", "eod_mark", "equity", "cash"])
def test_semantic_mutation_fails_before_byte_skip(version, mutation, captured_case, monkeypatch, tmp_path):
    monkeypatch.setattr(baseline.pd, "__version__", version)
    table = captured_case["canonical_csv"]
    if mutation in {"shares", "price", "reason"}:
        table["trades"]["rows"][0][mutation] = {"shares": 1, "price": "10.00000001",
                                                "reason": "changed"}[mutation]
    elif mutation == "eod_mark":
        assert table["trades"]["rows"][-1]["side"] == "EOD_MARK"
        table["trades"]["rows"].pop()
    elif mutation == "equity":
        table["equity"]["rows"][0]["equity"] = "0.00000000"
    else:
        captured_case["structured"]["cash"] += .01
    with pytest.raises(AssertionError, match="canonical"):
        matrix.test_off_byte_baseline_trades_equity_and_account("version3", "daily", False, tmp_path)


@pytest.mark.parametrize("version", ["3.0.6", "3.0.7"])
@pytest.mark.parametrize("field", ["sha256_csv_bytes", "library_sha256_csv_bytes"])
def test_same_major_minor_keeps_raw_hash_checks(version, field, captured_case, monkeypatch, tmp_path):
    monkeypatch.setattr(baseline.pd, "__version__", version)
    captured_case[field]["trades"] = "changed raw bytes, unchanged canonical"
    with pytest.raises(AssertionError):
        matrix.test_off_byte_baseline_trades_equity_and_account("version3", "daily", False, tmp_path)


def test_different_version_skips_bytes_after_canonical_pass(captured_case, monkeypatch, tmp_path):
    monkeypatch.setattr(baseline.pd, "__version__", "2.3.3")
    captured_case["sha256_csv_bytes"]["trades"] = "changed formatting"
    captured_case["library_sha256_csv_bytes"]["trades"] = "different formatting"
    with pytest.raises(pytest.skip.Exception, match=r"golden pandas=3.0.6, runtime pandas=2.3.3"):
        matrix.test_off_byte_baseline_trades_equity_and_account("version3", "daily", False, tmp_path)


def test_library_canonical_and_account_metadata_are_still_checked(captured_case, monkeypatch, tmp_path):
    monkeypatch.setattr(baseline.pd, "__version__", "2.3.3")
    original = deepcopy(captured_case)
    captured_case["library_canonical_csv"]["trades"]["rows"][0]["shares"] = 1
    with pytest.raises(AssertionError, match="canonical library CSV drift"):
        matrix.test_off_byte_baseline_trades_equity_and_account("version3", "daily", False, tmp_path)
    captured_case.update(original)
    del captured_case["structured"]["stats"]["daily_quota"]
    with pytest.raises(AssertionError):
        matrix.test_off_byte_baseline_trades_equity_and_account("version3", "daily", False, tmp_path)
