#!/usr/bin/env python3
"""Synthetic microbench for csv_minute_backtest.scan_held_day.

No lake / market data required. Compares Python reference vs optional numba
trail path when numba is installed.

Usage:
    python scripts/research/bench_scan_held_day.py
    python scripts/research/bench_scan_held_day.py --bars 240 --reps 2000
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backtest.research import csv_minute_backtest as sim  # noqa: E402


def _synth(n: int, *, seed: int = 0):
    rng = np.random.default_rng(seed)
    # Random walk around 10.0; mostly no-exit so the loop runs full length.
    noise = rng.normal(0.0, 0.01, size=n)
    close = 10.0 + np.cumsum(noise)
    open_ = close + rng.normal(0.0, 0.005, size=n)
    high = np.maximum(open_, close) + rng.random(n) * 0.01
    hm = np.arange(9 * 60 + 30, 9 * 60 + 30 + n, dtype=np.int64)
    # skip lunch gap visually; values only need to be monotonic-ish for peak_gap
    return (
        open_.astype(np.float64),
        high.astype(np.float64),
        close.astype(np.float64),
        hm,
    )


def _time_call(fn, args, kwargs, reps: int) -> float:
    # warmup
    fn(*args, **kwargs)
    t0 = time.perf_counter()
    for _ in range(reps):
        fn(*args, **kwargs)
    return time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", type=int, default=240)
    ap.add_argument("--reps", type=int, default=1000)
    args = ap.parse_args()

    o, h, c, hm = _synth(args.bars)
    kwargs = dict(
        cost=10.0,
        peak=10.0,
        n_days=2,
        can_sell=True,
        stop_pct=0.06,
        profit_base=0.01,
        trail_ratio=0.50,
        hm=hm,
        peak_hm=-1,
        peak_gap_min=15,
        force_sell_hm=None,
    )

    py_s = _time_call(sim.scan_held_day_python, (o, h, c), kwargs, args.reps)
    print(
        f"python  bars={args.bars} reps={args.reps}  "
        f"total={py_s:.4f}s  per_call={py_s / args.reps * 1e6:.1f}µs"
    )

    if not getattr(sim, "_NUMBA_SCAN_AVAILABLE", False):
        print("numba   SKIP (numba not installed / import failed)")
        return 0

    # Force numba path; trail-only kwargs already have no callables.
    nb_kwargs = dict(kwargs, use_numba=True)
    # include compile in a separate line
    t_compile0 = time.perf_counter()
    sim.scan_held_day(o, h, c, **nb_kwargs)
    compile_s = time.perf_counter() - t_compile0
    nb_s = _time_call(sim.scan_held_day, (o, h, c), nb_kwargs, args.reps)
    print(
        f"numba   bars={args.bars} reps={args.reps}  "
        f"total={nb_s:.4f}s  per_call={nb_s / args.reps * 1e6:.1f}µs  "
        f"(first_call_incl_compile={compile_s:.4f}s)"
    )
    if nb_s > 0:
        print(f"speedup python/numba = {py_s / nb_s:.2f}x")
    print(f"env CSV_SCAN_HELD_DAY_BACKEND={os.environ.get('CSV_SCAN_HELD_DAY_BACKEND', '')!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
