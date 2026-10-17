#!/usr/bin/env python3
"""Strategy 13 A signals, observed at D close and written for next session T.

Raw daily prices/volumes and point-in-time float shares. No future-return
selection, theme, regulatory-list or B-class approximation.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.csv_pool import is_repo_stock_pool
from backtest.research.market_layer import limit_pct
from common.infra.data_root import resolve_parquet_container, resolve_period_root
from oskh_data.symbol_format import to_canonical_symbol
from scripts.data.export_strategy9_pool import write_strategy9_pool

VOLUME_RATIO = 1.5
BREAKOUT_DAYS = 60
TURNOVER = 0.03
FLOAT_MV_MIN = 3e9
FLOAT_MV_MAX = 30e9
AMOUNT_MIN = 5e7
MIN_LISTED_BARS = 60
CHIP_CONCENTRATION = 0.20


def chip_single_peak(frame, code):
    """90% cost band concentration and price above the distribution's mode."""
    from oskh_factors.chip.core import adapt_columns, daily_chip_distribution
    from qlib_cost.cyq import ChipFactor
    dist = daily_chip_distribution(adapt_columns(frame, stock_code=code,
                                                 as_of_date=frame.index[-1]))
    cf = ChipFactor(float(frame.close.iloc[-1]), dist)
    low, high = cf.get_cost(0.05), cf.get_cost(0.95)
    concentration = (high - low) / (high + low) if high + low > 0 else np.inf
    return concentration <= CHIP_CONCENTRATION and frame.close.iloc[-1] > float(dist.idxmax())


def signal_mask(frame, code, *, breakout_days=BREAKOUT_DAYS,
                volume_ratio=VOLUME_RATIO, chip=False):
    """All rolling windows end at D; volume/high references exclude D."""
    if breakout_days < 1 or not np.isfinite(volume_ratio) or volume_ratio <= 0:
        raise ValueError("breakout_days and volume_ratio must be positive")
    required = {"open", "high", "close", "volume", "amount", "float_shares", "is_st"}
    if not required <= set(frame):
        raise ValueError(f"missing signal inputs: {sorted(required - set(frame))}")
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError("daily sessions must be sorted and unique")
    c, v = frame.close, frame.volume
    ma = {n: c.rolling(n).mean() for n in (5, 10, 20, 60, 120)}
    band = limit_pct(code)
    if band is None:
        raise ValueError(f"unknown board: {code}")
    # Match the research engine's near-limit filter (9.5/19.5/29.5%).
    mask = ((v >= volume_ratio * v.shift().rolling(20).mean())
            & (c > frame.open)
            & ((c > frame.high.shift().rolling(breakout_days).max())
               | (c > pd.concat([ma[60], ma[120]], axis=1).max(axis=1, skipna=False)))
            & (ma[5] > ma[10]) & (ma[10] > ma[20])
            & (ma[5] > ma[5].shift()) & (ma[10] > ma[10].shift())
            & (ma[20] > ma[20].shift())
            & (frame.float_shares > 0) & (v / frame.float_shares > TURNOVER)
            & ((c / c.shift() - 1) < band - 0.005)
            & (c * frame.float_shares).between(FLOAT_MV_MIN, FLOAT_MV_MAX)
            & (frame.amount.rolling(20).mean() >= AMOUNT_MIN)
            & frame.is_st.eq(False)
            & (np.arange(len(frame)) + 1 >= MIN_LISTED_BARS))
    if chip:
        for day in mask.index[mask]:
            mask.loc[day] = chip_single_peak(frame.loc[:day], code)
    return mask.fillna(False)


def attach_float_history(frame, history, code):
    """Backward asof only; no snapshot backfill or future shares."""
    h = history.loc[history.stock_code == code, ["date", "FloatVolume"]].copy()
    h["date"] = pd.to_datetime(h.date).dt.normalize()
    if h.date.duplicated().any():
        raise ValueError(f"duplicate float-share dates for {code}")
    left = frame.rename_axis("date").reset_index()
    return pd.merge_asof(left, h.sort_values("date"), on="date", direction="backward").set_index("date").rename(columns={"FloatVolume": "float_shares"})


def scan_frames(frames, start, end, **kwargs):
    days = {}
    for code, frame in sorted(frames.items()):
        signal = signal_mask(frame, code, **kwargs)
        # D close cannot buy D open or D 14:55. Use next observed trading bar.
        for i in np.flatnonzero(signal.to_numpy()):
            if i + 1 < len(frame):
                t = frame.index[i + 1].strftime("%Y%m%d")
                if start <= t <= end:
                    days.setdefault(t, []).append(code)
    return days


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--pool-dir", type=Path, required=True, help="explicit exports/ destination; refuses stock_pool/")
    ap.add_argument("--breakout-days", type=int, default=BREAKOUT_DAYS)
    ap.add_argument("--volume-ratio", type=float, default=VOLUME_RATIO)
    ap.add_argument("--chip-single-peak", action="store_true", default=False)
    args = ap.parse_args(argv)
    if is_repo_stock_pool(args.pool_dir):
        raise SystemExit("refusing stock_pool/")
    if pd.Timestamp(args.end) < pd.Timestamp(args.start):
        raise ValueError("end precedes start")
    root = resolve_period_root("1d") / "dividend_type=none"
    if not root.is_dir():
        raise FileNotFoundError(root)
    history = pd.read_parquet(resolve_parquet_container() / "float_shares_history.parquet")
    history["stock_code"] = history.stock_code.map(to_canonical_symbol)
    from backtest.research.st_status import membership_from_frame
    # Non-ST is a required prefilter, so a missing vendor table is an error.
    st = membership_from_frame(pd.read_parquet(resolve_parquet_container() / "vendor_wind_st_status/st_daily.parquet"))
    frames = {}
    for path in sorted(root.glob("symbol=*/data.parquet")):
        code = to_canonical_symbol(path.parent.name.removeprefix("symbol="))
        if limit_pct(code) is None:
            continue
        f = pd.read_parquet(path)
        f.index = pd.to_datetime(f.pop("time"), unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
        f = f.loc[f.index <= pd.Timestamp(args.end)].sort_index()
        if f.index.has_duplicates:
            raise ValueError(f"duplicate daily bars: {code}")
        f = attach_float_history(f, history, code)
        f["is_st"] = [code in st.get(d.strftime("%Y%m%d"), ()) for d in f.index]
        frames[code] = f
    if not frames:
        raise ValueError(f"no daily partitions under {root}")
    days = scan_frames(frames, args.start, args.end,
                       breakout_days=args.breakout_days, volume_ratio=args.volume_ratio,
                       chip=args.chip_single_peak)
    written = write_strategy9_pool(days, args.pool_dir)
    print(f"beidou: {len(written)} day files, {sum(map(len, days.values()))} signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
