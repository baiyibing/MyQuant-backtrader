#!/usr/bin/env python3
"""s9 + s10: post-signal N-day high/low (and dates), sorted by gain.

Two name lists:
- s9 底量超顶量 contract pool (``--s9-pool-dir``)
- s10 阻力 resist_tr_bb_1000 contract pool (``--s10-pool-dir``)

For each code's earliest signal in ``[--start, --end]`` (front daily):

- look at the next ``--horizon`` **trading** days **after** the signal day
  (signal day itself excluded)
- record max high / min low and the dates they first occur
- ``gain_pct`` = high / signal_close - 1; sort descending

Never writes ``stock_pool/``.
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

from backtest.research.source_b_tr_pool import normalize_stock_code  # noqa: E402
from common.infra.data_root import resolve_period_root  # noqa: E402
from scripts.data.export_strategy9_pool import load_daily_ohlcv  # noqa: E402
from scripts.research.s10_signal_peak_gains import load_pool_days  # noqa: E402
from scripts.research.s9_signal_peak_gains import (  # noqa: E402
    _bare,
    _ymd,
    per_stock_earliest,
)

CN_COLS = {
    "source": "名单",
    "code": "代码",
    "signal_date": "信号日",
    "signal_close": "信号收盘",
    "high": "区间最高",
    "high_date": "最高日",
    "low": "区间最低",
    "low_date": "最低日",
    "gain_pct": "涨幅%",
    "drop_pct": "跌幅%",
    "bars_used": "统计天数",
    "horizon": "目标天数",
    "n_signals": "信号次数",
}


def _ohlcv_end(end: str, horizon: int) -> str:
    """Pad calendar days so late signals can still fill the horizon."""
    return (pd.Timestamp(end) + pd.Timedelta(days=max(40, int(horizon) * 3))).strftime(
        "%Y%m%d"
    )


def post_signal_horizon_range(
    frame: pd.DataFrame,
    signal_i: int,
    *,
    horizon: int,
) -> Optional[dict[str, Any]]:
    """Stats on trading bars ``(signal_i, signal_i+horizon]`` (exclude signal day)."""
    start = int(signal_i) + 1
    end = start + int(horizon)
    if start >= len(frame):
        return None
    window = frame.iloc[start:end]
    if window.empty:
        return None
    highs = np.asarray(window["high"].to_numpy(), dtype=np.float64)
    lows = np.asarray(window["low"].to_numpy(), dtype=np.float64)
    if not np.isfinite(highs).any() or not np.isfinite(lows).any():
        return None
    hi_i = int(np.nanargmax(highs))
    lo_i = int(np.nanargmin(lows))
    return {
        "high": float(highs[hi_i]),
        "high_date": _ymd(window.index[hi_i]),
        "low": float(lows[lo_i]),
        "low_date": _ymd(window.index[lo_i]),
        "bars_used": int(len(window)),
    }


def build_rows(
    days: dict[str, list[str]],
    frames: dict[str, pd.DataFrame],
    *,
    source: str,
    horizon: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ymd in sorted(days):
        day = pd.Timestamp(ymd)
        for code in days[ymd]:
            canon = normalize_stock_code(code)
            if not canon:
                continue
            frame = frames.get(canon)
            if frame is None or frame.empty or day not in frame.index:
                continue
            loc = frame.index.get_loc(day)
            i = int(loc.stop - 1) if isinstance(loc, slice) else int(loc)
            signal_close = float(frame["close"].iloc[i])
            if not np.isfinite(signal_close) or signal_close <= 0:
                continue
            stats = post_signal_horizon_range(frame, i, horizon=horizon)
            if stats is None:
                continue
            gain_pct = (stats["high"] / signal_close - 1.0) * 100.0
            drop_pct = (stats["low"] / signal_close - 1.0) * 100.0
            rows.append(
                {
                    "source": source,
                    "code": _bare(canon),
                    "canonical": canon,
                    "signal_date": ymd,
                    "signal_close": round(signal_close, 4),
                    "high": round(stats["high"], 4),
                    "high_date": stats["high_date"],
                    "low": round(stats["low"], 4),
                    "low_date": stats["low_date"],
                    "gain_pct": round(gain_pct, 2),
                    "drop_pct": round(drop_pct, 2),
                    "bars_used": stats["bars_used"],
                    "horizon": int(horizon),
                }
            )
    return rows


def write_and_print(
    per_stock: list[dict[str, Any]],
    out_csv: Path,
    *,
    title: str,
    top: int,
) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(per_stock)
    if frame.empty:
        print(f"{title}: 0 rows", flush=True)
        frame.to_csv(out_csv, index=False, encoding="utf-8", lineterminator="\n")
        return
    frame["code"] = frame["code"].astype(str).str.zfill(6)
    frame.to_csv(out_csv, index=False, encoding="utf-8", lineterminator="\n")
    print(f"{title}: wrote {len(frame)} -> {out_csv}", flush=True)

    show = frame.head(int(top)).copy()
    show.insert(0, "排名", range(1, len(show) + 1))
    rename = {k: v for k, v in CN_COLS.items() if k in show.columns}
    show = show.rename(columns=rename)
    cols = [
        "排名",
        "代码",
        "信号日",
        "信号收盘",
        "区间最高",
        "最高日",
        "区间最低",
        "最低日",
        "涨幅%",
        "跌幅%",
        "统计天数",
        "信号次数",
    ]
    cols = [c for c in cols if c in show.columns]
    print(show[cols].to_string(index=False), flush=True)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "s9 + s10: post-signal N-trading-day high/low (+ dates), "
            "sorted by gain_pct (earliest signal per code)"
        )
    )
    ap.add_argument("--start", required=True, help="first signal day YYYYMMDD")
    ap.add_argument("--end", required=True, help="last signal day YYYYMMDD")
    ap.add_argument(
        "--s9-pool-dir",
        type=Path,
        required=True,
        help="strategy 9 contract pool dir",
    )
    ap.add_argument(
        "--s10-pool-dir",
        type=Path,
        default=None,
        help="strategy 10 / TR contract pool dir (optional; omit to skip s10)",
    )
    ap.add_argument(
        "--horizon",
        type=int,
        default=10,
        help="trading days after signal day (default 10; signal day excluded)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output dir (default: out/)",
    )
    ap.add_argument("--top", type=int, default=50, help="print top N per list")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv if argv is not None else None)

    if int(args.horizon) <= 0:
        raise SystemExit("--horizon must be > 0")

    out_dir = Path(args.out_dir) if args.out_dir is not None else REPO_ROOT / "out"
    ohlcv_end = _ohlcv_end(args.end, args.horizon)

    s9_days = load_pool_days(Path(args.s9_pool_dir), args.start, args.end)
    s10_days: dict[str, list[str]] = {}
    if args.s10_pool_dir is not None:
        s10_days = load_pool_days(Path(args.s10_pool_dir), args.start, args.end)
    print(
        f"s9 pool days={len(s9_days)} name-days={sum(len(v) for v in s9_days.values())}",
        flush=True,
    )
    if args.s10_pool_dir is not None:
        print(
            f"s10 pool days={len(s10_days)} "
            f"name-days={sum(len(v) for v in s10_days.values())}",
            flush=True,
        )
    else:
        print("s10 skipped (--s10-pool-dir omitted)", flush=True)

    codes = sorted(
        {
            normalize_stock_code(c)
            for days in (s9_days, s10_days)
            for cs in days.values()
            for c in cs
        }
    )
    codes = [c for c in codes if c]
    lake_front = resolve_period_root("1d") / "dividend_type=front"
    print(
        f"load {len(codes)} codes OHLCV {args.start}..{ohlcv_end} (pad for horizon)",
        flush=True,
    )
    frames = load_daily_ohlcv(
        codes, args.start, ohlcv_end, root=lake_front, workers=args.workers
    )
    print(f"ohlcv frames {len(frames)}", flush=True)

    s9_rows = build_rows(s9_days, frames, source="s9_bvot", horizon=args.horizon)
    s9_stock = per_stock_earliest(s9_rows)

    tag = f"{args.start}_{args.end}_h{args.horizon}"
    write_and_print(
        s9_stock,
        out_dir / f"s9_signal_{tag}_range.csv",
        title="【底量超顶量 s9】",
        top=args.top,
    )
    if args.s10_pool_dir is not None:
        s10_rows = build_rows(s10_days, frames, source="s10_tr", horizon=args.horizon)
        s10_stock = per_stock_earliest(s10_rows)
        print("", flush=True)
        write_and_print(
            s10_stock,
            out_dir / f"s10_signal_{tag}_range.csv",
            title="【阻力模型 s10】",
            top=args.top,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
