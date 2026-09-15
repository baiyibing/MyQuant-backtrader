#!/usr/bin/env python3
"""Profile the real csv_minute_backtest.simulate orchestration path.

Synthetic only: no F lake or cache is read.  Timings include multi-day,
multi-code and (version8) multi-lot holdings.

Usage:
    python scripts/research/bench_minute_simulate_hotpath.py
    CSV_SCAN_HELD_DAY_BACKEND=numba python scripts/research/bench_minute_simulate_hotpath.py \
        --days 40 --codes 24 --lots-days 12 --reps 5
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backtest.research import csv_minute_backtest as sim  # noqa: E402


def _hm_values(n: int) -> np.ndarray:
    morning = np.arange(9 * 60 + 30, 11 * 60 + 30)
    afternoon = np.arange(13 * 60, 15 * 60)
    session = np.concatenate((morning, afternoon))
    if n > len(session):
        raise ValueError(f"--minutes must be <= {len(session)}")
    return session[:n]


def _synthetic_inputs(
    days: int, codes: int, minutes: int, lots_days: int
):
    calendar = pd.bdate_range("2025-01-02", periods=days)
    hm = _hm_values(minutes)
    minute_bars: dict[str, pd.DataFrame] = {}
    daily_bars: dict[str, pd.DataFrame] = {}
    names: dict[str, str] = {}
    code_list = [f"{600000 + i:06d}.SH" for i in range(codes)]

    for code_i, code in enumerate(code_list):
        base = 10.0 + code_i * 0.01
        daily_close = base * (1.0 + np.arange(days) * 0.00005)
        daily_bars[code] = pd.DataFrame(
            {
                "open": daily_close,
                "high": daily_close * 1.001,
                "low": daily_close * 0.999,
                "close": daily_close,
            },
            index=calendar,
        )
        frames = []
        for day_i, day in enumerate(calendar):
            close = base * (1.0 + day_i * 0.00005) + np.arange(minutes) * 1e-7
            frames.append(
                pd.DataFrame(
                    {
                        "ymd": day.strftime("%Y%m%d"),
                        "hm": hm,
                        "open": close,
                        "high": close + 1e-6,
                        "low": close - 1e-6,
                        "close": close,
                    }
                )
            )
        minute_bars[code] = pd.concat(frames, ignore_index=True)
        names[code] = f"SYNTH-{code_i}"

    buy_days = calendar[1 : min(days, lots_days + 1)]
    pool_days = {day.strftime("%Y%m%d"): list(code_list) for day in buy_days}
    return minute_bars, daily_bars, pool_days, names, calendar


@contextmanager
def _timed_functions():
    totals: dict[str, float] = defaultdict(float)
    calls: dict[str, int] = defaultdict(int)
    originals = {}
    targets = {
        "day_slice": "_slice_day",
        "prev_close_prep": "_previous_rows",
        "sell_scan": "scan_held_day",
        "chase": "run_chase_due_day",
        "pool_buy": "run_pool_buys_day",
        "ledger_mark": "append_equity_and_eod_marks",
    }
    for label, name in targets.items():
        original = getattr(sim, name)
        originals[name] = original

        def wrapper(*args, _fn=original, _label=label, **kwargs):
            t0 = time.perf_counter()
            try:
                return _fn(*args, **kwargs)
            finally:
                totals[_label] += time.perf_counter() - t0
                calls[_label] += 1

        setattr(sim, name, wrapper)
    try:
        yield totals, calls
    finally:
        for name, original in originals.items():
            setattr(sim, name, original)


def _backend_report() -> str:
    requested = (
        os.environ.get("CSV_SCAN_HELD_DAY_BACKEND") or "python"
    ).strip().lower()
    reasons = ["simulate passes reserve_state"]
    reasons.append("version8 supplies take_profit callable")
    if requested not in {"numba", "jit"}:
        reasons.insert(0, f"requested backend is {requested!r}")
    elif not sim._NUMBA_SCAN_AVAILABLE:
        reasons.insert(0, "numba is unavailable")
    return "python (" + "; ".join(reasons) + ")"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--codes", type=int, default=16)
    ap.add_argument("--minutes", type=int, default=240)
    ap.add_argument("--lots-days", type=int, default=10)
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()
    if min(args.days, args.codes, args.minutes, args.lots_days, args.reps) <= 0:
        ap.error("all numeric arguments must be positive")

    inputs = _synthetic_inputs(args.days, args.codes, args.minutes, args.lots_days)
    minute_bars, daily_bars, pool_days, names, calendar = inputs
    kwargs = dict(
        start=calendar[0].strftime("%Y%m%d"),
        end=calendar[-1].strftime("%Y%m%d"),
        strategy="version8",
        total_cash=1e12,
        daily_quota=1e9,
        pool_names=names,
    )

    # Warm pandas paths outside measurement. The returned state is discarded.
    sim.simulate(minute_bars, daily_bars, pool_days, **kwargs)
    totals_all: dict[str, float] = defaultdict(float)
    calls_all: dict[str, int] = defaultdict(int)
    elapsed = 0.0
    last_state = None
    for _ in range(args.reps):
        with _timed_functions() as (totals, calls):
            t0 = time.perf_counter()
            last_state = sim.simulate(minute_bars, daily_bars, pool_days, **kwargs)
            elapsed += time.perf_counter() - t0
        for key, value in totals.items():
            totals_all[key] += value
        for key, value in calls.items():
            calls_all[key] += value

    assert last_state is not None
    max_lots = max((len(v) for v in last_state.positions.values()), default=0)
    print("minute simulate hotpath (synthetic; real simulate(); no lake)")
    print(
        f"scenario days={args.days} codes={args.codes} minutes/day={args.minutes} "
        f"pool_days={len(pool_days)} reps={args.reps} max_lots/code={max_lots}"
    )
    print(f"scan backend: {_backend_report()}")
    print(f"simulate total: {elapsed:.4f}s  per_run={elapsed / args.reps * 1e3:.2f}ms")
    print("top-level phases (exclusive of each other except Python call overhead):")
    top = ("sell_scan", "chase", "pool_buy", "ledger_mark")
    for label in top:
        value = totals_all[label]
        print(
            f"  {label:16s} {value:.4f}s  "
            f"{value / elapsed * 100:6.2f}%  calls={calls_all[label]}"
        )
    remainder = elapsed - sum(totals_all[label] for label in top)
    print(f"  orchestration    {remainder:.4f}s  {remainder / elapsed * 100:6.2f}%")
    print("nested prep (already included in sell/chase/pool above):")
    for label in ("day_slice", "prev_close_prep"):
        value = totals_all[label]
        print(
            f"  {label:16s} {value:.4f}s  "
            f"{value / elapsed * 100:6.2f}%  calls={calls_all[label]}"
        )
    print(
        f"outcome positions={sum(len(v) for v in last_state.positions.values())} "
        f"buys={last_state.stats['buys']} trades={len(last_state.trades)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
