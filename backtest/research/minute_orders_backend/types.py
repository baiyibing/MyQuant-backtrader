"""Immutable inputs and action evidence for research contract v0, L2-S1."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal


class MatchContractError(ValueError):
    """Malformed matching facts; never a business no-match result."""


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class MatchReason(str, Enum):
    PRICE_CROSSED = "price_crossed"
    PRICE_NOT_CROSSED = "price_not_crossed"
    ZERO_AFTER_LOT = "zero_after_lot"


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise MatchContractError(f"{name} must be a nonempty string")


def _require_int(value: int, name: str, *, minimum: int = 0) -> None:
    # bool is an int subclass, but is not an explicit share count.
    if type(value) is not int or value < minimum:
        raise MatchContractError(f"{name} must be an integer >= {minimum}")


def _require_price(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise MatchContractError(f"{name} must be a finite positive Decimal")
    # Exact cent alignment without quantizing or relying on context precision.
    _, denominator = value.as_integer_ratio()
    if 100 % denominator:
        raise MatchContractError(f"{name} must be cent-aligned; no price rounding")


@dataclass(frozen=True)
class LimitOrderMatchInput:
    """Already-qualified active LIMIT snapshot; caller owns eligibility/resources."""

    order_id: str
    symbol: str
    side: Side
    limit: Decimal
    remaining_qty: int
    lot_size: int
    order_type: Literal["LIMIT"] = "LIMIT"

    def __post_init__(self) -> None:
        _require_id(self.order_id, "order_id")
        _require_id(self.symbol, "symbol")
        if not isinstance(self.side, Side):
            raise MatchContractError("side must be Side.BUY or Side.SELL")
        if self.order_type != "LIMIT":
            raise MatchContractError("only LIMIT orders are supported")
        _require_price(self.limit, "limit")
        _require_int(self.lot_size, "lot_size", minimum=1)
        _require_int(self.remaining_qty, "remaining_qty")
        if self.remaining_qty % self.lot_size:
            raise MatchContractError("remaining_qty must be lot-aligned")


@dataclass(frozen=True)
class BucketQuote:
    """Completed [start, end) close fact, supplied only when visible at end.

    Completion, session/calendar and instrument gates are caller preconditions.
    Volume is a separate explicit input to the pure capacity helper.
    """

    symbol: str
    bucket_id: str
    start: datetime
    end: datetime
    close: Decimal

    def __post_init__(self) -> None:
        _require_id(self.symbol, "symbol")
        _require_id(self.bucket_id, "bucket_id")
        for name, value in (("start", self.start), ("end", self.end)):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise MatchContractError(f"bucket {name} must be timezone-aware")
        if self.start >= self.end:
            raise MatchContractError("bucket start must precede end")
        _require_price(self.close, "close")


@dataclass(frozen=True)
class CandidateMatch:
    """An action, NOT a fill or a claim that any resources were consumed."""

    order_id: str
    symbol: str
    side: Side
    candidate_price: Decimal
    proposed_qty: int
    bucket_id: str
    bucket_start: datetime
    bucket_end: datetime
    reason: MatchReason = field(default=MatchReason.PRICE_CROSSED, init=False)


@dataclass(frozen=True)
class NoMatch:
    order_id: str
    symbol: str
    bucket_id: str
    reason: MatchReason
