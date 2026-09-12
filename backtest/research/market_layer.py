# -*- coding: utf-8 -*-
"""Shared market facts for CSV research engines.

This module is deliberately a leaf: it does not import an engine, data reader,
or strategy implementation.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

def utc_ms_range(start: str, end: str) -> tuple[int, int]:
    """Convert a closed YYYYMMDD range to UTC-midnight milliseconds."""
    first = datetime.strptime(start, "%Y%m%d").replace(tzinfo=timezone.utc)
    last = datetime.strptime(end, "%Y%m%d").replace(tzinfo=timezone.utc)
    t0 = int(first.timestamp() * 1000)
    t1 = int((last + timedelta(days=1)).timestamp() * 1000) - 1
    return t0, t1


def limit_pct(code: str) -> float:
    num = "".join(c for c in code if c.isdigit())
    if num.startswith(("300", "301", "688")):
        return 0.20
    return 0.10


def round_fen(price: float) -> float:
    """Round to one fen using decimal half-up, not banker's rounding."""
    return float(Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def limit_prices(code: str, prev_close: float) -> tuple[float, float]:
    """6/8 limit prices, preserving their Decimal-before-multiply arithmetic."""
    pct = limit_pct(code)
    prev = Decimal(str(prev_close))
    step = Decimal("0.01")
    up = (prev * (Decimal("1") + Decimal(str(pct)))).quantize(step, rounding=ROUND_HALF_UP)
    down = (prev * (Decimal("1") - Decimal(str(pct)))).quantize(step, rounding=ROUND_HALF_UP)
    return float(up), float(down)


def as_datetime(value: Any) -> datetime:
    """Parse lake epoch milliseconds/seconds, YYYYMMDD, date, or datetime."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    number: int | None = None
    if isinstance(value, bool):
        number = None
    elif isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif hasattr(value, "item"):
        inner = value.item()
        if isinstance(inner, bool):
            number = None
        elif isinstance(inner, int):
            number = inner
        elif isinstance(inner, float) and inner.is_integer():
            number = int(inner)
    if number is not None:
        if number >= 10**11:
            return datetime.fromtimestamp(number / 1000.0, tz=timezone.utc).replace(tzinfo=None)
        if number >= 10**9:
            return datetime.fromtimestamp(number, tz=timezone.utc).replace(tzinfo=None)
        if 19900101 <= number <= 21001231:
            return datetime.strptime(str(number), "%Y%m%d")
    text = str(value).strip().replace("-", "")[:8]
    return datetime.strptime(text, "%Y%m%d")


def as_date(value: Any) -> date:
    return as_datetime(value).date()
