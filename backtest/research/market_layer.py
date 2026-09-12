# -*- coding: utf-8 -*-
"""Shared market facts for CSV research engines.

This module is deliberately a leaf: it does not import an engine, data reader,
or strategy implementation.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

_ST_NAME_RE = re.compile(r"(?:\*ST|(?<![A-Za-z])ST)", re.IGNORECASE)

# ChiNext / STAR (incl. 689 CDR). Longer prefixes first.
_BOARD_20 = ("300", "301", "302", "688", "689")
# Beijing Stock Exchange. Plan E-R2: 430 / 83 / 87 / 88 / 920.
_BOARD_30 = ("920", "430", "83", "87", "88")
# Shanghai / Shenzhen main + SME. Fail-closed: anything else is unknown.
_BOARD_10 = ("600", "601", "603", "605", "000", "001", "002", "003")


def utc_ms_range(start: str, end: str) -> tuple[int, int]:
    """Convert a closed YYYYMMDD range to UTC-midnight milliseconds."""
    first = datetime.strptime(start, "%Y%m%d").replace(tzinfo=timezone.utc)
    last = datetime.strptime(end, "%Y%m%d").replace(tzinfo=timezone.utc)
    t0 = int(first.timestamp() * 1000)
    t1 = int((last + timedelta(days=1)).timestamp() * 1000) - 1
    return t0, t1


def is_st_name(name: str) -> bool:
    """True when the pool name column marks ST / *ST (not a Latin token like WEST)."""
    return bool(name and _ST_NAME_RE.search(str(name)))


def _digit_prefix(code: str) -> str:
    return "".join(c for c in str(code) if c.isdigit())


def board_limit_pct(code: str) -> Optional[float]:
    """Board-only limit ratio, or None when the prefix is not a known A-share board."""
    num = _digit_prefix(code)
    if not num:
        return None
    if num.startswith(_BOARD_20):
        return 0.20
    if num.startswith(_BOARD_30):
        return 0.30
    if num.startswith(_BOARD_10):
        return 0.10
    return None


def limit_pct(code: str, name: str = "") -> Optional[float]:
    """A-share limit ratio, or None when the board is unknown and the name is not ST.

    ST / *ST in the pool name column is 5%. Known boards without a name stay
    tradable (600 → 10%). Unknown prefixes without a name are fail-closed.
    """
    if is_st_name(name):
        return 0.05
    return board_limit_pct(code)


def round_fen(price: float) -> float:
    """Round to one fen using decimal half-up, not banker's rounding."""
    return float(Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def limit_prices(
    code: str, prev_close: float, name: str = ""
) -> Optional[tuple[float, float]]:
    """昨收 × (1±档) 先 Decimal 再 HALF_UP 到分。未知板块返回 None。"""
    pct = limit_pct(code, name)
    if pct is None:
        return None
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
