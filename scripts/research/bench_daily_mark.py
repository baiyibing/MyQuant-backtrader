#!/usr/bin/env python3
"""Synthetic microbench for daily equity mark (last_close_mark / cache).

No lake / market data required. Compares naive per-lot pandas lookups vs
per-code cached market_close_mark (the H5 path used by append_equity).

Usage:
    python scripts/research/bench_daily_mark.py
    python scripts/research/bench_daily_mark.py --codes 50 --lots 4 --days 240 --reps 200
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backtest.research.csv_ledger import (  # noqa: E402
    last_close_mark,
    market_close_mark,
)


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
                "close": close,
            },
            index=idx,
        )
    return bars


def _naive_mark_equity(bars, positions, day) -> float:
    eq = 0.0
    for code, lots in positions.items():
        df_c = bars.get(code)
        for cost, shares in lots:
            eq += shares * last_close_mark(df_c, day, cost)
    return eq


def _cached_mark_equity(bars, positions, day) -> float:
    eq = 0.0
    mark_by_code: dict[str, float | None] = {}
    for code, lots in positions.items():
        if code not in mark_by_code:
            mark_by_code[code] = market_close_mark(bars.get(code), day)
        m = mark_by_code[code]
        for cost, shares in lots:
            last = float(cost) if m is None else m
            eq += shares * last
    return eq


def _time_call(fn, args, reps: int) -> float:
    fn(*args)
    t0 = time.perf_counter()
    for _ in range(reps):
        fn(*args)
    return time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codes", type=int, default=40)
    ap.add_argument("--lots", type=int, default=3)
    ap.add_argument("--days", type=int, default=240)
    ap.add_argument("--reps", type=int, default=300)
    args = ap.parse_args()

    bars = _synth_bars(args.codes, args.days)
    day = bars[next(iter(bars))].index[-1]
    # Drop last bar for ~10% of codes to exercise prior-close path.
    codes = list(bars)
    for code in codes[::10]:
        bars[code] = bars[code].iloc[:-1]
    positions = {
        code: [(10.0 + (i % 5), 1000.0) for _ in range(args.lots)]
        for i, code in enumerate(codes)
    }

    naive_v = _naive_mark_equity(bars, positions, day)
    cached_v = _cached_mark_equity(bars, positions, day)
    if abs(naive_v - cached_v) > 1e-9:
        print(f"MISMATCH naive={naive_v} cached={cached_v}")
        return 1

    naive_s = _time_call(_naive_mark_equity, (bars, positions, day), args.reps)
    cached_s = _time_call(_cached_mark_equity, (bars, positions, day), args.reps)
    print(
        f"naive   codes={args.codes} lots/code={args.lots} days={args.days} "
        f"reps={args.reps}  total={naive_s:.4f}s  "
        f"per_call={naive_s / args.reps * 1e3:.2f}ms"
    )
    print(
        f"cached  codes={args.codes} lots/code={args.lots} days={args.days} "
        f"reps={args.reps}  total={cached_s:.4f}s  "
        f"per_call={cached_s / args.reps * 1e3:.2f}ms"
    )
    if cached_s > 0:
        print(f"speedup naive/cached = {naive_s / cached_s:.2f}x")
    print(f"equity_mark_check = {naive_v:.4f} (match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
