"""Frozen, data-free OFF matrix captured before X-01 at eff77f3.

The production writers are called unchanged. Their bytes are never normalized:
the shared pandas writer uses Linux LF and the standalone v7 csv writer CRLF.
The independent library serialization explicitly pins those same line endings.
Run this script with --check after implementation; generation refuses another
HEAD or an existing golden, so updating a baseline cannot hide a regression.
Checks retain the eff77f3 bytes/account contract and require the single #205
metadata addition. Canonical CSV/account checks always run; raw byte checks
require the golden's pandas major.minor (otherwise --check reports SKIP).
Six per_name strategy-8 books use the explicit 2026-09-26 correction overlay;
the other 27 cases still use the immutable historical files. --record-s8 writes
only those 12 corrected cases and refuses to replace an existing overlay.
See docs/backtest/s8-independent-positions-2026-09-26.md.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import inspect
import io
import json
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.csv_artifacts import write_run_artifacts
from backtest.research.csv_strategy_books import BOOKS

SOURCE = "eff77f375f5636e3e9659aa8fd753404035f2782"
GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_eff77f3.json"
CANONICAL_GOLDEN = ROOT / "tests/fixtures/off_canonical_baseline_eff77f3.json"
HISTORICAL_GOLDEN_SHA256 = "3bfe51b6d3e20b665c3fed0449ebf8569988022719da275b7fcc9635a9988c6c"
HISTORICAL_CANONICAL_SHA256 = "34f611da359f1a1d059bc78be75b2e9e2458c533b1dc3b46cfd61130fca7a04e"
S8_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_s8_independent_20260926.json"
S8_RULE_REVISION = "s8-independent-group-exits-2026-09-26"
S8_BOOK_NAMES = ("version8", "version8_2", "version8_3", "version8_4", "version8_5", "version8_6")
S8_CASES = tuple((book, engine) for book in S8_BOOK_NAMES for engine in ("daily", "minute"))
BOOK_NAMES = (
    "version1", "version2", "version3", "version4", "version5", "version6",
    "version8", "version8_1", "version8_2", "version8_3", "version8_4",
    "version8_5", "version8_6", "version9", "version10", "version11",
    "version12", "topk_dropout", "topk_score_exit",
)
CODE = "600000.SH"
TOPK_CODES = (CODE, "600001.SH", "600002.SH")
CASES = tuple((book, engine) for book in BOOK_NAMES for engine in ("daily", "minute")) + (
    ("version7", "minute"),
)
# Eight decimal places retain sub-cent fills/fees while removing float tails.
MONEY_QUANTUM = Decimal("0.00000001")
MONEY_FIELDS = frozenset({"price", "notional", "commission", "cash", "holdings", "equity"})
INTEGER_FIELDS = frozenset({"shares", "lot", "hm"})
CANONICAL_CONTRACT = {
    "schema": 1,
    "money_quantum": str(MONEY_QUANTUM),
    "rounding": "ROUND_HALF_EVEN",
    "money_fields": sorted(MONEY_FIELDS),
    "integer_fields": sorted(INTEGER_FIELDS),
    "text": "verbatim; preserve all columns and row/column order, including EOD_MARK",
    "hash": "sha256 of UTF-8 JSON; ensure_ascii=False, sort_keys=True, separators=(',', ':')",
}


def frozen_inputs():
    """Quarter/eighth prices avoid dependency-sensitive numeric construction."""
    dates = pd.bdate_range("2025-10-13", periods=25)
    prices = [10.] * 12 + [10., 10.5, 10.75, 11., 10.5, 9.75, 9.25,
                           9.75, 10.25, 10., 9.75, 10.25, 10.]
    bars = pd.DataFrame({
        "open": [p - .125 for p in prices],
        "high": [p + .25 for p in prices],
        "low": [p - .25 for p in prices],
        "close": prices,
        "volume": [100_000.] * len(prices),
    }, index=dates, dtype="float64")
    rows = []
    for day, price in zip(dates, prices):
        for hm, offset in ((570, -.125), (585, 0.), (870, .125), (895, 0.), (900, 0.)):
            rows.append({
                "time": day + pd.Timedelta(minutes=hm),
                "open": price - .125, "high": price + .25,
                "low": price - .25, "close": price + offset,
                "volume": 10_000., "ymd": day.strftime("%Y%m%d"), "hm": hm,
            })
    minutes = pd.DataFrame(rows).set_index("time")
    start, end = (dates[i].strftime("%Y%m%d") for i in (12, -1))
    pools = {dates[j].strftime("%Y%m%d"): [CODE] for j in (12, 14, 18)}
    return bars, minutes, pools, start, end, dates


def _eligible_buy(_code, _day):
    return True


def run_case(book: str, engine: str, *, explicit_false: bool = False):
    bars, minutes, pools, start, end, dates = frozen_inputs()
    daily_bars, minute_bars = {CODE: bars}, {CODE: minutes}
    index_gate = {d.strftime("%Y%m%d"): False for d in dates[12:]}
    kwargs = {"strategy": book, "ration": "file_order", "ration_seed": 0,
              "total_cash": 5_000_000., "daily_quota": 1_000_000.,
              "index_block_new": index_gate}
    if book.startswith("topk_"):
        daily_bars = {code: bars.copy() for code in TOPK_CODES}
        minute_bars = {code: minutes.copy() for code in TOPK_CODES}
        scores = {}
        for i, day in enumerate(dates[12:]):
            # Both ranking exits and SX0 have frozen, nonempty day plans.
            values = ((3., 2., 1.), (-1., 3., 2.), (3., 1., 2.))[i % 3]
            scores[day.strftime("%Y%m%d")] = dict(zip(TOPK_CODES, values))
        kwargs.update(scores_by_day=scores, topk=2, n_drop=1,
                      eligible_buy=_eligible_buy, keep_buy_vacancy=False)
    if book == "version7":
        return v7.simulate_v7(minute_bars, daily_bars, pools,
                              index_days={day.date(): 3000. for day in dates},
                              cash_total=5_000_000., start=start, end=end)
    simulate = daily.simulate if engine == "daily" else minute.simulate
    if explicit_false:
        # The pre-change commit has no new API. Once added, every supported
        # default-OFF switch is passed explicitly (including non-s12 books).
        kwargs.update({name: False for name in inspect.signature(simulate).parameters
                       if name.startswith("fix_")})
    args = (daily_bars,) if engine == "daily" else (minute_bars, daily_bars)
    return simulate(*args, pools, start, end, **kwargs)


def _hash(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _canonical_value(field: str, value):
    if field in MONEY_FIELDS | INTEGER_FIELDS:
        number = Decimal(str(value))
        assert number.is_finite(), (field, value, "non-finite number")
        if field in INTEGER_FIELDS:
            assert number == number.to_integral_value(), (field, value, "fractional integer")
            return int(number)
        with localcontext() as ctx:
            ctx.prec = 50
            return format(number.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN), "f")
    # Preserve dates, symbols, case, reasons and all other text verbatim.
    return str(value)


def _canonical_rows(columns, rows):
    columns = list(columns)
    assert columns and len(columns) == len(set(columns)), ("invalid columns", columns)
    result = []
    for row in rows:
        assert set(row) == set(columns), ("CSV/structured row schema mismatch", row)
        assert all(value is not None for value in row.values()), ("missing CSV value", row)
        result.append({field: _canonical_value(field, row[field]) for field in columns})
    # Column order, row order and every field remain part of the contract.
    return {"columns": columns, "rows": result}


def canonical_csv(blob: bytes) -> dict:
    """Parse with stdlib csv; never round-trip through pandas or binary floats."""
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8"), newline=""))
    return _canonical_rows(reader.fieldnames, reader)


def canonical_hash(table: dict) -> str:
    blob = json.dumps(table, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _hash(blob.encode("utf-8"))


def load_canonical_golden() -> dict:
    """The companion binds full eff77f3 CSVs (also EOD_MARK) to the raw golden.

    structured.fills alone cannot reconstruct EOD_MARK rows. The companion was
    generated from original eff77f3 outputs only after every raw hash matched.
    """
    golden = json.loads(CANONICAL_GOLDEN.read_text(encoding="utf-8"))
    assert golden["source"] == SOURCE
    assert golden["raw_golden_sha256"] == _hash(GOLDEN.read_bytes())
    assert golden["contract"] == CANONICAL_CONTRACT
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in CASES}
    return golden


def load_s8_golden() -> dict:
    """Only the authorized 12 cases may supersede their historical contract."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(S8_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == S8_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(S8_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in S8_CASES}
    return golden


def expected_case(book: str, engine: str) -> tuple[dict, dict, str]:
    """Return account/raw, canonical hashes, and the recorded pandas version."""
    key = f"{book}/{engine}"
    if (book, engine) in S8_CASES:
        golden = load_s8_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    case = post205_expected_case(book, golden["cases"][key])
    canonical = load_canonical_golden()["cases"][key]
    return case, canonical, golden["captured_environment"]["pandas"]


def assert_case_canonical(book: str, actual: dict, expected: dict, canonical_expected: dict):
    """Mandatory on every pandas version, before any byte-check skip."""
    for field, label in (("canonical_csv", "production"), ("library_canonical_csv", "library")):
        hashes = {name: canonical_hash(table) for name, table in actual[field].items()}
        assert hashes == canonical_expected, (book, f"canonical {label} CSV drift")
    assert _canonical_value("cash", actual["structured"]["cash"]) == _canonical_value(
        "cash", expected["structured"]["cash"]), (book, "canonical cash drift")
    assert actual["fill_counts"] == expected["fill_counts"]
    # Keep the original stronger, unrounded account/positions/stats assertion too.
    assert actual["structured"] == expected["structured"]


def byte_skip_reason(recorded_pandas: str) -> str | None:
    runtime = pd.__version__
    if runtime.split(".")[:2] != recorded_pandas.split(".")[:2]:
        return (f"raw CSV byte checks skipped: golden pandas={recorded_pandas}, "
                f"runtime pandas={runtime} (major.minor differs); "
                "canonical trades/equity/cash and full structured assertions passed")
    return None


def assert_case_bytes(actual: dict, expected: dict):
    """Original exact raw SHA-256 contract, including writer/library equality."""
    assert actual["sha256_csv_bytes"] == actual["library_sha256_csv_bytes"], "writer/library mismatch"
    assert actual["sha256_csv_bytes"] == expected["sha256_csv_bytes"]
    assert actual["library_sha256_csv_bytes"] == expected["library_sha256_csv_bytes"]


def _library_bytes(state, book: str):
    if book != "version7":
        return {
            "trades": pd.DataFrame(state.trades).to_csv(
                index=False, lineterminator="\n").encode("utf-8"),
            "equity": pd.DataFrame(state.equity_curve, columns=["date", "equity"]).to_csv(
                index=False, lineterminator="\n").encode("utf-8"),
        }
    result = {}
    for name, rows, fields in (
        ("trades", state.trades, ("date", "symbol", "hm", "side", "shares", "price", "reason")),
        ("equity", state.equity_curve, ("date", "cash", "holdings", "equity")),
    ):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        result[name] = stream.getvalue().encode("utf-8")
    return result


def capture_case(book: str, engine: str, output_dir: Path, *, explicit_false: bool = False):
    state = run_case(book, engine, explicit_false=explicit_false)
    trades = [row for row in state.trades if row["side"].upper() in ("BUY", "SELL")]
    assert any(row["side"].upper() == "BUY" for row in trades), (book, engine, "no BUY")
    assert any(row["side"].upper() == "SELL" for row in trades), (book, engine, "no SELL")
    with contextlib.redirect_stdout(io.StringIO()):
        if book == "version7":
            v7.write_run_artifacts(state, output_dir)
        else:
            write_run_artifacts(output_dir, state, "Frozen OFF byte baseline", "")
    writer_bytes = {name: (output_dir / filename).read_bytes() for name, filename in (
        ("trades", "trades.csv"), ("equity", "daily_equity.csv"))}
    library_bytes = _library_bytes(state, book)
    # Assert canonical first in the caller. Raw hashes (including writer/library
    # equality) are then checked only on the recorded pandas major.minor.
    for blob in writer_bytes.values():
        assert not blob.startswith(b"\xef\xbb\xbf") and b"\0" not in blob
    positions = {code: ([asdict(pos) for pos in value] if isinstance(value, list)
                        else asdict(value)) for code, value in state.positions.items()}
    structured = {
        "fills": trades, "cash": state.cash, "positions": positions,
        "equity_curve": state.equity_curve,
    }
    if book != "version7":
        # OFF stats are frozen too: adding metadata to SimState is observable.
        structured["stats"] = state.stats
    return {
        "sha256_csv_bytes": {name: _hash(blob) for name, blob in writer_bytes.items()},
        "library_sha256_csv_bytes": {name: _hash(blob) for name, blob in library_bytes.items()},
        "canonical_csv": {name: canonical_csv(blob) for name, blob in writer_bytes.items()},
        "library_canonical_csv": {name: canonical_csv(blob) for name, blob in library_bytes.items()},
        "fill_counts": {side: sum(row["side"].upper() == side for row in trades)
                        for side in ("BUY", "SELL")},
        "structured": json.loads(json.dumps(structured, default=str)),
    }


def capture_matrix(output_dir: Path, *, explicit_false: bool = False):
    assert set(BOOK_NAMES) == set(BOOKS), "Update coverage explicitly when BOOKS changes"
    assert len(BOOK_NAMES) == 19 and len(CASES) == 39
    return {f"{book}/{engine}": capture_case(book, engine, output_dir / book / engine,
                                            explicit_false=explicit_false)
            for book, engine in CASES}


def post205_expected_case(book: str, frozen_case: dict) -> dict:
    """Require #205's quota echo while preserving every eff77f3 field/hash.

    The frozen inputs explicitly pass daily_quota=1M to simulate (including
    topk); CLI money-mode default resolution does not participate. Only the
    shared engines added this stats key. v7's entire snapshot stays unchanged.
    Build an expected copy instead of dropping metadata from the actual state,
    so a missing/wrong quota or any other new stats key still fails comparison.
    """
    if book == "version7":
        return frozen_case
    structured = frozen_case["structured"]
    stats = structured["stats"]
    assert "daily_quota" not in stats, "The original eff77f3 golden must remain unchanged"
    return {
        **frozen_case,
        "structured": {**structured, "stats": {**stats, "daily_quota": 1_000_000.0}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Compare historical cases plus the S8 overlay")
    mode.add_argument("--record-s8", action="store_true", help="Record only the 12 corrected S8 cases")
    args = parser.parse_args()
    if args.record_s8:
        if S8_GOLDEN.exists():
            parser.error("The S8 correction overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("S8 correction recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="s8-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in S8_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
        payload = {
            "rule_revision": S8_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(S8_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        S8_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {S8_GOLDEN}: 12 corrected cases / 24 production CSV hashes")
        return
    if not args.check:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if head != SOURCE or GOLDEN.exists():
            parser.error("Generation requires original eff77f3 HEAD and an absent golden; use --check")
    with tempfile.TemporaryDirectory(prefix="off-byte-baseline-") as temp:
        cases = capture_matrix(Path(temp))
    if args.check:
        skipped = set()
        for book, engine in CASES:
            actual = cases[f"{book}/{engine}"]
            expected, canonical_expected, recorded_pandas = expected_case(book, engine)
            assert_case_canonical(book, actual, expected, canonical_expected)
            reason = byte_skip_reason(recorded_pandas)
            if reason:
                skipped.add(reason)
            else:
                assert_case_bytes(actual, expected)
        for reason in sorted(skipped):
            print(f"SKIP: {reason}")
        if not skipped:
            print("PASS: 78 production CSV hashes + library hashes (raw bytes)")
        print(f"PASS: 27 unchanged + 12 corrected canonical CSV/account cases; pandas={pd.__version__}")
        return
    for case in cases.values():
        assert case["sha256_csv_bytes"] == case["library_sha256_csv_bytes"], "writer/library mismatch"
    payload = {
        "source": SOURCE, "books": list(BOOK_NAMES),
        "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                 "platform": sys.platform},
        "writer_contract": "Unmodified writer bytes: shared LF (Linux); v7 CRLF; no float override",
        "cases": cases,
    }
    GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {GOLDEN}: 39 cases / 78 production CSV hashes")


if __name__ == "__main__":
    main()
