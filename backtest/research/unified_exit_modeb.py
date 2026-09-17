# -*- coding: utf-8 -*-
"""Unified-exit Mode B: none daily entries, session-minute exits (Q36/Q37).

Research only. Mode A and the shared trading ledger remain unchanged.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtest.research import unified_exit_modea as modea
from backtest.research.csv_daily_loader import warmup_start
from backtest.research.csv_minute_backtest import MINUTE_LAKE_END, load_minute_bars
from common.infra.data_root import resolve_period_root


def load_none_bars(codes, start, end, *, none_root=None, workers=8, bars=None):
    """Reuse daily I/O only, explicitly selecting the unadjusted price domain."""
    root = Path(none_root) if none_root is not None else resolve_period_root("1d") / "dividend_type=none"
    return modea.load_front_bars(codes, start, end, front_root=root, workers=workers, bars=bars)


def load_monitor_bars(codes, start=modea.DEFAULT_START, end=modea.DEFAULT_END,
                      *, workers=16, cache_dir=None, status=None):
    """Use the existing ten-calendar-day warmup cache (20251013 by default)."""
    return load_minute_bars(set(codes), warmup_start(start, days=10), end,
                            workers=workers, use_cache=True,
                            cache_dir=cache_dir, status=status)


def minute_coverage(codes, bars, *, start=modea.DEFAULT_START, end=modea.DEFAULT_END):
    """Count unique requested codes with session minutes inside the run window."""
    wanted = set(codes)
    found = set()
    for code in wanted & bars.keys():
        df = session_minutes(bars[code])
        if not df.empty and df["ymd"].between(start, end).any():
            found.add(code)
    return {"requested_codes": len(wanted), "covered_codes": len(found),
            "missing_codes": sorted(wanted - found), "minute_lake_end": MINUTE_LAKE_END}


def session_minutes(df):
    """Return chronological regular-session rows; exclude auctions/off-session K."""
    if df.empty:
        return df
    hm = df["hm"]
    mask = hm.between(930, 1130) | hm.between(1300, 1500)
    out = df.loc[mask].copy()
    out["ymd"] = out["ymd"].astype(str)
    return out.sort_values(["ymd", "hm"], kind="stable")


def assemble_instances(pool_dir, sessions, bars, *, tol=modea.DEFAULT_TOL):
    """Mode A identity/filter contract with explicitly supplied none daily bars."""
    return modea.assemble_instances(pool_dir, sessions, bars, tol=tol)
