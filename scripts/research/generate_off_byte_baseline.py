"""Frozen, data-free OFF matrix captured before X-01 at eff77f3.

The production writers are called unchanged. Their bytes are never normalized:
the shared pandas writer uses Linux LF and the standalone v7 csv writer CRLF.
The independent library serialization explicitly pins those same line endings.
Run this script with --check after implementation; generation refuses another
HEAD or an existing golden, so updating a baseline cannot hide a regression.
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
    # This compares raw bytes, not parsed tables or reformatted CSV.
    assert writer_bytes == library_bytes, (book, engine, "writer/library mismatch")
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare to the immutable golden")
    args = parser.parse_args()
    if not args.check:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if head != SOURCE or GOLDEN.exists():
            parser.error("Generation requires original eff77f3 HEAD and an absent golden; use --check")
    with tempfile.TemporaryDirectory(prefix="off-byte-baseline-") as temp:
        cases = capture_matrix(Path(temp))
    if args.check:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        assert expected["source"] == SOURCE
        assert cases == expected["cases"]
        print(f"PASS: 39 cases / 78 production CSV hashes; pandas={pd.__version__}")
        return
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
