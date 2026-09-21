"""Caller-supplied ex-date entitlements; independent of E-R6 reference ratios.

No loaders, inferred events, fees or market fills. Amounts are gross/pre-tax;
integer bonus shares are floored per existing lot (fractions are discarded).
An event_id must be unique across symbols within a run. Revisions/replay across
runs and record-date eligibility are outside this cut.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from math import isfinite


@dataclass(frozen=True)
class ExDivEvent:
    event_id: str
    bonus_ratio: float | Decimal
    cash_div_per_share: float | Decimal
    ex_date: str
    pay_date: str
    list_date: str | None = None


EconomicLookup = Mapping[tuple[str, str], ExDivEvent | None] | Callable[
    [str, str], ExDivEvent | None
]


@dataclass(frozen=True)
class CashReceivable:
    pay_date: str
    amount: float


@dataclass(frozen=True)
class Entitlement:
    bonus_shares: tuple[int, ...]
    list_date: str


def _date(value: str) -> str:
    if not isinstance(value, str) or len(value) != 8 or not value.isascii() or not value.isdigit():
        raise ValueError("event dates must be YYYYMMDD")
    datetime.strptime(value, "%Y%m%d")
    return value


def _ratio(value: float | Decimal) -> tuple[int, int]:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("event amounts must be numeric")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError("event amounts must be finite and nonnegative")
    return number.as_integer_ratio()


class ExDivEconomics:
    """One run's dedup/receivable ledger, mounted only for an explicit lookup.

    Missing lookups are normal; untyped/invalid events are skipped with a
    counter. Unexpected exceptions from a caller's callback propagate.
    Settlement uses the first simulated session on/after pay_date, even when
    the symbol has no bars or its position has already been sold.
    """

    def __init__(self, lookup: EconomicLookup, stats: dict | None = None):
        self.lookup = lookup
        self.stats = stats if stats is not None else {}
        self.applied_ids: set[str] = set()
        self.receivables: dict[str, CashReceivable] = {}
        self.bonus_locks: dict[int, dict[str, int]] = {}  # book lot identity -> list-date quantities

    @property
    def receivable_total(self) -> float:
        return sum(item.amount for item in self.receivables.values())

    def _count(self, name: str, value: int | float = 1) -> None:
        key = "exdiv_econ_" + name
        self.stats[key] = self.stats.get(key, 0) + value

    def entitle(self, symbol: str, ds: str, quantities: Sequence[int], *,
                on_event: Callable[[ExDivEvent], None] | None = None) -> Entitlement | None:
        """Snapshot all pre-scan lots together; no share/cost mutations here."""
        if not callable(self.lookup) and not isinstance(self.lookup, Mapping):
            self._count("invalid_event")
            return None
        try:
            event = (self.lookup(symbol, ds) if callable(self.lookup)
                     else self.lookup.get((symbol, ds)))
        except LookupError:
            event = None
        if event is None:
            return None
        try:
            if not isinstance(event, ExDivEvent) or not isinstance(event.event_id, str) or not event.event_id.strip():
                raise ValueError("typed event with nonempty id required")
            ex_date, pay_date = _date(event.ex_date), _date(event.pay_date)
            list_date = _date(event.list_date if event.list_date is not None else ex_date)
            if ex_date != ds or pay_date < ex_date or list_date < ex_date:
                raise ValueError("event dates out of order or lookup day mismatch")
            bn, bd = _ratio(event.bonus_ratio)
            cn, cd = _ratio(event.cash_div_per_share)
            additions = tuple(q * bn // bd for q in quantities)
            gross = sum(quantities) * cn / cd
            if not isfinite(gross):
                raise ValueError("cash entitlement overflow")
        except (ValueError, TypeError, InvalidOperation, OverflowError):
            self._count("invalid_event")
            return None
        if event.event_id in self.applied_ids:
            self._count("duplicate_event")
            return None
        if not quantities and on_event is None:
            return None
        self.applied_ids.add(event.event_id)
        if gross:
            self.receivables[event.event_id] = CashReceivable(pay_date, gross)
        self._count("events")
        self._count("bonus_shares", sum(additions))
        self._count("cash_entitled", gross)
        self.stats["exdiv_econ_receivable_open"] = self.receivable_total
        if on_event is not None:
            on_event(event)  # Validated, deduplicated; also covers flat buyback memory.
        return Entitlement(additions, list_date)

    def settle(self, ds: str) -> float:
        """Remove due receivables once; caller credits this amount to cash."""
        due = [key for key, item in self.receivables.items() if item.pay_date <= ds]
        amount = sum(self.receivables.pop(key).amount for key in due)
        if due:
            self._count("cash_posted", amount)
            self.stats["exdiv_econ_receivable_open"] = self.receivable_total
        return amount
