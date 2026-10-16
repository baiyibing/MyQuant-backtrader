"""S1.1 read-only scan/open probe. Run with the repository's selected Python.

No runtime cache writes, source mutations, shard grain selection or speed gate.
The OS page cache is not evicted: timings are ordered observations, not cold IO.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import datetime, timedelta
import json
from pathlib import Path
from time import perf_counter

# Support direct script invocation using the shared repository bootstrap.
if __package__ in (None, ""):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_script_bootstrap", Path(__file__).resolve().parents[1] / "_script_bootstrap.py")
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    bootstrap.ensure_repo_on_syspath(__file__)

from backtest.research import ashare_bars as bars
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key


def month_windows(start: str, end: str) -> list[tuple[str, str]]:
    """Full calendar months covering loader parameters, never CLI warmup guesses."""
    first = datetime.strptime(start, "%Y%m%d").date()
    last = datetime.strptime(end, "%Y%m%d").date()
    if first > last:
        raise ValueError("start must be <= end")
    cursor = first.replace(day=1)
    result = []
    while cursor <= last:
        stop = cursor.replace(day=calendar.monthrange(cursor.year, cursor.month)[1])
        result.append((cursor.strftime("%Y%m%d"), stop.strftime("%Y%m%d")))
        cursor = stop + timedelta(days=1)
    return result


def cut_a_counts(start: str, end: str) -> dict:
    """Expected counts for a changed symbol stamp; NOT measured rebuilt files."""
    day = datetime.strptime(end, "%Y%m%d").date()
    # Use a month with an in-month +1 even if the request ends on month end.
    within = day.replace(day=min(day.day, calendar.monthrange(day.year, day.month)[1] - 1))
    boundary = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return {
        label: {"base_end": base.strftime("%Y%m%d"),
                "extended_end": (base + timedelta(days=1)).strftime("%Y%m%d"),
                "expected_rebuilt_shards_per_changed_symbol": len(
                    month_windows(start, (base + timedelta(days=1)).strftime("%Y%m%d")))}
        for label, base in (("same_month_plus_one", within), ("cross_month_plus_one", boundary))
    }


def _stamp(path: Path) -> list[int]:
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns]


def _ratio(numerator: float, denominator: float):
    return numerator / denominator if denominator > 0 else None


def probe(codes, start, end, *, request_codes: int, workers: int = 16,
          open_repeats: int = 20, lake_root=None, source_snapshot=None) -> dict:
    import pandas as pd
    import pyarrow.parquet as pq

    windows = month_windows(start, end)
    wanted = sorted({to_canonical_symbol(str(code)) for code in codes})
    if not wanted or request_codes < len(wanted) or workers < 1 or open_repeats < 1:
        raise ValueError("need sample codes, request_codes >= sample size, and positive workers/repeats")
    identity = bars.minute_cache_identity(windows[0][0], windows[-1][1],
                                          lake_root=lake_root, source_snapshot=source_snapshot)
    root = Path(identity["resolver_identity"])
    paths = {code: root / f"symbol={to_partition_key(code)}" / "data.parquet" for code in wanted}
    # Unlike the runtime loader, a missing requested measurement source is an error.
    before = {code: _stamp(path) for code, path in paths.items()}
    observations = []
    for code, path in paths.items():
        tick = perf_counter()
        for _ in range(open_repeats):
            with pq.ParquetFile(path):
                pass
        open_s = (perf_counter() - tick) / open_repeats
        tick = perf_counter()
        once = bars.read_lake_minute_ohlc(code, root, windows[0][0], windows[-1][1])
        scan_s = perf_counter() - tick
        tick = perf_counter()
        months = [bars.read_lake_minute_ohlc(code, root, a, b) for a, b in windows]
        monthly_s = perf_counter() - tick
        pieces = [frame for frame in months if frame is not None]
        joined = pd.concat(pieces) if pieces else None
        if once is None:
            if joined is not None:
                raise AssertionError("month scan differs from one scan")
        else:
            pd.testing.assert_frame_equal(once, joined)
        observations.append({"code": code, "source_stamp": before[code],
                             "rows": 0 if once is None else len(once),
                             "open_s": open_s, "one_scan_s": scan_s,
                             "per_month_scans_s": monthly_s,
                             "per_month_over_one_scan": _ratio(monthly_s, scan_s),
                             "open_over_one_scan": _ratio(open_s, scan_s)})
    after = {code: _stamp(path) for code, path in paths.items()}
    final_identity = bars.minute_cache_identity(windows[0][0], windows[-1][1],
                                                lake_root=root, source_snapshot=source_snapshot)
    if before != after or identity != final_identity:
        raise RuntimeError("source changed during probe; freeze lake and rerun")
    return {"stage": "S1.1 scaffolding", "identity": identity,
            "loader_request": [start, end], "month_windows": windows,
            "timing_caveat": "ordered reads; OS page cache not evicted; not cold-cache evidence",
            "source_assumption": "frozen source; preserved-metadata mutations require new explicit token",
            "observations": observations, "cut_a_modeled_counts": cut_a_counts(start, end),
            "actual_rebuilt_shards": None,
            "fd_extrapolation": {"request_codes": request_codes, "workers": workers,
                                 "single_symbol_month_total_files": request_codes * len(windows),
                                 "serial_probe_peak_parquet_handles": 1,
                                 "one_handle_per_worker_projection": min(workers, request_codes),
                                 "all_shards_open_projection": request_codes * len(windows)},
            "pending": ["actual same-month and cross-month rebuilt counts on frozen host fixtures",
                        "monolith versus shard write/read timings and grain decision",
                        "same-commit CSV reconciliation and cold/warm budgets before S1"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", nargs="+", required=True, help="explicit sample symbols")
    parser.add_argument("--start", required=True, help="loader start including caller warmup, YYYYMMDD")
    parser.add_argument("--end", required=True)
    parser.add_argument("--request-codes", required=True, type=int, help="full request count for fd projection")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--open-repeats", type=int, default=20)
    parser.add_argument("--source-snapshot")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = probe(args.codes, args.start, args.end, request_codes=args.request_codes,
                   workers=args.workers, open_repeats=args.open_repeats,
                   source_snapshot=args.source_snapshot)
    # Exclusive output: never overwrite a previous evidence run.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
