"""Opt-in first-buy TWAP primitives; no data reads or account mutation.

Parents are fixed at the exact 14:30 open. Children use completed minute bars;
neither missed children nor integer-lot residuals are redistributed. Volume
defaults to the lake's shares unit; callers can select lots (100 shares).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite

TAIL_START = 14 * 60 + 30
TAIL_MINUTES = tuple(range(TAIL_START, 14 * 60 + 57)) + (15 * 60,)


def resolve_tail_volume_unit(volume_unit: str | None = None) -> str:
    """Default missing units to shares; reject all other non-contract values."""
    if volume_unit is None:
        return "shares"
    if volume_unit not in ("shares", "lots"):
        raise ValueError("tail volume unit (--tail-volume-unit) must be shares or lots")
    return volume_unit


def validate_tail_options(enabled, fix_minute_cash_order, volume_unit):
    if not enabled:
        return
    if not fix_minute_cash_order:
        raise ValueError("--tail-window-buy requires --fix-minute-cash-order")
    resolve_tail_volume_unit(volume_unit)


@dataclass(frozen=True)
class TailQuote:
    price: float
    capacity: int


def tail_quote(row, hm: int, volume_unit: str | None = "shares") -> TailQuote | None:
    """A whole completed bucket, with amount in yuan and volume defaulting to shares.

    Missing/invalid volume or a present invalid amount rejects this child.
    The 15:00 auction uses close regardless of amount. No fallback quote or
    continuous matching is allowed during 14:57–14:59.
    """
    volume_unit = resolve_tail_volume_unit(volume_unit)
    if hm not in TAIL_MINUTES or row is None:
        return None
    try:
        volume = Decimal(str(row.get("volume")))
        if not volume.is_finite() or volume <= 0:
            return None
        shares = volume * (100 if volume_unit == "lots" else 1)
        if shares != shares.to_integral_value():
            return None
        capacity = int(shares) // 10 // 100 * 100
        if hm != 900 and "amount" in row:
            amount = float(row["amount"])
            if not isfinite(amount) or amount <= 0:
                return None
            price = amount / float(shares)
        else:
            price = float(row["close"])
    except (TypeError, ValueError, KeyError, InvalidOperation, OverflowError):
        return None
    if not isfinite(price) or price <= 0:
        return None
    return TailQuote(price, capacity)


def affordable_shares(wanted: int, price: float, cash: float, debit_fn) -> int:
    """Largest 100-share child payable now, including its own minimum fee."""
    if not isfinite(price) or price <= 0 or not isfinite(cash) or cash <= 0:
        return 0
    lo, hi = 0, max(0, int(wanted)) // 100
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if debit_fn(mid * 100 * price) <= cash:
            lo = mid
        else:
            hi = mid - 1
    return lo * 100


@dataclass
class TailParent:
    target_shares: int
    slice_shares: int
    budget: float
    filled_shares: int = 0
    spent: float = 0.0

    @classmethod
    def from_budget(cls, budget: float, price: float) -> TailParent:
        if not isfinite(budget) or budget < 0 or not isfinite(price) or price <= 0:
            raise ValueError("tail parent requires a finite budget and positive 14:30 open")
        # Decimal prevents a mathematically exact hand from losing one share
        # due to binary division. Every child has exactly the same planned size.
        target = int(Decimal(str(budget)) / Decimal(str(price)) / 100) * 100
        return cls(target, target // len(TAIL_MINUTES) // 100 * 100, float(budget))

    def requested_shares(self, quote: TailQuote) -> int:
        """Apply slice, market capacity and nominal budget limits, never cash."""
        wanted = min(self.slice_shares, quote.capacity,
                     self.target_shares - self.filled_shares)
        # Rising prices must not enlarge the original strategy's notional
        # allocation. Fees remain an additional cash constraint, as in ledger.
        return affordable_shares(wanted, quote.price,
                                 max(0.0, self.budget - self.spent), lambda x: x)

    def allocation(self, quote: TailQuote, cash: float, debit_fn) -> int:
        """Non-strict books size each child against cash available right now."""
        return affordable_shares(self.requested_shares(quote), quote.price, cash, debit_fn)

    def opening_debit(self, price: float, debit_fn) -> float:
        """Known-price funding check; no cash reservation or future quotes.

        Retain the whole target requirement, including discarded lot residuals,
        and account for each actual child's minimum fee separately.
        """
        whole = debit_fn(self.target_shares * price) if self.target_shares else 0.0
        children = len(TAIL_MINUTES) * debit_fn(self.slice_shares * price) if self.slice_shares else 0.0
        return max(whole, children)

    def book(self, shares: int, price: float) -> None:
        self.filled_shares += shares
        self.spent += shares * price


def tail_policy(volume_unit: str | None = "shares") -> dict:
    """Outer run/manifest metadata; never add keys to OFF simulation stats."""
    return {
        "tail_window_buy": True,
        "tail_volume_unit": resolve_tail_volume_unit(volume_unit),
        "tail_parent_clock": "14:30_open_exact",
        "tail_slice_count": len(TAIL_MINUTES),
        "tail_continuous_minutes": "14:30-14:56_close",
        "tail_auction_minute": "15:00_close",
        "tail_participation_rate": 0.1,
        "tail_residual_policy": "floor_100_each_child_no_carry_day_expiry",
        "tail_pool_availability": "caller_attests_known_before_14:30",
        "tail_volume_contract": "caller_attested_incremental_raw_volume_amount_yuan",
    }
