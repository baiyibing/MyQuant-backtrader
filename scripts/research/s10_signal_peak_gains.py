#!/usr/bin/env python3
"""Strategy 10 (阻力 / resist_tr_bb_1000): post-signal peak gain and max drawdown.

Mirrors ``s9_signal_peak_gains.py`` metrics, but the name list comes from Source B
TR pool (``export_ta_pool`` / ``resist_tr_bb_1000``), not 底量超顶量.

Signals: either scan with ``--universe-mode lake_tr`` (default host path) or
reuse an existing contract pool via ``--pool-dir``.

For each code's earliest signal in ``[--start, --end]`` (front daily):

- peak high vs signal close (gain_pct)
- max peak-to-trough drawdown **before** the peak day
  (running high vs low on ``[signal, peak_date)``)

Never writes ``stock_pool/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.csv_pool import is_repo_stock_pool  # noqa: E402
from backtest.research.source_b_tr_pool import (  # noqa: E402
    normalize_stock_code,
    scan_tr_days,
    write_tr_pool,
)
from common.infra.data_root import resolve_period_root  # noqa: E402
from scripts.data.export_strategy9_pool import load_daily_ohlcv  # noqa: E402
from scripts.data.export_ta_pool import (  # noqa: E402
    _dates_between,
    _loader_from_store,
    lake_tr_universe_for_day,
    list_lake_symbols,
    lake_universe_on_day,
    resolve_lake_root,
)
from scripts.research.s9_signal_peak_gains import (  # noqa: E402
    _bare,
    _ymd,
    per_stock_earliest,
    post_signal_max_drawdown,
)


def load_pool_days(pool_dir: Path, start: str, end: str) -> dict[str, list[str]]:
    """Read contract day CSVs → ``{YYYYMMDD: [canonical codes]}``."""
    root = Path(pool_dir)
    if is_repo_stock_pool(root):
        raise SystemExit(f"refusing stock_pool/: {root}")
    out: dict[str, list[str]] = {}
    for path in sorted(root.glob("*.csv")):
        ymd = path.stem
        if not (ymd.isdigit() and len(ymd) == 8):
            continue
        if ymd < str(start) or ymd > str(end):
            continue
        codes: list[str] = []
        seen: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            code = normalize_stock_code(raw)
            if not code or code in seen:
                continue
            seen.add(code)
            codes.append(code)
        if codes:
            out[ymd] = codes
    return out


def scan_tr_pool(
    start: str,
    end: str,
    *,
    universe_mode: str,
    store_parquet: Optional[Path],
    lake_root: Optional[Path],
    workers: int,
) -> dict[str, list[str]]:
    loader, _store = _loader_from_store(store_parquet)
    loader(start)  # warm session cache
    lake = resolve_lake_root(lake_root)
    lake_order = list_lake_symbols(lake)
    if universe_mode == "lake_tr":

        def universe_for(ymd: str) -> Sequence[str]:
            return lake_tr_universe_for_day(
                lake_order=lake_order,
                load_cross_section=loader,
                ymd=ymd,
            )

    elif universe_mode == "lake_bar":

        def universe_for(ymd: str) -> Sequence[str]:
            return lake_universe_on_day(
                lake, ymd, workers=workers, symbols=lake_order
            )

    else:
        raise SystemExit(f"unsupported universe-mode: {universe_mode}")

    dates = _dates_between(start, end)
    print(
        f"tr scan {len(dates)} bdays universe={universe_mode} lake={lake}",
        flush=True,
    )
    return scan_tr_days(
        dates,
        load_cross_section=loader,
        universe_for=universe_for,
        fail_closed=True,
    )


def build_signal_rows(
    days: dict[str, list[str]],
    frames: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ymd in sorted(days):
        day = pd.Timestamp(ymd)
        for code in days[ymd]:
            canon = normalize_stock_code(code)
            if not canon:
                continue
            frame = frames.get(canon)
            if frame is None or frame.empty:
                continue
            if day not in frame.index:
                continue
            loc = frame.index.get_loc(day)
            i = int(loc.stop - 1) if isinstance(loc, slice) else int(loc)
            signal_close = float(frame["close"].iloc[i])
            after = frame.iloc[i:]
            highs = np.asarray(after["high"].to_numpy(), dtype=np.float64)
            lows = np.asarray(after["low"].to_numpy(), dtype=np.float64)
            if highs.size == 0 or not np.isfinite(signal_close) or signal_close <= 0:
                continue
            peak_high = float(np.nanmax(highs))
            peak_i = int(np.nanargmax(highs))
            peak_ymd = _ymd(after.index[peak_i])
            last_day = _ymd(frame.index[-1])
            gain_pct = (peak_high / signal_close - 1.0) * 100.0
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
            rows.append(
                {
                    "code": _bare(canon),
                    "canonical": canon,
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
                }
            )
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "s10 / resist_tr_bb_1000 post-signal peak gain + max drawdown "
            "(earliest signal per code; front daily)"
        )
    )
    ap.add_argument("--start", required=True, help="first signal day YYYYMMDD")
    ap.add_argument("--end", required=True, help="last signal / data day YYYYMMDD")
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=None,
        help="output CSV (default: out/s10_peak_gains_<start>_<end>.csv)",
    )
    ap.add_argument(
        "--pool-dir",
        type=Path,
        default=None,
        help=(
            "existing TR contract pool; if omitted, scan resist_tr_bb_1000 "
            "(and optionally write via --write-pool-dir)"
        ),
    )
    ap.add_argument(
        "--write-pool-dir",
        type=Path,
        default=None,
        help="when scanning, also write TR day CSVs here",
    )
    ap.add_argument(
        "--universe-mode",
        choices=("lake_tr", "lake_bar"),
        default="lake_tr",
        help="scan universe when --pool-dir omitted (default: lake_tr)",
    )
    ap.add_argument(
        "--store-parquet",
        type=Path,
        default=None,
        help="optional TurnoverResistanceStore path",
    )
    ap.add_argument(
        "--lake-root",
        type=Path,
        default=None,
        help="override period=1d dividend_type=none root",
    )
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv if argv is not None else None)

    out_csv = (
        Path(args.out_csv)
        if args.out_csv is not None
        else REPO_ROOT / "out" / f"s10_peak_gains_{args.start}_{args.end}.csv"
    )

    if args.pool_dir is not None:
        if is_repo_stock_pool(args.pool_dir):
            raise SystemExit(f"refusing stock_pool/: {args.pool_dir}")
        days = load_pool_days(Path(args.pool_dir), args.start, args.end)
        print(
            f"pool {args.pool_dir}: {len(days)} days, "
            f"{sum(len(v) for v in days.values())} name-days",
            flush=True,
        )
    else:
        days = scan_tr_pool(
            args.start,
            args.end,
            universe_mode=args.universe_mode,
            store_parquet=args.store_parquet,
            lake_root=args.lake_root,
            workers=args.workers,
        )
        print(
            f"tr signals: {len(days)} days, "
            f"{sum(len(v) for v in days.values())} name-days",
            flush=True,
        )
        write_dir = args.write_pool_dir
        if write_dir is not None:
            if is_repo_stock_pool(write_dir):
                raise SystemExit(f"refusing stock_pool/: {write_dir}")
            written = write_tr_pool(days, Path(write_dir), repo=REPO_ROOT)
            print(f"pool -> {write_dir} ({len(written)} files)", flush=True)

    if not days:
        raise SystemExit(f"no TR pool days in [{args.start}, {args.end}]")

    codes = sorted({normalize_stock_code(c) for cs in days.values() for c in cs})
    codes = [c for c in codes if c]
    lake_front = resolve_period_root("1d") / "dividend_type=front"
    print(f"load {len(codes)} codes OHLCV {args.start}..{args.end}", flush=True)
    frames = load_daily_ohlcv(
        codes, args.start, args.end, root=lake_front, workers=args.workers
    )
    print(f"ohlcv frames {len(frames)}", flush=True)

    signal_rows = build_signal_rows(days, frames)
    print(f"signal rows with bars {len(signal_rows)}", flush=True)
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
