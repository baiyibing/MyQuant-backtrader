"""Immutable action, accounting and explicit replay values for research v0."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, IntEnum
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


class LedgerError(ValueError):
    """Malformed accounting command, stale proposal or conflicting identity."""


class FeeContractError(LedgerError):
    """Invalid explicit fee parameters or an unavailable reservation bound."""


@dataclass(frozen=True)
class FeeModelParams:
    rate: Decimal
    min_fee: Decimal
    rounding: str


@dataclass(frozen=True)
class LotPosition:
    lot_id: str
    symbol: str
    acquire_date: date
    sellable_date: date
    qty: int
    lot_size: int
    reserved_qty: int = 0

    @property
    def free_qty(self) -> int:
        return self.qty - self.reserved_qty


@dataclass(frozen=True)
class LotAllocation:
    lot_id: str
    qty: int


@dataclass(frozen=True)
class Reservation:
    order_id: str
    symbol: str
    side: Side
    limit: Decimal
    remaining_qty: int
    lot_size: int
    cash: Decimal
    fee_upper: Decimal
    lots: tuple[LotAllocation, ...] = ()


class ResourceRejectReason(str, Enum):
    INSUFFICIENT_CASH = "insufficient_cash"
    INSUFFICIENT_SELLABLE = "insufficient_sellable"


@dataclass(frozen=True)
class ReservationRejected:
    order_id: str
    reason: ResourceRejectReason
    required: Decimal | int
    available: Decimal | int


@dataclass(frozen=True)
class OrderTotals:
    order_id: str
    side: Side
    notional: Decimal
    fees_paid: Decimal


@dataclass(frozen=True)
class BucketCapacity:
    symbol: str
    bucket_id: str
    trade_date: date
    lot_size: int
    capacity: int
    remaining: int


@dataclass(frozen=True)
class FillProposal:
    """Explicit economic command; never implicitly constructed from an action."""

    fill_id: str
    order_id: str
    symbol: str
    side: Side
    qty: int
    price: Decimal
    fee_delta: Decimal
    bucket_id: str
    capacity_consumed: int
    lot_size: int
    trade_date: date
    sellable_date: date | None
    expected_version: int


@dataclass(frozen=True)
class FillApplied:
    proposal: FillProposal
    ledger_version: int
    duplicate: bool = False


@dataclass(frozen=True)
class LedgerSnapshot:
    cash: Decimal
    reserved_cash: Decimal
    free_cash: Decimal
    lots: tuple[LotPosition, ...]
    reservations: tuple[Reservation, ...]
    order_totals: tuple[OrderTotals, ...]
    buckets: tuple[BucketCapacity, ...]
    applied_fills: tuple[FillApplied, ...]
    used_order_ids: frozenset[str]
    ledger_version: int
    fees_paid: Decimal

    @property
    def applied_fill_ids(self) -> frozenset[str]:
        return frozenset(item.proposal.fill_id for item in self.applied_fills)

    def reserved_sellable_qty(self, symbol: str) -> int:
        return sum(lot.reserved_qty for lot in self.lots if lot.symbol == symbol)


class RunContractError(ValueError):
    """Invalid replay facts; abort instead of returning a successful result."""


class Phase(IntEnum):
    # BUCKET is the visibility/registration step of the match phase, not a fill.
    EXPIRY = 0
    CANCEL = 1
    BUCKET = 2
    MATCH = 3
    SUBMIT = 4
    MARK = 5


class OrderStatus(str, Enum):
    SUBMITTED = "Submitted"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"


@dataclass(frozen=True)
class SubmitOrder:
    command_id: str
    order_id: str
    symbol: str
    side: Side
    qty: int
    limit: Decimal
    available_at: datetime
    submitted_at: datetime
    effective_at: datetime
    expires_at: datetime
    sequence: int
    order_type: Literal["LIMIT"] = "LIMIT"


@dataclass(frozen=True)
class CancelOrder:
    command_id: str
    order_id: str
    available_at: datetime
    submitted_at: datetime
    effective_at: datetime
    sequence: int


@dataclass(frozen=True)
class SessionBucket:
    bucket_id: str
    start: datetime
    end: datetime
    session: Literal["continuous"]


@dataclass(frozen=True)
class CalendarFacts:
    """Caller-attested dates and exact buckets covered by this bounded replay."""

    trading_dates: tuple[date, ...]
    session_buckets: tuple[SessionBucket, ...]
    company_actions_covered: bool
    company_actions: tuple[object, ...]


@dataclass(frozen=True)
class InstrumentFacts:
    symbol: str
    trade_date: date
    board: Literal["main"]
    price_domain: Literal["raw"]
    tick_size: Decimal
    lot_size: int
    reference_price: Decimal
    limit_down: Decimal
    limit_up: Decimal


@dataclass(frozen=True)
class CompletedBucket:
    """One calendar bucket's symbol coverage, including explicit missing/halt facts.

    A missing bucket has close=volume_shares=None. A present bucket (including
    a halted one) must supply both. Neither field is released before end.
    """

    symbol: str
    bucket_id: str
    start: datetime
    end: datetime
    close: Decimal | None
    volume_shares: int | None
    missing: bool
    halted: bool


@dataclass(frozen=True)
class MarkPrice:
    symbol: str
    price: Decimal


@dataclass(frozen=True)
class MarkEvent:
    mark_id: str
    event_time: datetime
    available_at: datetime
    prices: tuple[MarkPrice, ...]
    price_domain: Literal["raw"]
    source: str


@dataclass(frozen=True)
class RunInput:
    start_at: datetime
    end_at: datetime
    commands: tuple[SubmitOrder | CancelOrder, ...]
    buckets: tuple[CompletedBucket, ...]
    calendar: CalendarFacts
    instruments: tuple[InstrumentFacts, ...]
    initial_cash: Decimal
    initial_lots: tuple[LotPosition, ...]
    buy_fees: FeeModelParams
    sell_fees: FeeModelParams
    participation_rate: Decimal
    marks: tuple[MarkEvent, ...]
    requires_marks: bool


@dataclass(frozen=True)
class ClockEvent:
    event_time: datetime
    phase: Phase
    sell_before_buy: int
    submitted_at: datetime
    sequence: int
    order_id: str
    payload: SubmitOrder | CancelOrder | CompletedBucket | MarkEvent

    @property
    def key(self) -> tuple:
        return (
            self.event_time, int(self.phase), self.sell_before_buy,
            self.submitted_at, self.sequence, self.order_id,
        )


@dataclass(frozen=True)
class OrderState:
    order: SubmitOrder
    status: OrderStatus
    filled_qty: int
    remaining_qty: int
    rejection: ReservationRejected | None = None


@dataclass(frozen=True)
class OrderTransition:
    event: ClockEvent
    state: OrderState
    # S4 opt-in observation only; the ordinary S3 replay leaves this unavailable.
    ledger: LedgerSnapshot | None = None


@dataclass(frozen=True)
class MarkObservation:
    event: MarkEvent
    ledger: LedgerSnapshot


@dataclass(frozen=True)
class RunResult:
    orders: tuple[OrderState, ...]
    fills: tuple[FillApplied, ...]
    ledger: LedgerSnapshot
    transitions: tuple[OrderTransition, ...]
    marks: tuple[MarkObservation, ...]
