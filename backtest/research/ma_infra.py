"""Shared research moving averages; callers own cutoffs and price domains."""

from __future__ import annotations

from datetime import date, timedelta
from itertools import groupby
from math import isfinite, isnan, sqrt
from typing import Optional


def sma_asof(closes: list[float], n: int) -> Optional[float]:
    n = int(n)
    if n <= 0 or len(closes) < n:
        return None
    return sum(float(x) for x in closes[-n:]) / n


def sma_series(closes: list[float], n: int) -> list[Optional[float]]:
    """Equal-length SMA, with full windows and the seed's NaN propagation."""
    n = int(n)
    result = [None] * len(closes)
    if n <= 0 or len(closes) < n:
        return result

    # Separate nonfinite counts keep prefix sums usable after a NaN/inf exits.
    prefixes = [(0.0, 0, 0, 0)]
    total, nan_count, pos_inf, neg_inf = prefixes[0]
    for close in closes:
        value = float(close)
        if isnan(value):
            nan_count += 1
        elif value == float("inf"):
            pos_inf += 1
        elif value == -float("inf"):
            neg_inf += 1
        else:
            total += value
        prefixes.append((total, nan_count, pos_inf, neg_inf))

    for end in range(n, len(prefixes)):
        right, left = prefixes[end], prefixes[end - n]
        has_pos_inf = right[2] > left[2]
        has_neg_inf = right[3] > left[3]
        if right[1] > left[1] or (has_pos_inf and has_neg_inf):
            result[end - 1] = float("nan")
        elif has_pos_inf:
            result[end - 1] = float("inf")
        elif has_neg_inf:
            result[end - 1] = -float("inf")
        else:
            result[end - 1] = (right[0] - left[0]) / n
    return result


def sma_live(prev_closes: list[float], px: float, n: int) -> Optional[float]:
    """SMA of the last n-1 closes plus the current positive price."""
    n = int(n)
    px = float(px)
    if n <= 0 or len(prev_closes) < n - 1 or px <= 0:
        return None
    tail = list(prev_closes[-(n - 1):]) if n > 1 else []
    return sma_asof(tail + [px], n)


def bb_series(
    closes: list[float], n: int = 20, k: float = 2.0
) -> list[Optional[tuple[float, float, float]]]:
    """Full-window (middle, upper, lower) bands using sample sigma (ddof=1)."""
    n = int(n)
    result = [None] * len(closes)
    if n < 2 or len(closes) < n:
        return result

    values = [float(close) for close in closes]
    mids = sma_series(values, n)
    s1 = s2 = 0.0
    nonfinite = 0
    for i, value in enumerate(values):
        if isfinite(value):
            s1 += value
            s2 += value * value
        else:
            nonfinite += 1
        if i >= n:
            old = values[i - n]
            if isfinite(old):
                s1 -= old
                s2 -= old * old
            else:
                nonfinite -= 1
        if i >= n - 1:
            # Clamp tiny negative variances from floating-point cancellation.
            variance = (s2 - s1 * s1 / n) / (n - 1)
            sigma = float("nan") if nonfinite else sqrt(max(variance, 0.0))
            mid = mids[i]
            result[i] = (mid, mid + k * sigma, mid - k * sigma)
    return result


def bb_asof(
    closes: list[float], n: int = 20, k: float = 2.0
) -> Optional[tuple[float, float, float]]:
    """Last value of bb_series, or None for empty input."""
    series = bb_series(closes, n, k)
    return series[-1] if series else None


def daily_to_weekly(dates: list[date], closes: list[float]) -> list[tuple[date, float]]:
    """W-FRI closes keyed by the last input day, retaining the trailing week.

    Pure-Python counterpart of weekly_macd_divergence._daily_to_weekly:
    close='last' skips NaNs, _last_day='max' includes their dates, and dropna
    removes all-NaN/empty weeks. The pandas differential pins are the oracle.
    """
    weeks = {}
    for day, close in sorted(zip(dates, closes, strict=True), key=lambda row: row[0]):
        friday = day + timedelta(days=(4 - day.weekday()) % 7)
        value = float(close)
        if isnan(value):
            value = weeks.get(friday, (day, float("nan")))[1]
        weeks[friday] = (day, value)
    return [row for row in weeks.values() if not isnan(row[1])]


def weekly_sma_series(
    dates: list[date], closes: list[float], n_weeks: int, *,
    prefix_equivalent: bool = False,
) -> list[Optional[float]]:
    """Convert once, roll over observed weeks, then align backward by _last_day.

    Intermediate weeks enter at their last observed day; the final incomplete
    week enters at the input's last day. Callers must truncate inputs to D.

    Explicit ``prefix_equivalent=True`` instead recomputes each D's trailing
    week as though the input had been truncated to dates <= D first. Default
    full-history backward alignment is intentionally unchanged.
    """
    if prefix_equivalent:
        return _weekly_sma_prefix_series(dates, closes, n_weeks)
    weekly = daily_to_weekly(dates, closes)
    averages = sma_series([close for _, close in weekly], n_weeks)
    result = [None] * len(dates)
    week_index = 0
    latest = None
    for i, day in sorted(enumerate(dates), key=lambda row: row[1]):
        while week_index < len(weekly) and weekly[week_index][0] <= day:
            latest = averages[week_index]
            week_index += 1
        result[i] = latest
    return result


def _weekly_sma_prefix_series(dates, closes, n_weeks):
    """Incrementally reproduce truncate-then-call, including partial/NaN weeks.

    Maintain observed weekly closes, replacing only the current week's close.
    No future row contributes to D. Equal dates are processed together and
    results are returned in caller order, as in the default series API.
    """
    rows = sorted(enumerate(zip(dates, closes, strict=True)), key=lambda row: row[1][0])
    result = [None] * len(dates)
    weekly_closes = []
    last_observed_week = None
    for day, group in groupby(rows, key=lambda row: row[1][0]):
        day_rows = list(group)
        friday = day + timedelta(days=(4 - day.weekday()) % 7)
        for _, (_, close) in day_rows:
            value = float(close)
            if isnan(value):
                continue
            if friday == last_observed_week:
                weekly_closes[-1] = value
            else:
                weekly_closes.append(value)
                last_observed_week = friday
        average = sma_asof(weekly_closes, n_weeks)
        for i, _ in day_rows:
            result[i] = average
    return result


def weekly_sma_asof(
    dates: list[date], closes: list[float], n_weeks: int
) -> Optional[float]:
    """Last value of weekly_sma_series on caller-truncated daily inputs."""
    series = weekly_sma_series(dates, closes, n_weeks)
    return series[-1] if series else None
