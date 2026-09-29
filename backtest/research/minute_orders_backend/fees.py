"""Pure, explicitly configured cumulative fees; no account mutation.

Only this monotone model is supported in S2. No arbitrary model can claim a
reservation bound, and no production rate or rounding rule is inherited.
"""

from dataclasses import dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Context,
    Decimal,
    DecimalException,
    localcontext,
)

from .types import FeeContractError, FeeModelParams, Side


def _cents(value: Decimal, name: str) -> int:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise FeeContractError(f"{name} must be a finite nonnegative Decimal")
    numerator, denominator = value.as_integer_ratio()
    cents, remainder = divmod(numerator * 100, denominator)
    if remainder:
        raise FeeContractError(f"{name} must be cent-aligned; no implicit rounding")
    return cents


def _money(cents: int) -> Decimal:
    """Exact cents -> Decimal, independent of the caller's decimal context."""
    return Decimal((int(cents < 0), tuple(map(int, str(abs(cents)))), -2))


_MONOTONE_ROUNDING = frozenset(
    {
        ROUND_CEILING,
        ROUND_DOWN,
        ROUND_FLOOR,
        ROUND_HALF_DOWN,
        ROUND_HALF_EVEN,
        ROUND_HALF_UP,
        ROUND_UP,
    }
)


def _validate_params(params: FeeModelParams) -> None:
    if type(params) is not FeeModelParams:
        raise FeeContractError("explicit FeeModelParams required for each side")
    if not isinstance(params.rate, Decimal) or not params.rate.is_finite() or params.rate < 0:
        raise FeeContractError("rate must be a finite nonnegative Decimal")
    _cents(params.min_fee, "min_fee")
    if not isinstance(params.rounding, str) or params.rounding not in _MONOTONE_ROUNDING:
        raise FeeContractError("rounding must provide a monotone cent fee bound")


@dataclass(frozen=True)
class FeeModel:
    """F(0)=0; F(N>0)=quantize(max(min_fee, N*rate), cent, rounding).

    BUY and SELL parameters are independent and mandatory. Ledger validates fee
    proposals against this same immutable configuration, but owns all payments.
    """

    buy: FeeModelParams
    sell: FeeModelParams

    def __post_init__(self) -> None:
        _validate_params(self.buy)
        _validate_params(self.sell)

    def cumulative_fee(self, side: Side, notional: Decimal) -> Decimal:
        if not isinstance(side, Side):
            raise FeeContractError("side must be Side.BUY or Side.SELL")
        cents = _cents(notional, "notional")
        if cents == 0:
            return Decimal("0.00")
        params = self.buy if side is Side.BUY else self.sell
        # Enough coefficient digits for an exact product, plus enough integer
        # digits to quantize to cents. Do not inherit precision, traps or rounding.
        precision = max(
            28,
            len(notional.as_tuple().digits) + len(params.rate.as_tuple().digits),
            notional.adjusted() + params.rate.adjusted() + 4,
            params.min_fee.adjusted() + 4,
        )
        try:
            with localcontext(Context(prec=precision, rounding=params.rounding)):
                return max(params.min_fee, notional * params.rate).quantize(Decimal("0.01"))
        except DecimalException as exc:
            raise FeeContractError("fee arithmetic cannot provide a valid bound") from exc

    def fee_delta(self, side: Side, before: Decimal, after: Decimal) -> Decimal:
        if _cents(after, "after") < _cents(before, "before"):
            raise FeeContractError("cumulative notional cannot decrease")
        delta = _cents(self.cumulative_fee(side, after), "fee_after") - _cents(
            self.cumulative_fee(side, before), "fee_before"
        )
        if delta < 0:
            raise FeeContractError("fee model is not monotone")
        return _money(delta)

    def buy_fee_upper_bound(
        self, paid_notional: Decimal, limit: Decimal, remaining_qty: int
    ) -> Decimal:
        paid = _cents(paid_notional, "paid_notional")
        price = _cents(limit, "limit")
        if price == 0:
            raise FeeContractError("limit must be positive")
        if type(remaining_qty) is not int or remaining_qty < 0:
            raise FeeContractError("remaining_qty must be a nonnegative integer")
        return self.fee_delta(Side.BUY, paid_notional, _money(paid + price * remaining_qty))
