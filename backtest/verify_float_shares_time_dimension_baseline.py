#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
verify_float_shares_time_dimension_baseline.py

?? float_shares ???????????
1) ????_get_float_shares(code) vs _get_float_shares(code, None)
2) ??????history ?????????
3) ????????? vs ???? ? turnover_rate ????
4) ???????/?? turnover ??? ARC ???????

???
    python backtest/verify_float_shares_time_dimension_baseline.py
    python backtest/verify_float_shares_time_dimension_baseline.py --sample-size 60 --bars 260
    python backtest/verify_float_shares_time_dimension_baseline.py --codes 000001.SZ,000002.SZ --output-json backtest_output/float_shares_time_baseline.json
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

from backtest.chip_algorithm import _get_float_shares, turnover_chip_factors  # noqa: E402

FLOAT_SHARES_PATH = os.path.join(REPO, "stock_data", "float_shares.parquet")
FLOAT_SHARES_HISTORY_PATH = os.path.join(REPO, "stock_data", "float_shares_history.parquet")
DAILY_DIR = os.path.join(REPO, "stock_data", "period=1d", "dividend_type=front")
OUTPUT_DIR = os.path.join(REPO, "backtest_output")


def _safe_quantile(arr: np.ndarray, q: float) -> Optional[float]:
    if arr.size == 0:
        return None
    return float(np.quantile(arr, q))


def _load_daily(code: str, bars: int, start: Optional[str], end: Optional[str]) -> Optional[pd.DataFrame]:
    sym = code.replace(".", "_")
    path = os.path.join(DAILY_DIR, f"symbol={sym}", "data.parquet")
    if not os.path.exists(path):
        return None
    df = pd.read_parquet(path)
    df["dt"] = pd.to_datetime(df["time"], unit="ms")
    if start:
        df = df[df["dt"] >= pd.Timestamp(start)]
    if end:
        df = df[df["dt"] <= pd.Timestamp(end)]
    df = df.sort_values("dt")
    if bars > 0:
        df = df.tail(bars)
    df = df.reset_index(drop=True)
    if df.empty:
        return None
    return df


def _compatibility_check(codes: List[str]) -> Dict[str, float]:
    total = len(codes)
    passed = 0
    for code in codes:
        fs_old = _get_float_shares(code)
        fs_none = _get_float_shares(code, None)
        if abs(fs_old - fs_none) < 1e-6:
            passed += 1
    ratio = (passed / total) if total > 0 else 0.0
    return {"compatibility_passed": passed, "compatibility_total": total, "compatibility_ratio": ratio}


def _history_integrity() -> Dict[str, object]:
    if not os.path.exists(FLOAT_SHARES_HISTORY_PATH):
        return {
            "history_exists": False,
            "history_rows": 0,
            "history_duplicate_keys": None,
            "history_float_shares_nonnull_ratio": None,
            "history_date_min": None,
            "history_date_max": None,
        }

    hist = pd.read_parquet(FLOAT_SHARES_HISTORY_PATH)
    if "date" in hist.columns:
        hist["date"] = pd.to_datetime(hist["date"]).dt.normalize()
    dup = None
    if {"stock_code", "date"}.issubset(hist.columns):
        dup = int(hist.duplicated(["stock_code", "date"]).sum())
    nonnull_ratio = None
    if "float_shares" in hist.columns and len(hist) > 0:
        nonnull_ratio = float(hist["float_shares"].notna().mean())

    date_min = None
    date_max = None
    if "date" in hist.columns and len(hist) > 0:
        date_min = str(hist["date"].min().date())
        date_max = str(hist["date"].max().date())

    return {
        "history_exists": True,
        "history_rows": int(len(hist)),
        "history_duplicate_keys": dup,
        "history_float_shares_nonnull_ratio": nonnull_ratio,
        "history_date_min": date_min,
        "history_date_max": date_max,
    }


def _turnover_and_factor_baseline(
    codes: List[str], bars: int, start: Optional[str], end: Optional[str], window: int
) -> Dict[str, object]:
    abs_diff_all = []
    rel_diff_all = []
    arc_delta_all = []
    scanned_codes = 0
    valid_factor_codes = 0

    for code in codes:
        df = _load_daily(code, bars=bars, start=start, end=end)
        if df is None or len(df) < 2:
            continue

        vol = df["volume"].astype(np.float64).values
        dt = df["dt"]
        static_fs = _get_float_shares(code)
        tr_static = (vol * 100.0) / static_fs

        fs_time = np.array([_get_float_shares(code, d) for d in dt], dtype=np.float64)
        tr_time = (vol * 100.0) / fs_time

        diff = np.abs(tr_static - tr_time)
        abs_diff_all.append(diff)
        safe_denom = np.where(np.abs(tr_static) > 1e-12, np.abs(tr_static), np.nan)
        rel_diff = diff / safe_denom
        rel_diff = rel_diff[~np.isnan(rel_diff)]
        if rel_diff.size > 0:
            rel_diff_all.append(rel_diff)

        scanned_codes += 1

        if len(df) >= window:
            close = df["close"].astype(np.float64).values
            try:
                f_static = turnover_chip_factors(tr_static, close, window=window)
                f_time = turnover_chip_factors(tr_time, close, window=window)
                if not (np.isnan(f_static["arc"]) or np.isnan(f_time["arc"])):
                    arc_delta_all.append(abs(float(f_static["arc"]) - float(f_time["arc"])))
                    valid_factor_codes += 1
            except Exception:
                continue

    abs_concat = np.concatenate(abs_diff_all) if abs_diff_all else np.array([], dtype=np.float64)
    rel_concat = np.concatenate(rel_diff_all) if rel_diff_all else np.array([], dtype=np.float64)
    arc_arr = np.asarray(arc_delta_all, dtype=np.float64) if arc_delta_all else np.array([], dtype=np.float64)

    return {
        "scanned_codes": scanned_codes,
        "turnover_abs_diff_p50": _safe_quantile(abs_concat, 0.50),
        "turnover_abs_diff_p95": _safe_quantile(abs_concat, 0.95),
        "turnover_abs_diff_max": float(abs_concat.max()) if abs_concat.size else None,
        "turnover_rel_diff_p50": _safe_quantile(rel_concat, 0.50),
        "turnover_rel_diff_p95": _safe_quantile(rel_concat, 0.95),
        "turnover_rel_diff_max": float(rel_concat.max()) if rel_concat.size else None,
        "factor_codes": valid_factor_codes,
        "arc_abs_delta_p50": _safe_quantile(arc_arr, 0.50),
        "arc_abs_delta_p95": _safe_quantile(arc_arr, 0.95),
        "arc_abs_delta_max": float(arc_arr.max()) if arc_arr.size else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="float_shares ?????????")
    parser.add_argument("--sample-size", type=int, default=30, help="???????")
    parser.add_argument("--bars", type=int, default=240, help="?????? bars?0=???")
    parser.add_argument("--start", default=None, help="?????YYYY-MM-DD?")
    parser.add_argument("--end", default=None, help="?????YYYY-MM-DD?")
    parser.add_argument("--seed", type=int, default=42, help="??????")
    parser.add_argument("--window", type=int, default=60, help="ARC ????")
    parser.add_argument("--codes", default=None, help="?????????? sample-size?")
    parser.add_argument(
        "--output-json",
        default=os.path.join(OUTPUT_DIR, "float_shares_time_dimension_baseline.json"),
        help="?? JSON ??",
    )
    args = parser.parse_args()

    fs_all = pd.read_parquet(FLOAT_SHARES_PATH)
    all_codes = fs_all["stock_code"].dropna().astype(str).unique().tolist()
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        rng = np.random.RandomState(args.seed)
        n = min(args.sample_size, len(all_codes))
        codes = list(rng.choice(all_codes, size=n, replace=False))

    metrics = {"sample_size": len(codes), "window": int(args.window), "bars": int(args.bars)}
    metrics.update(_compatibility_check(codes))
    metrics.update(_history_integrity())
    metrics.update(
        _turnover_and_factor_baseline(codes, bars=args.bars, start=args.start, end=args.end, window=args.window)
    )

    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("=== float_shares time-dimension baseline ===")
    for k in sorted(metrics.keys()):
        print(f"{k}: {metrics[k]}")
    print(f"saved: {args.output_json}")


if __name__ == "__main__":
    main()
