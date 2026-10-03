"""Local synthetic correctness/performance proof; no timing thresholds or real lake.

Run with the repository's configured Python, e.g. bt-ci/bin/python this_file.py.
"""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.research.bar_scan_exit import OhlcBar
from backtest.research.minute_bar_scan_host import (
    _scan_held_decisions, load_scan_bars, scan_held_bars,
)
from backtest.research.minute_true_core_wire import invoke_minute_strategy
from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars


def before_decisions(bars):
    peak = 10.0
    for bar in bars:
        result = invoke_minute_strategy("version1", bar, cost=10, peak=peak,
                                        n_days=1, timing="same_bar")
        peak = result.peak
        yield result


def assert_scan_equivalence():
    bars = [
        OhlcBar(9.7, 9.8, 9.6, 9.75),  # gap-open stop
        OhlcBar(10, 10.1, 9.7, 10),  # intrabar stop touch
        OhlcBar(11, 12, 10.9, 11.8),  # peak ratchet, no fill
        OhlcBar(10.9, 11, 10.8, 10.9),  # drawdown take-profit
    ]
    expected = list(before_decisions(bars))
    assert [x.reason for x in expected] == [
        "stop_loss:gap_open", "stop_loss:touch", "", "profit_take:drawdown:50",
    ]
    assert expected == list(_scan_held_decisions(bars, cost=10, peak=10))
    summary = scan_held_bars(bars, cost=10, peak=10)
    assert (summary.fills, summary.skips) == (3, 1)
    for runner in (before_decisions,
                   lambda series: _scan_held_decisions(series, cost=10, peak=10)):
        try:
            list(runner([OhlcBar(10, 9, 8, 10)]))
        except ValueError as exc:
            assert "inconsistent" in str(exc)
        else:
            raise AssertionError("inconsistent OHLC accepted")


def timed(label, action):
    start = perf_counter()
    result = action()
    seconds = perf_counter() - start
    print(f"{label}: {seconds:.6f} s")
    return result


def bench_lake_window(root):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from backtest.research.ashare_bars import load_minute_from_lake

    folder = root / "symbol=603196_SH"
    folder.mkdir()
    stamps = pd.date_range("2020-01-01", periods=1_000_000, freq="min", tz="UTC")
    table = pa.table({
        "time": stamps.asi8 // 1_000_000,
        **{name: np.full(len(stamps), value) for name, value in
           zip(("open", "high", "low", "close"), (10, 10.1, 9.95, 10.05))},
        "volume": np.ones(len(stamps)),
    })
    path = folder / "data.parquet"
    pq.write_table(table, path, row_group_size=10_000)
    assert pq.read_metadata(path).num_row_groups == 100
    day = stamps[900_000].strftime("%Y%m%d")

    def before_read():
        with redirect_stdout(StringIO()):
            return load_minute_from_lake(["603196.SH"], day, day, workers=1,
                                         lake_root=root)["603196.SH"]

    frame = timed("lake full-file read (1000000 rows, one-day window)", before_read)
    dates = []
    loaded = timed("lake host window read (1000000 rows, one-day window)",
                   lambda: load_scan_bars("603196.SH", day, day, source="lake",
                                         lake_root=root, bar_dates=dates))
    assert len(loaded) == len(frame)
    assert dates == list(frame.index.date)
    for name in ("open", "high", "low", "close"):
        np.testing.assert_array_equal([getattr(bar, name) for bar in loaded], frame[name])


def main():
    assert_scan_equivalence()
    bars = [OhlcBar(10, 10.1, 9.95, 10.05)] * 100_000
    def before_scan():
        fills = sum(result.decision == "fill" for result in before_decisions(bars))
        return fills, len(bars) - fills
    before = timed("scan before-style (100000 bars)", before_scan)
    after = timed("scan optimized (100000 bars)",
                  lambda: scan_held_bars(bars, cost=10, peak=10))
    assert before == (after.fills, after.skips)
    with TemporaryDirectory(prefix="minute-host-bench-") as directory:
        root = Path(directory)
        bench_lake_window(root)
        stamps = pd.date_range("2020-01-01", periods=1_000_000, freq="min")
        calendar = root / "calendars" / "1min.txt"
        calendar.parent.mkdir()
        calendar.write_text("\n".join(stamps.strftime("%Y-%m-%d %H:%M:%S")) + "\n",
                            encoding="utf-8")
        folder = root / "features" / "sh603196"
        folder.mkdir(parents=True)
        offset = 900_000
        for name, value in zip(("open", "high", "low", "close"), (10, 10.1, 9.95, 10.05)):
            values = np.full(1440, value, dtype="<f")
            if name == "close":
                values[50] = np.nan
                values[100] = np.inf
            (folder / f"{name}.1min.bin").write_bytes(
                np.asarray([offset], dtype="<f").tobytes() + values.tobytes())
        day = stamps[offset].date()
        def before_read():
            # Unchanged public path converts the entire calendar and uses a pool.
            with redirect_stdout(StringIO()):
                return load_qlib_bin_1min_bars(["603196.SH"], day, day,
                                             qlib_root=root, workers=1, preload_days=0)["603196.SH"]
        frame = timed("qlib full-calendar datetime path (1000000 stamps)", before_read)
        loaded = timed("qlib optimized window read (1000000 stamps)",
                       lambda: load_scan_bars("603196.SH", day, day,
                                             source="qlib_1min", qlib_root=root))
        assert len(loaded) == len(frame)
        for name in ("open", "high", "close"):
            np.testing.assert_array_equal([getattr(bar, name) for bar in loaded], frame[name])
        assert all(bar.low == float(np.float32(9.95)) for bar in loaded)
    print("correctness assertions passed")


if __name__ == "__main__":
    main()
