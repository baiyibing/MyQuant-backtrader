#!/usr/bin/env python3
"""Synthetic microbench: naive .loc / index<day vs day_bar_and_prev_closes.

No lake / market data required. Compares per-lookup cost for the daily sell /
chase / pool quote pattern (day row + prior closes).

Usage:
    python scripts/research/bench_daily_sell_index.py
    python scripts/research/bench_daily_sell_index.py --codes 40 --days 240 --reps 500
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backtest.research.csv_common import day_bar_and_prev_closes  # noqa: E402


def _synth_bars(n_codes: int, n_days: int) -> dict[str, pd.DataFrame]:
    idx = pd.bdate_range("2024-01-02", periods=n_days)
    bars: dict[str, pd.DataFrame] = {}
    for i in range(n_codes):
        code = f"{600000 + i:06d}.SH"
        close = 10.0 + (i % 7) * 0.1
        bars[code] = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.05,
                "low": close - 0.05,
                "close": close + (i % 3) * 0.01,
            },
            index=idx,
        )
    return bars


def _naive_lookup(df: pd.DataFrame, day):
    if day not in df.index:
        return None
    prev = df.loc[df.index < day]
    if prev.empty:
        return None
    row = df.loc[day]
    closes = prev["close"].astype(float).tolist()
    return float(row["open"]), float(row["high"]), float(row["low"]), float(
        row["close"]
    ), closes


def _fast_lookup(df: pd.DataFrame, day):
    got = day_bar_and_prev_closes(df, day)
    if got is None:
        return None
    row, closes = got
    return float(row["open"]), float(row["high"]), float(row["low"]), float(
        row["close"]
    ), closes


def _run_all(bars, days, lookup) -> list:
    out = []
    for day in days:
        for df in bars.values():
            out.append(lookup(df, day))
    return out


def _time_call(fn, args, reps: int) -> float:
    fn(*args)
    t0 = time.perf_counter()
    for _ in range(reps):
        fn(*args)
    return time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codes", type=int, default=40)
    ap.add_argument("--days", type=int, default=240)
    ap.add_argument("--reps", type=int, default=40)
    args = ap.parse_args()

    bars = _synth_bars(args.codes, args.days)
    calendar = list(next(iter(bars.values())).index)
    # Sample every ~5th day mid-range (always has prior bars).
    sample_days = calendar[max(1, len(calendar) // 10) :: 5]
    if not sample_days:
        sample_days = calendar[1:]

    naive_v = _run_all(bars, sample_days, _naive_lookup)
    fast_v = _run_all(bars, sample_days, _fast_lookup)
    if naive_v != fast_v:
        mismatches = sum(1 for a, b in zip(naive_v, fast_v) if a != b)
        print(f"MISMATCH count={mismatches} / {len(naive_v)}")
        for a, b in zip(naive_v, fast_v):
            if a != b:
                print(" naive", a)
                print(" fast ", b)
                break
        return 1

    naive_s = _time_call(_run_all, (bars, sample_days, _naive_lookup), args.reps)
    fast_s = _time_call(_run_all, (bars, sample_days, _fast_lookup), args.reps)
    n_lookups = len(sample_days) * args.codes
    print(
        f"naive   codes={args.codes} bar_days={args.days} "
        f"sample_days={len(sample_days)} lookups/rep={n_lookups} "
        f"reps={args.reps}  total={naive_s:.4f}s  "
        f"per_rep={naive_s / args.reps * 1e3:.2f}ms"
    )
    print(
        f"fast    codes={args.codes} bar_days={args.days} "
        f"sample_days={len(sample_days)} lookups/rep={n_lookups} "
        f"reps={args.reps}  total={fast_s:.4f}s  "
        f"per_rep={fast_s / args.reps * 1e3:.2f}ms"
    )
    if fast_s > 0:
        print(f"speedup naive/fast = {naive_s / fast_s:.2f}x")
    print(f"parity_lookups = {len(naive_v)} (match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
