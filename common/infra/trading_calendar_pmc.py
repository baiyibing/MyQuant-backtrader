"""BT clock/window and failure policy over infra's SSE calendar data cache."""
from __future__ import annotations

from datetime import datetime
import threading

import pandas as pd
from myquant_infra.reference_data.calendar import (
    CalendarBuildError, CalendarCoverageError, SSECalendar,
    get_trade_days_sse as _query,
    list_sse_trade_dates as _list_dates,
)

from common.infra.timekeeping import shanghai_now

_SSE_CALENDAR: SSECalendar | None = None
_SSE_CACHE_FAILED = False
_SSE_CACHE_BUILD_YEAR: int | None = None
_SSE_LOCK = threading.Lock()


def _calendar(reference_date: datetime | None = None) -> SSECalendar:
    """BT chooses the rolling coverage window; infra builds and queries it."""
    global _SSE_CALENDAR, _SSE_CACHE_BUILD_YEAR
    now = reference_date or shanghai_now()
    with _SSE_LOCK:
        if (_SSE_CALENDAR is None or _SSE_CACHE_BUILD_YEAR is None
                or now.year - _SSE_CACHE_BUILD_YEAR >= 3):
            _SSE_CALENDAR = SSECalendar(
                start=f"{now.year - 15}{now:%m%d}",
                end=f"{now.year + 5}{now:%m%d}",
            )
            _SSE_CACHE_BUILD_YEAR = now.year
        return _SSE_CALENDAR


def _build_sse_cache(reference_date: datetime | None = None) -> list[str]:
    global _SSE_CACHE_FAILED
    if _SSE_CACHE_FAILED:
        return []
    calendar = _calendar(reference_date)
    try:
        start, end = calendar.coverage
        return _list_dates(calendar=calendar, since=start, until=end)
    except CalendarBuildError:
        _SSE_CACHE_FAILED = True
        return []


def get_trade_days_sse(*, since: str | None = None, until: str | None = None,
                       count: int | None = None) -> pd.DataFrame | None:
    """Covered holidays are empty; an unavailable/uncovered query returns None."""
    global _SSE_CACHE_FAILED
    if _SSE_CACHE_FAILED:
        return None
    try:
        return _query(calendar=_calendar(), since=since, until=until, count=count)
    except CalendarBuildError:
        _SSE_CACHE_FAILED = True
        return None


def warmup_sse_cache() -> bool:
    return bool(_build_sse_cache())


def mark_sse_cache_permanently_failed() -> None:
    """Host mismatch policy: disable this process's cache until reset."""
    global _SSE_CACHE_FAILED
    _SSE_CACHE_FAILED = True


def invalidate_sse_cache() -> None:
    global _SSE_CALENDAR, _SSE_CACHE_FAILED, _SSE_CACHE_BUILD_YEAR
    with _SSE_LOCK:
        _SSE_CALENDAR = None
        _SSE_CACHE_FAILED = False
        _SSE_CACHE_BUILD_YEAR = None


def list_sse_trade_dates(*, since: str, until: str) -> list[str]:
    """BT may request a wider explicit research window from the same SSE source."""
    if not str(since or "").strip() or not str(until or "").strip() or _SSE_CACHE_FAILED:
        return []
    try:
        return _list_dates(calendar=_calendar(), since=since, until=until)
    except CalendarCoverageError:
        try:
            return _list_dates(calendar=SSECalendar(start=since, end=until), since=since, until=until)
        except CalendarBuildError:
            return []
    except CalendarBuildError:
        return []


__all__ = [
    "get_trade_days_sse", "list_sse_trade_dates", "warmup_sse_cache",
    "invalidate_sse_cache", "mark_sse_cache_permanently_failed",
]
