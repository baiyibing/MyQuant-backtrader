# -*- coding: utf-8 -*-
"""Process-level SSE trade calendar cache from pandas-market-calendars.

Zero-side-effect infrastructure layer: no Redis / hkcodex / strategy_config.
First call lazily builds the cache; subsequent queries use bisect.
Thread-safe: CPython GIL protects reference assignment; Lock serialises the build.

Unified to SSE (not XSHG): XSHG lacks ``regular_holidays`` after 2026-10-07 and
misclassifies 2027+ statutory holidays as trading days. See
``docs/engineering/plan-trade-calendar-unify-2026-07-13.md`` §3.2.
"""
from __future__ import annotations

import bisect
import threading
from datetime import datetime
from typing import List, Optional

import pandas as pd

from common.infra.pandas_frame_utils import (
    cal_date_dataframe_from_strings,
    empty_cal_date_dataframe,
)
from common.infra.timekeeping import shanghai_now

_SSE_CACHE: Optional[List[str]] = None  # None = not built yet
_SSE_CACHE_FAILED: bool = False  # True = build failed, don't retry
_SSE_CACHE_BUILD_YEAR: Optional[int] = None  # for annual auto-rebuild
_SSE_LOCK = threading.Lock()


def _build_sse_cache(reference_date: Optional[datetime] = None) -> List[str]:
    """Lazily build sorted YYYYMMDD trade-day list.

    ``reference_date`` for test injection only; production passes None.
    Uses ``shanghai_now()`` (Asia/Shanghai) — consistent with SSE calendar.
    """
    global _SSE_CACHE, _SSE_CACHE_FAILED, _SSE_CACHE_BUILD_YEAR
    now = reference_date or shanghai_now()
    # Annual auto-rebuild: if cache was built ≥ 3 years ago, force rebuild.
    # The cache covers [now-15y, now+5y], so rebuilding every 3 years keeps
    # the forward window ≥ 2 years.
    # This check is outside the lock (racy), but the inner double-check inside
    # the lock serialises the rebuild — only one thread actually calls mcal.
    if _SSE_CACHE is not None and _SSE_CACHE_BUILD_YEAR is not None:
        if now.year - _SSE_CACHE_BUILD_YEAR >= 3:
            _SSE_CACHE = None
    if _SSE_CACHE is not None or _SSE_CACHE_FAILED:
        return _SSE_CACHE or []
    with _SSE_LOCK:
        if _SSE_CACHE is not None or _SSE_CACHE_FAILED:
            return _SSE_CACHE or []
        try:
            import pandas_market_calendars as mcal

            start = now.replace(year=now.year - 15)
            end = now.replace(year=now.year + 5)
            cal = mcal.get_calendar("SSE")
            days = cal.valid_days(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            _SSE_CACHE = sorted(d.date().strftime("%Y%m%d") for d in days)
            _SSE_CACHE_BUILD_YEAR = now.year
        except Exception:
            _SSE_CACHE_FAILED = True  # don't retry; callers fall through to Redis/hkcodex
        return _SSE_CACHE or []


def get_trade_days_sse(
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    count: Optional[int] = None,
) -> Optional[pd.DataFrame]:
    """Query SSE cache via bisect; returns None on miss (caller falls through).

    Supports three modes: since+until, until+count, since-only.

    For ``since+until``, an empty slice is **authoritative** (holiday / non-session
    window) and returns an empty DataFrame — not ``None`` — so callers must not
    fall through to Redis/local and resurrect false trading days (P0-d 2027).

    .. warning:: since-only returns all trading days from *since* to cache end
       (up to ~5 years, thousands of rows).  Use count or until to limit.
    """
    cal = _build_sse_cache()
    if not cal:
        return None
    s_norm = str(since or "").strip()
    u_norm = str(until or "").strip()
    c = int(count) if count is not None and int(count) > 0 else None

    if s_norm and u_norm:
        days = cal[bisect.bisect_left(cal, s_norm) : bisect.bisect_right(cal, u_norm)]
        # Authoritative empty (holiday) vs miss (None).
        return (
            cal_date_dataframe_from_strings(days)
            if days
            else empty_cal_date_dataframe()
        )
    if u_norm and c:
        r = bisect.bisect_right(cal, u_norm)
        days = cal[max(0, r - c) : r]
    elif s_norm and not u_norm and c is None:
        days = cal[bisect.bisect_left(cal, s_norm) :]
    else:
        return None
    return cal_date_dataframe_from_strings(days) if days else None


def warmup_sse_cache() -> bool:
    """Bootstrap preheating: build cache early so first sell scan hits memory.

    Returns True if cache built successfully (or already built).
    """
    return bool(_build_sse_cache())


def mark_sse_cache_permanently_failed() -> None:
    """Fail-closed: disable SSE cache for rest of **this process** lifetime.

    Sets ``_SSE_CACHE_FAILED`` (session-scoped; not persisted across days).
    Used when SSE-vs-QMT diff detects a true calendar mismatch. Recover via
    process restart or ``invalidate_sse_cache()``.
    """
    global _SSE_CACHE_FAILED
    _SSE_CACHE_FAILED = True


def invalidate_sse_cache() -> None:
    """Clear cache (daily diff auto-recovery / tests / calendar refresh)."""
    global _SSE_CACHE, _SSE_CACHE_FAILED, _SSE_CACHE_BUILD_YEAR
    with _SSE_LOCK:
        _SSE_CACHE = None
        _SSE_CACHE_FAILED = False
        _SSE_CACHE_BUILD_YEAR = None


def list_sse_trade_dates(*, since: str, until: str) -> List[str]:
    """Return YYYYMMDD trade dates for ``[since, until]``.

    Prefer the process SSE cache; if the requested ``since`` is before the
    cache window (typical for long backtests), fall back to a one-shot
    ``mcal.get_calendar(\"SSE\").valid_days`` for the exact range.
    """
    s_norm = str(since or "").strip()
    u_norm = str(until or "").strip()
    if not s_norm or not u_norm:
        return []
    df = get_trade_days_sse(since=s_norm, until=u_norm)
    if df is not None and not df.empty:
        days = [str(x) for x in df["cal_date"].astype(str).tolist()]
        if days and days[0] <= s_norm:
            return days
    try:
        import pandas_market_calendars as mcal

        start = f"{s_norm[:4]}-{s_norm[4:6]}-{s_norm[6:8]}"
        end = f"{u_norm[:4]}-{u_norm[4:6]}-{u_norm[6:8]}"
        cal = mcal.get_calendar("SSE")
        raw = cal.valid_days(start, end)
        return sorted(d.date().strftime("%Y%m%d") for d in raw)
    except Exception:
        return []


__all__ = [
    "get_trade_days_sse",
    "list_sse_trade_dates",
    "warmup_sse_cache",
    "invalidate_sse_cache",
    "mark_sse_cache_permanently_failed",
]
