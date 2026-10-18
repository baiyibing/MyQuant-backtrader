"""Shared opt-in market regime core: precomputed MA, exact prior session only.

Series-agnostic generalization of the bigvalue regime (#480): the input is a
parquet with ``date`` / a value column / ``ma{fast}`` / ``ma{slow}``; bigvalue
(大单净量) uses ``value_col="bigvalue"``, index gates use e.g. ``value_col="close"``
with ``fast=1`` (the value itself against its slow MA — no fake ma1 column).
See plan-market-regime-unify-2026-10-18.md. ``bigvalue_regime`` re-exports
this module unchanged; frozen books and CLI contracts are untouched.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


def load_regime(
    path: str | Path,
    fast: int = 5,
    slow: int = 10,
    *,
    value_col: str = "bigvalue",
) -> dict[str, int | None]:
    if not 0 < fast < slow:
        raise ValueError("regime requires 0 < fast < slow")
    frame = pd.read_parquet(path)
    fast_col = value_col if fast == 1 else f"ma{fast}"
    required = list(dict.fromkeys(["date", value_col, fast_col, f"ma{slow}"]))
    if missing := set(required) - set(frame.columns):
        raise ValueError(f"regime missing columns: {sorted(missing)}")
    frame = frame[required].copy()
    # Strict YYYYMMDD contract: no truncation of floats or date coercion to epoch.
    frame["date"] = pd.to_datetime(
        frame["date"].astype(str), format="%Y%m%d", errors="raise"
    ).dt.strftime("%Y%m%d")
    if frame.empty or frame["date"].duplicated().any():
        raise ValueError("regime empty input or duplicate dates")
    frame = frame.sort_values("date")
    for column in required[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    keep = len(frame)
    while keep and frame[value_col].iloc[keep - 1] == 0:
        keep -= 1
    frame = frame.iloc[:keep]
    if frame.empty:
        raise ValueError("regime has no finalized rows after trailing zeros")
    states = {}
    fast_line = frame[value_col] if fast == 1 else frame[f"ma{fast}"]
    for day, value, fast_ma, slow_ma in zip(
        frame["date"], frame[value_col], fast_line, frame[f"ma{slow}"]
    ):
        states[day] = (
            None
            if not all(math.isfinite(x) for x in (value, fast_ma, slow_ma))
            else (-1 if fast_ma < slow_ma else (1 if fast_ma > slow_ma else 0))
        )
    return states


def confirmed_days(bars, states, confirm_days=2):
    """Execution-day labels from exact prior sessions, never stale asof rows."""
    if confirm_days < 1:
        raise ValueError("regime confirm-days must be positive")
    calendar = sorted({pd.Timestamp(day).strftime("%Y%m%d")
                       for frame in bars.values() if frame is not None
                       for day in frame.index})
    if not calendar:
        raise ValueError("regime requires book calendar")
    positions = {day: i for i, day in enumerate(calendar)}
    if invalid := [day for day in states
                   if calendar[0] <= day <= calendar[-1] and day not in positions]:
        raise ValueError(f"regime noncalendar dates: {invalid[:3]}")
    reasons = {}
    for i, day in enumerate(calendar):
        state = states.get(calendar[i - 1]) if i else None
        if state is None:
            reasons[day] = "missing_or_warmup"
        elif state == 0:
            reasons[day] = "allowed_equal"
        elif i < confirm_days or any(states.get(d) != state
                                      for d in calendar[i - confirm_days:i]):
            reasons[day] = "under_confirm"
        else:
            reasons[day] = "death" if state == -1 else "allowed_golden"
    return reasons


def flatten_reason(reasons, day, enabled=False):
    return "regime_flat:bigvalue_death" if enabled and reasons.get(
        pd.Timestamp(str(day)).strftime("%Y%m%d")) == "death" else None


def regime_cash_fraction(reasons, day, multiplier=None, base=0.95):
    """Confirmed-golden deployment fraction: min(1, base*mult), else base."""
    if multiplier is None:
        return base
    if not math.isfinite(multiplier) or multiplier <= 0:
        raise ValueError("regime multiplier must be finite and positive")
    return min(1.0, base * multiplier) if reasons.get(
        pd.Timestamp(str(day)).strftime("%Y%m%d")) == "allowed_golden" else base


# Historical name from #480; the golden branch semantics are identical.
golden_cash_fraction = regime_cash_fraction


def with_regime_gate(eligible_buy, bars, states, confirm_days=2, *, block_new=True):
    """Preserve book list/seat hooks; unknown days always fail closed."""
    reasons = confirmed_days(bars, states, confirm_days)
    queried = set()
    diagnostics = {"skip_bigvalue_block": 0, "reasons_by_day": reasons}

    def list_ok(code, day):
        piece = getattr(eligible_buy, "list_ok", None)
        return True if piece is None else bool(piece(code, day))

    def seat_ok(code, day):
        ds = pd.Timestamp(str(day)).strftime("%Y%m%d")
        reason = reasons.get(ds, "missing_or_warmup")
        allowed = reason.startswith("allowed_") or (not block_new and reason == "death")
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


# Historical name from #480; attribute/counter names above are kept verbatim
# so engine wiring and diagnostics consumers stay byte-compatible.
with_bigvalue_gate = with_regime_gate
