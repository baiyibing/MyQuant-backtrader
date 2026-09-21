#!/usr/bin/env python3
"""Front ma_chip signals through D -> pool for first bar T strictly after D.

Outputs: out-dir/pool/YYYYMMDD.csv, out-dir/rejected.csv, manifest.json.
The separate pool directory keeps audit CSVs outside the strict pool contract.
No TR store signal columns are consumed; Rust CYQK is recomputed at window=200.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
import importlib
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research import ma_infra, strategy11_rules as rules  # noqa: E402
from backtest.research.csv_pool import is_repo_stock_pool, validate_pool_dir  # noqa: E402
from backtest.research.market_layer import is_st_name  # noqa: E402
from common.infra.data_root import resolve_period_root, resolve_source_parquet  # noqa: E402
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key  # noqa: E402
from oskh_factors.bridge.turnover_resist import circulating_capital_asof  # noqa: E402

LOAD_START = "20220701"
STATS_START = "20240101"
SEED = 20240907
STEP = 0.01
MAX_GRID_POINTS = 250_000
MAX_STALE_DAYS = 4
BOARDS = ("sz_main", "sh_main", "chinext")
COUNTERS = ("skip_buy(stale)", "skip_cyqk_grid", "skip_cyqk_nan",
            "skip_cyqk_error", "skip_warmup", "skip_zero_volume",
            "awaiting_contract_bar", "signals", "pool_rows")


@dataclass
class ScanResult:
    days: dict = field(default_factory=lambda: defaultdict(list))
    rejected: list = field(default_factory=list)
    counts: Counter = field(default_factory=lambda: Counter(dict.fromkeys(COUNTERS, 0)))
    symbols: list = field(default_factory=list)

    def reject(self, symbol, day, reason, *, contract_day="", detail=""):
        self.counts[reason] += 1
        self.rejected.append({
            "date": pd.Timestamp(day).strftime("%Y%m%d"), "symbol": symbol,
            "reason": reason, "original_signal_day": pd.Timestamp(day).strftime("%Y%m%d"),
            "contract_day": contract_day, "detail": detail,
        })


def board_of(code):
    bare, _, market = code.partition(".")
    if len(bare) != 6 or not bare.isdigit():
        return None
    if market == "SH" and bare.startswith("60"):
        return "sh_main"
    if market == "SZ" and bare.startswith(("000", "001", "002", "003")):
        return "sz_main"
    if market == "SZ" and bare.startswith(("300", "301")):
        return "chinext"
    return None


def candidates_by_board(codes, float_codes, *, sample=True, names=None, seed=SEED):
    """Archived RNG order, followed by warmup replacement in the caller."""
    candidates = sorted(set(codes) & set(float_codes))
    candidates = [code for code in candidates if board_of(code)]
    if not sample:
        missing = [code for code in candidates
                   if not names or not str(names.get(code, "")).strip()
                   or pd.isna(names.get(code))]
        if missing:
            raise ValueError(f"universe ST filter requires names; missing: {missing[:5]}")
        candidates = [code for code in candidates if not is_st_name(names[code])]
    rng = np.random.default_rng(seed)
    out = {}
    for board in BOARDS:
        group = [code for code in candidates if board_of(code) == board]
        if sample:
            rng.shuffle(group)
        out[board] = group
    return out


def contract_day(signal_day, bar_days, *, observed_through):
    """Return (T, rejection reason); stale always ages from the original D.

    Right-censored signals with <=4 observed calendar days stay unexported.
    ``bar_days`` is the sorted, zero-volume-filtered bar calendar for this code.
    """
    original = pd.Timestamp(signal_day).normalize()
    days = pd.DatetimeIndex(bar_days)
    loc = bisect_right(days, original)  # strict: never D itself
    target = days[loc] if loc < len(days) else None
    boundary = target if target is not None else pd.Timestamp(observed_through)
    if (boundary - original).days > MAX_STALE_DAYS:
        return target, "skip_buy(stale)"
    return target, "" if target is not None else "awaiting_contract_bar"


def prepare_frame(frame, end):
    required = ["open", "high", "low", "close", "volume"]
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("daily bars require a DatetimeIndex")
    out = frame[required].astype(float).copy()
    out.index = out.index.normalize()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.loc[out.index <= pd.Timestamp(end)]
    dropped = int((out["volume"] == 0).sum())
    return out.loc[out["volume"] != 0], dropped


def compute_signals(frame, shares, compute_cyqk):
    """Causal series, including explicit prefix weekly MA and bounded Rust runs.

    Partition safe output windows into runs so no oversized window ever reaches
    Rust. Do not drop bad-input days: Rust must return NaN in each affected window.
    ValueError is deliberately caught by the per-symbol caller, without fallback.
    """
    n = len(frame)
    if len(shares) != n:
        raise ValueError("close/high/low/volume/shares must have the same length")
    close, high, low, volume = (frame[col].tolist() for col in ("close", "high", "low", "volume"))
    window = rules.CYQK_WINDOW
    span = (frame["high"].rolling(window, min_periods=1).max()
            - frame["low"].rolling(window, min_periods=1).min()) / STEP
    grid = (span > MAX_GRID_POINTS).to_numpy()
    grid[:window - 1] = False
    cyqk = np.full(n, np.nan)
    i = window - 1
    while i < n:
        if grid[i]:
            i += 1
            continue
        stop = i + 1
        while stop < n and not grid[stop]:
            stop += 1
        lo = i - window + 1
        values = np.asarray(compute_cyqk(
            close[lo:stop], high[lo:stop], low[lo:stop], volume[lo:stop],
            list(shares[lo:stop]), window=window, start_i=window - 1, step=STEP,
        ), dtype=float)
        if values.shape != (stop - lo,):
            raise ValueError("compute_cyqk_series returned unequal length")
        cyqk[i:stop] = values[window - 1:]
        i = stop
    bands = ma_infra.bb_series(close)
    upper = [None if band is None else band[1] for band in bands]
    weekly = ma_infra.weekly_sma_series(
        frame.index.date.tolist(), close, rules.WEEKLY_WINDOW, prefix_equivalent=True,
    )
    edges = rules.edge_condition(close, high, upper, cyqk, weekly)
    finite = np.isfinite(np.asarray(weekly, dtype=float)) & np.isfinite(cyqk)
    finite &= np.isfinite(np.asarray(upper, dtype=float))
    finite &= np.isfinite(np.asarray(ma_infra.sma_series(close, 60), dtype=float))
    finite &= np.isfinite(close) & np.isfinite(high)
    return edges, cyqk, grid, finite


def scan_symbol(code, frame, history, start, end, compute_cyqk, result, *, require_warmup=False):
    frame, dropped = prepare_frame(frame, end)
    result.counts["skip_zero_volume"] += dropped
    shares = circulating_capital_asof(code, frame.index, history=history)
    try:
        edges, cyqk, grid, finite = compute_signals(frame, shares, compute_cyqk)
    except ValueError as exc:
        result.reject(code, start, "skip_cyqk_error", detail=str(exc))
        return False
    if require_warmup and not finite[frame.index < pd.Timestamp(start)].any():
        result.reject(code, start, "skip_warmup")
        return False
    result.symbols.append(code)
    for i, day in enumerate(frame.index):
        # The approved statistics window masks pre-window edges at export time.
        if day < max(pd.Timestamp(start), pd.Timestamp(STATS_START)):
            continue
        if grid[i]:
            result.reject(code, day, "skip_cyqk_grid")
        elif i >= rules.CYQK_WINDOW - 1 and not np.isfinite(cyqk[i]):
            result.reject(code, day, "skip_cyqk_nan")
        if not edges[i]:
            continue
        result.counts["signals"] += 1
        target, reason = contract_day(day, frame.index, observed_through=end)
        if reason == "skip_buy(stale)":
            result.reject(code, day, reason,
                          contract_day="" if target is None else target.strftime("%Y%m%d"))
        elif reason:
            result.counts[reason] += 1
        elif pd.Timestamp(start) <= target <= pd.Timestamp(end):
            result.days[target.strftime("%Y%m%d")].append(code)
            result.counts["pool_rows"] += 1
    return True


def read_front_daily(code, root, start, end):
    """Read only the configured front lake; missing files fail visibly."""
    path = Path(root) / f"symbol={to_partition_key(code)}" / "data.parquet"
    table = pq.ParquetFile(path).read(columns=["time", "open", "high", "low", "close", "volume"])
    stamps = pd.to_datetime(table["time"].to_numpy(), unit="ms", utc=True)
    days = stamps.tz_convert("Asia/Shanghai").tz_localize(None).normalize()
    frame = table.to_pandas().drop(columns="time")
    frame.index = days
    return frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index <= pd.Timestamp(end))]


def write_strategy11_pool(result, out_dir, manifest, *, repo=REPO_ROOT):
    out_dir = Path(out_dir)
    pool_dir = out_dir / "pool"
    if is_repo_stock_pool(out_dir, repo=repo) or is_repo_stock_pool(pool_dir, repo=repo):
        raise SystemExit(f"refusing to write into stock_pool/: {out_dir}")
    # Refuse reruns over old pools rather than silently retaining stale files.
    if pool_dir.exists() and any(pool_dir.iterdir()):
        raise FileExistsError(f"pool output must be empty: {pool_dir}")
    pool_dir.mkdir(parents=True, exist_ok=True)
    for day, symbols in sorted(result.days.items()):
        pd.Timestamp(day)  # validate before forming a filename
        if len(day) != 8 or not day.isdigit():
            raise ValueError(f"invalid pool date: {day}")
        codes = sorted({code.split(".")[0] for code in symbols})
        if any(len(code) != 6 or not code.isdigit() for code in codes):
            raise ValueError(f"invalid pool codes: {symbols}")
        if codes:
            (pool_dir / f"{day}.csv").write_text("".join(f"{code}\n" for code in codes),
                                               encoding="utf-8", newline="\n")
    failures = validate_pool_dir(pool_dir)
    if failures:
        raise ValueError("invalid strategy11 pool: " + "; ".join(failures))
    columns = ["date", "symbol", "reason", "original_signal_day", "contract_day", "detail"]
    pd.DataFrame(result.rejected, columns=columns).to_csv(
        out_dir / "rejected.csv", index=False, encoding="utf-8", lineterminator="\n",
    )
    payload = {
        **manifest, "strategy": "version11", "adjust_type": "front",
        "contract_day": "first bar strictly after original D; D->T <=4 calendar days",
        "signal_cutoff": "<=T-1", "weekly_prefix_equivalent": True,
        "cyqk_window": rules.CYQK_WINDOW, "cyqk_step": STEP,
        "max_grid_points": MAX_GRID_POINTS, "counts": dict(result.counts),
        "universe": result.symbols, "pool_dir": str(pool_dir),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
    )
    return pool_dir


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 epilog=rules.HELP_LOCK,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default=STATS_START, help="statistics and pool start YYYYMMDD")
    ap.add_argument("--end", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--load-start", default=LOAD_START)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--sample", nargs="?", const=SEED, default=SEED, type=int,
                      help="seed-30: 10 per board; optional seed (default 20240907)")
    mode.add_argument("--universe", action="store_true", help="all eligible names, filter ST and 688")
    ap.add_argument("--out-dir", type=Path)
    args = ap.parse_args(argv)
    if not pd.Timestamp(args.load_start) < pd.Timestamp(args.start) <= pd.Timestamp(args.end):
        ap.error("require load-start < start <= end")
    out_dir = args.out_dir or REPO_ROOT / "exports" / f"s11_machip_{args.start}_{args.end}"
    if is_repo_stock_pool(out_dir) or is_repo_stock_pool(out_dir / "pool"):
        ap.error("refusing to write into stock_pool/")
    started = perf_counter()
    root = resolve_period_root("1d") / "dividend_type=front"
    if not root.is_dir():
        raise FileNotFoundError(root)
    codes = [to_canonical_symbol(p.parent.name) for p in root.glob("symbol=*/data.parquet")]
    if not codes:
        raise ValueError(f"no front bars in configured lake: {root}")
    floats = pd.read_parquet(resolve_source_parquet("float_shares.parquet"))
    history = pd.read_parquet(resolve_source_parquet("free_float_shares.parquet"))
    float_codes = floats["stock_code"].map(to_canonical_symbol).tolist()
    names = dict(zip(float_codes, floats["name"], strict=True)) if "name" in floats else None
    groups = candidates_by_board(codes, float_codes, sample=not args.universe,
                                 names=names, seed=args.sample)
    rust = importlib.import_module("turnover_resist")
    compute_cyqk = rust.compute_cyqk_series  # no algorithm fallback
    result = ScanResult()
    for board, candidates in groups.items():
        accepted = 0
        for code in candidates:
            frame = read_front_daily(code, root, args.load_start, args.end)
            accepted += scan_symbol(code, frame, history, args.start, args.end, compute_cyqk,
                                    result, require_warmup=not args.universe)
            if not args.universe and accepted == 10:
                break
        if not args.universe and accepted != 10:
            raise ValueError(f"seed-30 needs 10 warmed names in {board}, got {accepted}")
        print(f"v11 {board}: {accepted} names", flush=True)
    pool = write_strategy11_pool(result, out_dir, {
        "start": args.start, "end": args.end, "load_start": args.load_start,
        "stats_floor": STATS_START, "warmup_bars_required": rules.CYQK_WINDOW,
        "mode": "universe" if args.universe else "seed-30", "seed": args.sample,
        "pyd_file": str(rust.__file__), "pyd_version": str(getattr(rust, "__version__", "unknown")),
        "elapsed_seconds": perf_counter() - started,
    })
    print(f"v11 pool: {pool}; counts={dict(result.counts)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
