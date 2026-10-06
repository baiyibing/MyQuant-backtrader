#!/usr/bin/env python3
"""Explicit local-CSV side artifact; never runs a simulation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from backtest.research.csv_analysis_export import load_trades
from backtest.research.metrics_pack import (
    PERIODS_PER_YEAR,
    compute_metrics_pack,
    write_metrics_pack,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--risk-free", type=float, default=0.0)
    parser.add_argument("--periods-per-year", type=int, default=PERIODS_PER_YEAR)
    args = parser.parse_args(argv)
    benchmark = None
    if args.benchmark is not None:
        if not args.benchmark.is_file():
            benchmark_reason = "supplied benchmark file does not exist"
        else:
            benchmark = pd.read_csv(args.benchmark)
    nav = pd.read_csv(args.run_dir / "daily_equity.csv")
    trades = load_trades(args.run_dir) if (args.run_dir / "trades.csv").is_file() else None
    pack = compute_metrics_pack(
        nav,
        trades,
        benchmark=benchmark,
        risk_free=args.risk_free,
        periods_per_year=args.periods_per_year,
    )
    # The legacy loader supplies zero commissions when absent; preserve missingness.
    if trades is not None:
        raw = pd.read_csv(args.run_dir / "trades.csv")
        columns = {str(c).strip().lower(): c for c in raw.columns}
        if "commission" not in columns:
            pack["fee_drag"] = {"status": "unavailable", "reason": "commission column not supplied"}
        elif pd.to_numeric(raw[columns["commission"]], errors="coerce").isna().any():
            pack["fee_drag"] = {"status": "unavailable", "reason": "commission values partially missing or invalid"}
    if args.benchmark is not None and benchmark is None:
        for key in ("benchmark_excess", "beta", "tracking_error"):
            pack[key] = {"status": "unavailable", "reason": benchmark_reason}
    write_metrics_pack(args.out, pack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
