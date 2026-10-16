"""Opt-in market-wide block-new gate; precomputed MA, exact prior session only."""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


def load_regime(path: str | Path, fast: int = 5, slow: int = 10) -> dict[str, int | None]:
    if not 0 < fast < slow:
        raise ValueError("bigvalue requires 0 < fast < slow")
    frame = pd.read_parquet(path)
    required = ["date", "bigvalue", f"ma{fast}", f"ma{slow}"]
    if missing := set(required) - set(frame.columns):
        raise ValueError(f"bigvalue missing columns: {sorted(missing)}")
    frame = frame[required].copy()
    # Strict YYYYMMDD contract: no truncation of floats or date coercion to epoch.
    frame["date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="raise").dt.strftime("%Y%m%d")
    if frame.empty or frame["date"].duplicated().any():
        raise ValueError("bigvalue empty input or duplicate dates")
    frame = frame.sort_values("date")
    for column in required[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    keep = len(frame)
    while keep and frame["bigvalue"].iloc[keep - 1] == 0:
        keep -= 1
    frame = frame.iloc[:keep]
    if frame.empty:
        raise ValueError("bigvalue has no finalized rows after trailing zeros")
    states = {}
    for day, value, fast_ma, slow_ma in frame.itertuples(index=False, name=None):
        states[day] = (
            None if not all(math.isfinite(x) for x in (value, fast_ma, slow_ma))
            else (-1 if fast_ma < slow_ma else (1 if fast_ma > slow_ma else 0))
        )
    return states


def with_bigvalue_gate(eligible_buy, bars, states, confirm_days=2):
    """Bind to the book's union daily-bar calendar, including loaded prehistory.

    Diagnostics count distinct queried buy days, independent of candidate count.
    Equality is neutral; missing/warmup/under-confirmation are fail-closed.
    """
    if confirm_days < 1:
        raise ValueError("bigvalue confirm-days must be positive")
    calendar = sorted({pd.Timestamp(day).strftime("%Y%m%d")
                       for frame in bars.values() if frame is not None
                       for day in frame.index})
    if not calendar:
        raise ValueError("bigvalue requires book calendar")
    positions = {day: i for i, day in enumerate(calendar)}
    if invalid := [day for day in states if calendar[0] <= day <= calendar[-1] and day not in positions]:
        raise ValueError(f"bigvalue noncalendar dates: {invalid[:3]}")
    reasons = {}
    for i, day in enumerate(calendar):
        state = states.get(calendar[i - 1]) if i else None
        if state is None:
            reasons[day] = "missing_or_warmup"
        elif state == 0:
            reasons[day] = "allowed_equal"
        elif i < confirm_days or any(states.get(d) != state for d in calendar[i-confirm_days:i]):
            reasons[day] = "under_confirm"
        else:
            reasons[day] = "death" if state == -1 else "allowed_golden"
    queried = set()
    diagnostics = {"skip_bigvalue_block": 0, "reasons_by_day": reasons}

    def list_ok(code, day):
        piece = getattr(eligible_buy, "list_ok", None)
        return True if piece is None else bool(piece(code, day))

    def seat_ok(code, day):
        ds = pd.Timestamp(str(day)).strftime("%Y%m%d")
        allowed = reasons.get(ds, "missing_or_warmup").startswith("allowed_")
        if not allowed:
            if ds not in queried:
                diagnostics["skip_bigvalue_block"] += 1
                queried.add(ds)
            return False
        piece = getattr(eligible_buy, "seat_ok", eligible_buy)
        return True if piece is None else bool(piece(code, day))

    def gated(code, day):
        return list_ok(code, day) and seat_ok(code, day)

    gated.list_ok = list_ok
    gated.seat_ok = seat_ok
    gated.bigvalue_diagnostics = diagnostics
    return gated
