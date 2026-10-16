#!/usr/bin/env python3
"""Strategy 9 (底量超顶量): post-signal peak gain and max drawdown.

Scans main-board daily (front adj) with default s9 buy rules, then for each
stock's earliest signal in ``[--start, --end]`` reports:

- peak high vs signal close (gain_pct)
- max peak-to-trough drawdown **before** the peak day
  (running high watermark vs low on ``[signal, peak_date)``)

Never writes ``stock_pool/``. Optional pool CSVs under ``--pool-dir``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.bottom_vol_over_top import (  # noqa: E402
    MIN_LISTED_BARS,
    MIN_TOP_LEAD,
    R_MIN,
    evaluate_at,
    resolve_top_lead,
    resolve_vol_ratio,
)
from backtest.research.st_status import drop_st_names  # noqa: E402
from common.infra.data_root import resolve_period_root  # noqa: E402
from scripts.data.export_strategy9_pool import (  # noqa: E402
    list_main_board_from_lake,
    load_daily_ohlcv,
    warmup_start,
    write_strategy9_pool,
)


def _bare(code: str) -> str:
    return str(code).split(".", 1)[0]


def _ymd(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y%m%d")


def post_signal_max_drawdown(
    high: np.ndarray,
    low: np.ndarray,
    index: pd.DatetimeIndex,
) -> tuple[float, Optional[str], float, float]:
    """Running-peak(high) vs low; return (dd_pct, trough_ymd, peak_at_dd, trough_low).

    ``dd_pct`` is a non-negative percentage (e.g. 12.5 means 12.5% drawdown).
    Callers that want pre-peak MDD must pass only bars before the peak day.
    """
    if len(high) == 0:
        return float("nan"), None, float("nan"), float("nan")
    running_peak = -np.inf
    max_dd = -1.0
    trough_i = 0
    peak_at = float("nan")
    for i in range(len(high)):
        h = float(high[i])
        lo = float(low[i])
        if not np.isfinite(h) or not np.isfinite(lo):
            continue
        if h > running_peak:
            running_peak = h
        if running_peak <= 0 or not np.isfinite(running_peak):
            continue
        dd = (running_peak - lo) / running_peak
        if dd > max_dd:
            max_dd = dd
            trough_i = i
            peak_at = running_peak
    if max_dd < 0:
        return float("nan"), None, float("nan"), float("nan")
    return (
        float(max_dd * 100.0),
        _ymd(index[trough_i]),
        float(peak_at),
        float(low[trough_i]),
    )


def build_signal_rows(
    frames: dict[str, pd.DataFrame],
    start: str,
    end: str,
    *,
    r_min: float,
    top_lead: int,
    turnover_check: bool,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    days: dict[str, list[str]] = {}
    signal_rows: list[dict[str, Any]] = []
    t0 = pd.Timestamp(start)
    t1 = pd.Timestamp(end)
    for code, frame in frames.items():
        for ts in frame.index[(frame.index >= t0) & (frame.index <= t1)]:
            sig = evaluate_at(
                frame,
                ts,
                code=code,
                name="",
                r_min=r_min,
                top_lead=top_lead,
                turnover_check=turnover_check,
            )
            if sig is None:
                continue
            ymd = sig.ymd
            days.setdefault(ymd, []).append(code)
            day = pd.Timestamp(ts).normalize()
            loc = frame.index.get_loc(day)
            i = int(loc.stop - 1) if isinstance(loc, slice) else int(loc)
            signal_close = float(frame["close"].iloc[i])
            after = frame.iloc[i:]
            highs = np.asarray(after["high"].to_numpy(), dtype=np.float64)
            lows = np.asarray(after["low"].to_numpy(), dtype=np.float64)
            peak_high = float(np.nanmax(highs))
            peak_i = int(np.nanargmax(highs))
            peak_ymd = _ymd(after.index[peak_i])
            last_day = _ymd(frame.index[-1])
            gain_pct = (
                (peak_high / signal_close - 1.0) * 100.0
                if signal_close > 0
                else float("nan")
            )
            # 最高日前：不含最高日当天及之后
            if peak_i <= 0:
                max_dd_pct, max_dd_date, dd_peak, dd_low = (
                    0.0,
                    None,
                    float("nan"),
                    float("nan"),
                )
            else:
                max_dd_pct, max_dd_date, dd_peak, dd_low = post_signal_max_drawdown(
                    highs[:peak_i], lows[:peak_i], after.index[:peak_i]
                )
            signal_rows.append(
                {
                    "code": _bare(code),
                    "canonical": code,
                    "signal_date": ymd,
                    "signal_close": round(signal_close, 4),
                    "peak_high": round(peak_high, 4),
                    "peak_date": peak_ymd,
                    "data_end": last_day,
                    "gain_pct": round(gain_pct, 2),
                    "max_dd_pct": (
                        round(max_dd_pct, 2) if np.isfinite(max_dd_pct) else max_dd_pct
                    ),
                    "max_dd_date": max_dd_date,
                    "max_dd_peak": (
                        round(dd_peak, 4) if np.isfinite(dd_peak) else dd_peak
                    ),
                    "max_dd_low": (
                        round(dd_low, 4) if np.isfinite(dd_low) else dd_low
                    ),
                    "ratio": round(float(sig.ratio), 4),
                    "top_ago": int(sig.top_ago),
                    "bottom_ago": int(sig.bottom_ago),
                }
            )
    return days, signal_rows


def per_stock_earliest(signal_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_code: dict[str, list[dict[str, Any]]] = {}
    for r in signal_rows:
        by_code.setdefault(r["code"], []).append(r)
    out: list[dict[str, Any]] = []
    for _code, rows in by_code.items():
        rows_sorted = sorted(rows, key=lambda x: x["signal_date"])
        first = dict(rows_sorted[0])
        best = max(rows, key=lambda x: x["gain_pct"])
        first["n_signals"] = len(rows)
        first["best_gain_pct"] = best["gain_pct"]
        first["best_signal_date"] = best["signal_date"]
        out.append(first)
    out.sort(key=lambda x: (-x["gain_pct"], x["code"]))
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "s9 post-signal peak gain + max drawdown "
            "(earliest signal per code; front daily)"
        )
    )
    ap.add_argument("--start", required=True, help="first signal day YYYYMMDD")
    ap.add_argument("--end", required=True, help="last signal / data day YYYYMMDD")
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=None,
        help="output CSV (default: out/s9_peak_gains_<start>_<end>.csv)",
    )
    ap.add_argument(
        "--pool-dir",
        type=Path,
        default=None,
        help="optional: also write s9 day CSVs here",
    )
    ap.add_argument(
        "--vol-ratio",
        type=resolve_vol_ratio,
        default=R_MIN,
        metavar="{1.2,1.5,2}",
    )
    ap.add_argument(
        "--top-lead",
        type=resolve_top_lead,
        default=MIN_TOP_LEAD,
        metavar="{10,20,30,40}",
    )
    ap.add_argument("--turnover-check", action="store_true", default=False)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv if argv is not None else None)

    out_csv = (
        Path(args.out_csv)
        if args.out_csv is not None
        else REPO_ROOT / "out" / f"s9_peak_gains_{args.start}_{args.end}.csv"
    )

    lake = resolve_period_root("1d") / "dividend_type=front"
    symbols = list_main_board_from_lake(lake)
    load_start = warmup_start(args.start)
    print(f"load {len(symbols)} codes {load_start}..{args.end}", flush=True)
    frames = load_daily_ohlcv(
        symbols, load_start, args.end, root=lake, workers=args.workers
    )
    kept = {
        code: frame for code, frame in frames.items() if len(frame) >= MIN_LISTED_BARS
    }
    print(f"kept {len(kept)} frames", flush=True)

    days, signal_rows = build_signal_rows(
        kept,
        args.start,
        args.end,
        r_min=args.vol_ratio,
        top_lead=args.top_lead,
        turnover_check=args.turnover_check,
    )
    days, st_dropped = drop_st_names(days)
    allowed = {ymd: {_bare(c) for c in codes} for ymd, codes in days.items()}
    signal_rows = [
        r
        for r in signal_rows
        if r["code"] in allowed.get(r["signal_date"], set())
    ]
    print(f"signals {len(signal_rows)} after ST drop {st_dropped}", flush=True)

    if args.pool_dir is not None:
        write_strategy9_pool(days, Path(args.pool_dir))
        print(f"pool -> {args.pool_dir}", flush=True)

    per_stock = per_stock_earliest(signal_rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(per_stock)
    if "code" in frame.columns:
        frame["code"] = frame["code"].astype(str).str.zfill(6)
    frame.to_csv(out_csv, index=False, encoding="utf-8", lineterminator="\n")
    print(f"wrote {len(per_stock)} stocks -> {out_csv}", flush=True)
    for i, r in enumerate(per_stock[:30], 1):
        print(
            f"{i:3d}  {r['code']}  sig={r['signal_date']}  "
            f"gain={r['gain_pct']:+.2f}%@{r['peak_date']}  "
            f"mdd=-{r['max_dd_pct']:.2f}%@{r['max_dd_date']}  "
            f"n={r['n_signals']}",
            flush=True,
        )
    if len(per_stock) > 30:
        print(f"... {len(per_stock) - 30} more in CSV", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
