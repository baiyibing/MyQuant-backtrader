# -*- coding: utf-8 -*-
"""Unified-exit Mode A: instance assembly + exit matrix + aggregation.

Spec SSOT: docs/backtest/stock-backtest-unified-exit-proposal-2026-09-17.md
§1 / §12 (Q1–Q35 locked). Uncovered boundary → STOP, open Q36+ in proposal §10.

Mode A only (front daily close). No backtrader / Cerebro / Mode B / E-R6.
Entry set is strategy-independent (nominal cash pool 1.1e9 never caps).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import pandas as pd

from backtest.research.csv_daily_loader import _read_one_daily, warmup_start
from backtest.research.csv_pool import parse_pool_csv_entries
from backtest.research.market_layer import limit_pct
from common.infra.data_root import resolve_period_root

DEFAULT_START = "20251023"
DEFAULT_END = "20260909"
DEFAULT_TOL = 0.002
LOT_NOTIONAL = 1_000_000.0
CASH_POOL = 1_100_000_000.0
COMMISSION = 0.001
WINDOW_CALENDAR_DAYS = 322  # 20251023–20260909 inclusive calendar span for annualization


def ymd_to_date(ymd: str) -> date:
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def date_to_ymd(d: date | pd.Timestamp) -> str:
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return d.strftime("%Y%m%d")


def load_session_calendar(
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    *,
    sessions: Optional[Sequence[str]] = None,
) -> list[str]:
    """Market sessions YYYYMMDD in ``[start, end]``.

    Production path uses v7 ``load_index_daily`` (000001.SH). Tests inject
    ``sessions`` so CI stays data-free. Master has no ``load_index_daily_closes``.
    """
    if sessions is not None:
        d0, d1 = ymd_to_date(start), ymd_to_date(end)
        out = sorted(
            y for y in sessions if d0 <= ymd_to_date(y) <= d1
        )
        if not out:
            raise ValueError("injected sessions empty inside window")
        return out

    from backtest.research.csv_minute_backtest_v7 import load_index_daily

    closes = load_index_daily(ymd_to_date(start), ymd_to_date(end))
    d0, d1 = ymd_to_date(start), ymd_to_date(end)
    return [date_to_ymd(d) for d in sorted(closes) if d0 <= d <= d1]


def resolve_front_root(front_root: Optional[Path] = None) -> Path:
    """Front dividend daily root via lake resolvers (never cwd stock_data/)."""
    if front_root is not None:
        return Path(front_root)
    return resolve_period_root("1d") / "dividend_type=front"


def load_front_bars(
    codes: Iterable[str],
    start: str,
    end: str,
    *,
    front_root: Optional[Path] = None,
    workers: int = 8,
    bars: Optional[Mapping[str, pd.DataFrame]] = None,
) -> dict[str, pd.DataFrame]:
    """Load front daily OHLCV keyed by canonical code.

    ``bars`` injects an in-memory map for synthetic tests (skip lake I/O).
    """
    if bars is not None:
        return {c: bars[c] for c in codes if c in bars}

    root = resolve_front_root(front_root)
    warm = warmup_start(start, days=20)
    codes_list = sorted(set(codes))
    out: dict[str, pd.DataFrame] = {}

    def _one(code: str) -> tuple[str, Optional[pd.DataFrame]]:
        return code, _read_one_daily(code, root, warm, end)

    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        for code, df in pool.map(_one, codes_list):
            if df is not None and not df.empty:
                out[code] = df
    return out


@dataclass(frozen=True)
class Instance:
    """One pool-row appearance = one independent lot."""

    symbol: str
    name: str
    list_date: str
    buy_price: float
    opened: bool
    skip_reason: Optional[str] = None  # no_bar | limit_up | unknown_board | shares_zero


def _bar_close_map(df: pd.DataFrame) -> dict[str, float]:
    return {date_to_ymd(idx): float(close) for idx, close in zip(df.index, df["close"])}


def _prev_close_on(df: pd.DataFrame, ymd: str) -> Optional[float]:
    """Previous bar close (cross-suspension): prior row in the series, not calendar-1."""
    closes = _bar_close_map(df)
    if ymd not in closes:
        return None
    ordered = sorted(closes)
    i = ordered.index(ymd)
    if i == 0:
        return None
    return closes[ordered[i - 1]]


def _lot_shares(buy_price: float) -> int:
    if buy_price <= 0:
        return 0
    return int(LOT_NOTIONAL // buy_price // 100) * 100


def _is_limit_up(
    close: float,
    prev_close: float,
    code: str,
    name: str,
    *,
    tol: float = DEFAULT_TOL,
) -> bool:
    lp = limit_pct(code, name)
    if lp is None:
        return False  # caller handles unknown_board separately
    pct = close / prev_close - 1.0
    return pct >= lp - tol


def _is_limit_down(
    close: float,
    prev_close: float,
    code: str,
    name: str,
    *,
    tol: float = DEFAULT_TOL,
) -> bool:
    lp = limit_pct(code, name)
    if lp is None:
        return False
    pct = close / prev_close - 1.0
    return pct <= -(lp - tol)


def iterate_pool_entries(
    pool_dir: Path,
    sessions: Sequence[str],
) -> list[tuple[str, str, str]]:
    """Yield (symbol, name, list_ymd) for each pool file that exists.

    Missing session files (e.g. 20260525 / 20260605) = no list that day: skip, no error.
    """
    root = Path(pool_dir)
    rows: list[tuple[str, str, str]] = []
    for ymd in sessions:
        path = root / f"{ymd}.csv"
        if not path.is_file():
            continue
        for symbol, name in parse_pool_csv_entries(path):
            rows.append((symbol, name, ymd))
    return rows


def assemble_instances(
    pool_dir: Path,
    sessions: Sequence[str],
    bars: Mapping[str, pd.DataFrame],
    *,
    tol: float = DEFAULT_TOL,
) -> list[Instance]:
    """Build the Mode A instance table (opened + skipped).

    Buy filter (Q5/Q6): no K on list day → skip; close limit-up (±tol) → skip no chase;
    unknown board → skip; shares round-down to 0 → skip.
    Buy price = list-day front close. prev_close = prior bar in series (cross halt).
    """
    out: list[Instance] = []
    for symbol, name, ymd in iterate_pool_entries(pool_dir, sessions):
        df = bars.get(symbol)
        if df is None or df.empty:
            out.append(Instance(symbol, name, ymd, 0.0, False, "no_bar"))
            continue
        closes = _bar_close_map(df)
        if ymd not in closes:
            out.append(Instance(symbol, name, ymd, 0.0, False, "no_bar"))
            continue
        buy_price = closes[ymd]
        lp = limit_pct(symbol, name)
        if lp is None:
            out.append(Instance(symbol, name, ymd, buy_price, False, "unknown_board"))
            continue
        prev = _prev_close_on(df, ymd)
        if prev is None or prev <= 0:
            # No prior bar to judge limit-up — still allow buy (first bar in series).
            prev = None
        if prev is not None and _is_limit_up(buy_price, prev, symbol, name, tol=tol):
            out.append(Instance(symbol, name, ymd, buy_price, False, "limit_up"))
            continue
        if _lot_shares(buy_price) < 100:
            out.append(Instance(symbol, name, ymd, buy_price, False, "shares_zero"))
            continue
        out.append(Instance(symbol, name, ymd, buy_price, True, None))
    return out


def opened_instances(instances: Sequence[Instance]) -> list[Instance]:
    return [inst for inst in instances if inst.opened]


def instance_key(inst: Instance) -> str:
    return f"{inst.symbol}|{inst.list_date}"



def main(argv: Optional[list[str]] = None) -> int:
    """CLI: Slice A prints assembly counts; B/C extend this entry."""
    import argparse
    import json

    ap = argparse.ArgumentParser(description="unified-exit Mode A (front daily grid)")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--pool-dir", type=Path, default=Path("stock_pool"))
    ap.add_argument("--front-root", type=Path, default=None)
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("backtest_output/unified_exit_modea"),
    )
    ap.add_argument(
        "--stage",
        choices=("assemble", "all"),
        default="assemble",
        help="assemble = instances only (Slice A); all = full grid (Slices B/C)",
    )
    args = ap.parse_args(argv)

    sessions = load_session_calendar(args.start, args.end)
    pool_rows = iterate_pool_entries(args.pool_dir, sessions)
    codes = sorted({c for c, _n, _y in pool_rows})
    bars = load_front_bars(
        codes, args.start, args.end, front_root=args.front_root, workers=args.workers
    )
    instances = assemble_instances(args.pool_dir, sessions, bars, tol=args.tol)
    opened = opened_instances(instances)
    summary = {
        "stage": "assemble",
        "start": args.start,
        "end": args.end,
        "sessions": len(sessions),
        "pool_rows": len(pool_rows),
        "instances": len(instances),
        "opened": len(opened),
        "skipped": {
            reason: sum(1 for i in instances if i.skip_reason == reason)
            for reason in sorted({i.skip_reason for i in instances if i.skip_reason})
        },
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "assemble_summary.json").write_text(
        json.dumps(summary, ensure_ascii=True, indent=1), encoding="utf-8"
    )
    print(
        f"[assemble] sessions={summary['sessions']} rows={summary['pool_rows']} "
        f"opened={summary['opened']} skipped={summary['skipped']}"
    )
    if args.stage != "assemble":
        print("[warn] stage=all requires Slices B/C; falling back to assemble-only")
    return 0
