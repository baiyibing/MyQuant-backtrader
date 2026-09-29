"""Pure completed_bucket_close actions; no capacity or account state owner."""

from decimal import Decimal

from .types import (
    BucketQuote,
    CandidateMatch,
    LimitOrderMatchInput,
    MatchContractError,
    MatchReason,
    NoMatch,
    Side,
    _require_int,
)


def compute_bucket_capacity(
    lot_size: int, volume_shares: int, participation_rate: Decimal
) -> int:
    """Return L * floor(p * V / L), with explicit shares and 0 <= p <= 1.

    Decimal's exact integer ratio avoids a rounded intermediate multiplication
    crossing a lot boundary under the caller's Decimal context. No state changes.
    """
    _require_int(lot_size, "lot_size", minimum=1)
    _require_int(volume_shares, "volume_shares")
    if (
        not isinstance(participation_rate, Decimal)
        or not participation_rate.is_finite()
        or not Decimal(0) <= participation_rate <= Decimal(1)
    ):
        raise MatchContractError("participation_rate must be a finite Decimal in [0, 1]")
    numerator, denominator = participation_rate.as_integer_ratio()
    return lot_size * (numerator * volume_shares // (denominator * lot_size))


def match_candidates(
    order: LimitOrderMatchInput,
    quote: BucketQuote,
    *,
    capacity_remaining: int,
) -> CandidateMatch | NoMatch:
    """Propose one action for an already-qualified order and completed bucket.

    Caller supplies the shared remaining capacity for this symbol+bucket, after
    prior committed consumption on either side. This function neither remembers
    earlier calls nor reserves/deducts capacity. Reusing a proposal is NOT a fill.
    Eligibility, reservation sufficiency and all scheduling remain outside S1.
    """
    if not isinstance(order, LimitOrderMatchInput):
        raise MatchContractError("order must be a LimitOrderMatchInput")
    if not isinstance(quote, BucketQuote):
        raise MatchContractError("quote must be a BucketQuote")
    _require_int(capacity_remaining, "capacity_remaining")
    if order.symbol != quote.symbol:
        raise MatchContractError("order and bucket symbols must match")

    crossed = (
        quote.close <= order.limit
        if order.side is Side.BUY
        else quote.close >= order.limit
    )
    if not crossed:
        return NoMatch(
            order.order_id, order.symbol, quote.bucket_id, MatchReason.PRICE_NOT_CROSSED
        )

    proposed_qty = (
        min(order.remaining_qty, capacity_remaining) // order.lot_size * order.lot_size
    )
    if proposed_qty == 0:
        return NoMatch(
            order.order_id, order.symbol, quote.bucket_id, MatchReason.ZERO_AFTER_LOT
        )
    return CandidateMatch(
        order_id=order.order_id,
        symbol=order.symbol,
        side=order.side,
        candidate_price=quote.close,
        proposed_qty=proposed_qty,
        bucket_id=quote.bucket_id,
        bucket_start=quote.start,
        bucket_end=quote.end,
    )
