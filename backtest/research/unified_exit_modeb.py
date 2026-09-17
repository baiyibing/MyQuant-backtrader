# -*- coding: utf-8 -*-
"""Unified-exit Mode B: none daily entries, session-minute exits (Q36/Q37).

Research only. Mode A and the shared trading ledger remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtest.research import unified_exit_modea as modea
from backtest.research.csv_daily_loader import warmup_start
from backtest.research.exdiv_map import load_exdiv_ratios
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


def assemble_instances(pool_dir, sessions, bars, *, tol=modea.DEFAULT_TOL, exdiv=None):
    """Mode A identity/filter contract with explicitly supplied none daily bars."""
    prepared = modea._PreparedBars(bars)
    for symbol in prepared:
        prepared.prev_maps[symbol] = _previous_refs(prepared, symbol, exdiv)
    return modea.assemble_instances(pool_dir, sessions, prepared, tol=tol)


def _previous_refs(daily, symbol, exdiv):
    """Map the prior raw daily close across intervening ex dates (including halts)."""
    closes = daily.closes(symbol)
    ordered = sorted(closes)
    events = (exdiv or {}).get(symbol, {})
    refs = {}
    for previous, current in zip(ordered, ordered[1:]):
        ref = closes[previous]
        for day, k in events.items():
            if previous < day <= current:
                ref *= k
        refs[current] = ref
    return refs


class PreparedMinutes:
    """Run-local grouped tuples, shared by every grid cell without frame mutation."""

    def __init__(self, bars):
        self.days = {}
        for symbol, frame in bars.items():
            frame = session_minutes(frame)
            self.days[symbol] = {
                ymd: list(day[["hm", "high", "low", "close"]].itertuples(index=False, name=None))
                for ymd, day in frame.groupby("ymd", sort=False)
            } if not frame.empty else {}


def _prepare_minutes(bars):
    return bars if isinstance(bars, PreparedMinutes) else PreparedMinutes(bars)


@dataclass(frozen=True)
class ExitResult(modea.ExitResult):
    shares: float
    sell_hm: int | None = None


def _result(inst, ymd, hm, price, shares, held, reason, *, trade):
    buy_cost = modea._lot_shares(inst.buy_price) * inst.buy_price * (1 + modea.COMMISSION)
    proceeds = shares * price * (1 - modea.COMMISSION if trade else 1)
    pnl = proceeds - buy_cost
    return ExitResult(ymd, price, reason, pnl / buy_cost, pnl, shares, held, trade, hm)


def evaluate_exit_modeb(inst, spec, daily_bars, minute_bars, sessions, *,
                        end=modea.DEFAULT_END, tol=modea.DEFAULT_TOL, exdiv=None):
    """SL-first high/low triggers; minute close fills; expiry at last session K.

    N counts market sessions. A blocked fill prevents all further sells that day,
    and rules are evaluated afresh next session (Q7). Buy-day minutes precede
    the daily-close entry and must never affect triggers or the trailing peak.
    """
    if not inst.opened:
        raise ValueError("evaluate_exit_modeb requires an opened instance")
    if spec.rule not in (0, 1, 2, 3):
        raise ValueError(f"unknown rule {spec.rule}")
    if spec.rule and (spec.n is None or spec.n < 1):
        raise ValueError("N must be positive")
    if spec.rule == 3 and spec.y is None:
        raise ValueError("trailing requires Y")
    daily = modea._prepare_bars(daily_bars)
    prev_by = _previous_refs(daily, inst.symbol, exdiv) if inst.symbol in daily else {}
    days = _prepare_minutes(minute_bars).days.get(inst.symbol, {})
    buy_i = modea._session_index(sessions, inst.list_date)
    cost = peak = mark_price = float(inst.buy_price)
    shares = float(modea._lot_shares(cost))
    mark_day, mark_hm, mark_held = inst.list_date, None, 0
    for i in range(buy_i + 1, len(sessions)):
        ymd = sessions[i]
        if ymd > end:
            break
        k = (exdiv or {}).get(inst.symbol, {}).get(ymd, 1.0)
        # E-R6 + Q29=B, local to this research module. No lot re-rounding.
        cost *= k
        peak *= k
        shares /= k
        mark_price *= k
        rows = days.get(ymd, [])
        blocked = False
        for j, (hm, high, low, close) in enumerate(rows):
            mark_day, mark_hm, mark_price, mark_held = ymd, int(hm), close, i - buy_i
            peak = max(peak, close)
            if blocked:
                continue
            reason = None
            if spec.rule == 2:
                if spec.y is not None and low <= cost * (1 - spec.y / 100):
                    reason = "stop_loss"
                elif spec.x is not None and high >= cost * (1 + spec.x / 100):
                    reason = "take_profit"
            elif spec.rule == 3 and close < peak * (1 - spec.y / 100):
                reason = "trailing"
            if reason is None and spec.rule and i - buy_i >= spec.n and j == len(rows) - 1:
                reason = "n_expire"
            if reason is None:
                continue
            prev = prev_by.get(ymd)
            if prev is not None and prev > 0 and modea._is_limit_down(close, prev, inst.symbol, inst.name, tol=tol):
                blocked = True
                continue
            return _result(inst, ymd, int(hm), close, shares, i - buy_i, reason, trade=True)
    return _result(inst, mark_day, mark_hm, mark_price, shares, mark_held, "mark_end", trade=False)


def evaluate_matrix(instances, specs, daily_bars, minute_bars, sessions, **kwargs):
    daily = modea._prepare_bars(daily_bars)
    minutes = _prepare_minutes(minute_bars)
    return {spec.label(): {
        modea.instance_key(inst): evaluate_exit_modeb(inst, spec, daily, minutes, sessions, **kwargs)
        for inst in modea.opened_instances(instances)
    } for spec in specs}
