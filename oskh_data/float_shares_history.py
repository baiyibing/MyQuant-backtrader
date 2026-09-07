#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
.. deprecated:: 2026-05-30

Replaced by ``oskh_data/free_float_shares.py`` which reads freeFloatCapital +
circulating_capital directly from miniQMT ``Capital`` financial table (historical
quarterly data, no akshare dependency). This module is retained for the
``--source snapshot`` fallback only; remove after full migration to
free_float_shares.parquet.

Original doc: Backfill float_shares history parquet. Sources: 1) snapshot 2) akshare.
"""

import argparse
import os

from common.infra.data_root import resolve_parquet_container, resolve_source_parquet
import sys
from pathlib import Path
from typing import Any, List, cast

import pandas as pd

from oskh_data.pandas_typing import normalize_timestamp

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

DEFAULT_SNAPSHOT_PATH = str(resolve_source_parquet("float_shares.parquet"))
DEFAULT_HISTORY_PATH = str(resolve_parquet_container() / "float_shares_history.parquet")


def business_days(start_date: str, end_date: str) -> List[pd.Timestamp]:
    return list(pd.bdate_range(pd.Timestamp(start_date), pd.Timestamp(end_date)))


def build_snapshot_backfill(snapshot_df: pd.DataFrame, dates: List[pd.Timestamp]) -> pd.DataFrame:
    base = snapshot_df[["stock_code", "FloatVolume", "TotalVolume", "name"]].copy()
    frames = []
    for d in dates:
        day_df = base.copy()
        day_df["date"] = d.normalize()
        frames.append(day_df)
    if not frames:
        return pd.DataFrame(columns=cast(Any, ["date", "stock_code", "FloatVolume", "TotalVolume", "name"]))
    out = pd.concat(frames, ignore_index=True)
    return pd.DataFrame(out[["date", "stock_code", "FloatVolume", "TotalVolume", "name"]])


def merge_history(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        merged = incoming.copy()
    else:
        merged = pd.concat([existing, incoming], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"]).dt.normalize()
    merged = merged.drop_duplicates(subset=["date", "stock_code"], keep="last")
    merged = merged.sort_values(["stock_code", "date"]).reset_index(drop=True)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill float_shares history parquet (deprecated; use free_float_shares.py)"
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--snapshot-path", default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--history-output", default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--replace", action="store_true", help="replace output instead of merge")
    parser.add_argument("--max-stocks", type=int, default=0, help="limit to first N stocks (0=all)")
    parser.add_argument("--codes", default=None, help="comma-separated stock codes")
    args = parser.parse_args()

    start_ts = normalize_timestamp(pd.Timestamp(args.start_date))
    end_ts = normalize_timestamp(pd.Timestamp(args.end_date))
    if end_ts < start_ts:
        raise ValueError("end-date must be >= start-date")

    snapshot_df = pd.read_parquet(args.snapshot_path)
    snapshot_df = snapshot_df.dropna(subset=["stock_code"]).copy()

    if args.codes:
        selected_codes = [c.strip().upper() for c in args.codes.split(",") if c.strip()]
        snapshot_df = pd.DataFrame(
            snapshot_df.loc[snapshot_df["stock_code"].isin(selected_codes)]
        )

    if args.max_stocks and args.max_stocks > 0:
        snapshot_df = pd.DataFrame(snapshot_df.head(args.max_stocks))

    incoming = build_snapshot_backfill(snapshot_df, business_days(args.start_date, args.end_date))

    if incoming.empty:
        print("[ERROR] no rows generated")
        sys.exit(1)

    if args.replace or (not os.path.exists(args.history_output)):
        merged = incoming
    else:
        existing = pd.read_parquet(args.history_output)
        merged = merge_history(existing, incoming)

    out = Path(args.history_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(str(out), index=False)

    latest_date = normalize_timestamp(pd.to_datetime(merged["date"]).max())
    latest = cast(
        pd.DataFrame,
        merged[merged["date"] == latest_date][["stock_code", "FloatVolume", "TotalVolume", "name"]],
    ).copy()
    latest["updated_at"] = pd.Timestamp.now().isoformat()
    latest = latest.sort_values(by="stock_code").reset_index(drop=True)  # pyright: ignore[reportCallIssue]
    latest.to_parquet(args.snapshot_path, index=False)

    print(f"source: snapshot")
    print(f"rows_incoming: {len(incoming)}")
    print(f"rows_history: {len(merged)}")
    print(f"date_range: {pd.to_datetime(merged['date']).min().date()} ~ {latest_date.date()}")
    print(f"saved_history: {args.history_output}")
    print(f"saved_snapshot: {args.snapshot_path}")


if __name__ == "__main__":
    main()
