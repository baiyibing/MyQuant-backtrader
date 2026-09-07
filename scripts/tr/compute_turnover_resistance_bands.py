#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily pipeline: Rust TR cross-section → Parquet → TR Bollinger Bands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if p.name == "scripts").parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._script_bootstrap import ensure_repo_on_syspath

ensure_repo_on_syspath(__file__)

from common.infra.quant_logger import get_logger
from oskh_core.turnover_resist_bridge import compute_turnover_resist
from oskh_data.turnover_resistance_store import (
    DEFAULT_FREE_FLOAT_POLICY,
    DEFAULT_WINDOW,
    TurnoverResistanceStore,
)

_log = get_logger(__name__)

CANONICAL_WINDOW = 1000


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute TR cross-section + TR BB for one trading day")
    parser.add_argument("--date", required=True, help="Trading day YYYYMMDD")
    parser.add_argument(
        "--data-dir",
        default="",
        help="Parquet root for turnover-resist (default: TURNOVER_RESIST_DATA_DIR)",
    )
    parser.add_argument(
        "--parquet-path",
        default="",
        help="Override turnover_resistance_daily.parquet path",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=CANONICAL_WINDOW,
        help="Chip distribution window (default 1000, canonical)",
    )
    parser.add_argument(
        "--free-float-policy",
        default=DEFAULT_FREE_FLOAT_POLICY,
        choices=("warn-zero", "skip", "fail"),
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip Step 1-2 when trade_date already present in store",
    )
    parser.add_argument(
        "--backfill-bands-only",
        action="store_true",
        help="Skip Step 1-2; only compute TR BB for rows missing bands",
    )
    parser.add_argument(
        "--bands-history",
        type=int,
        default=60,
        help="Trading-day history window for TR BB rolling (default 60)",
    )
    parser.add_argument("--bb-period", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.window != CANONICAL_WINDOW:
        _log.warning(
            "non-canonical window requested",
            context={"window": args.window, "canonical": CANONICAL_WINDOW},
        )

    store = TurnoverResistanceStore(args.parquet_path or None)
    trade_date = str(args.date)

    if args.backfill_bands_only:
        stats = store.compute_and_update_bands(
            trade_dates=[trade_date],
            n_history=args.bands_history,
            period=args.bb_period,
            window=args.window,
            only_missing=True,
        )
        print(
            f"[bands-only] {trade_date}: updated_rows={stats['updated_rows']} "
            f"trade_dates={stats['trade_dates']}"
        )
        return 0

    if args.skip_existing and store.has_trade_date(trade_date, window=args.window):
        print(f"[skip-existing] TR cross-section already present for {trade_date}")
    else:
        rows = compute_turnover_resist(
            trade_date,
            data_dir=args.data_dir,
            window=args.window,
            free_float_policy=args.free_float_policy,
        )
        upsert_stats = store.upsert_daily(
            trade_date,
            rows,
            window=args.window,
            source="canonical_rust",
            free_float_policy=args.free_float_policy,
        )
        print(
            f"[upsert] {trade_date}: inserted={upsert_stats['inserted']} "
            f"replaced={upsert_stats['replaced']} total={upsert_stats['total_after']}"
        )

    band_stats = store.compute_and_update_bands(
        trade_dates=[trade_date],
        n_history=args.bands_history,
        period=args.bb_period,
        window=args.window,
    )
    print(
        f"[bands] {trade_date}: updated_rows={band_stats['updated_rows']} "
        f"trade_dates={band_stats['trade_dates']}"
    )

    dist = store.distribution_stats(trade_date, window=args.window)
    if dist:
        print(
            f"[dist] count={int(dist['count'])} p50={dist['p50']:.4f} "
            f"p95={dist['p95']:.4f} |TR|>20={dist['abs_gt_20_pct']:.2f}%"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
