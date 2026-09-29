"""Single resource owner for explicit S2 commands, without event scheduling.

All values in the committed snapshot are immutable. Each command prepares a
replacement snapshot and publishes it once; exceptions leave the old state
intact. This is a single-process accounting core, not a concurrent broker.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from .fees import FeeModel, money_cents, from_cents
from .types import (
    BucketCapacity,
    FillApplied,
    FillProposal,
    LedgerError,
    LedgerSnapshot,
    LotAllocation,
    LotPosition,
    OrderTotals,
    Reservation,
    ReservationRejected,
    ResourceRejectReason,
    Side,
)

_ZERO = Decimal("0.00")


def _id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"{name} must be a nonempty string")


def _integer(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise LedgerError(f"{name} must be an integer >= {minimum}")


def _date(value: date, name: str) -> None:
    if type(value) is not date:
        raise LedgerError(f"{name} must be an explicit date, not a timestamp")


def _quantity(qty: int, lot_size: int) -> None:
    _integer(lot_size, "lot_size", 1)
    _integer(qty, "qty", 1)
    if qty % lot_size:
        raise LedgerError("qty must be lot-aligned")


class Ledger:
    def __init__(
        self, initial_cash: Decimal, initial_lots: list[LotPosition], *, fee_model: FeeModel
    ) -> None:
        cash = from_cents(money_cents(initial_cash, "initial_cash"))
        if type(fee_model) is not FeeModel:
            raise LedgerError("only the explicit monotone FeeModel is supported")
        if not isinstance(initial_lots, (list, tuple)):
            raise LedgerError("initial_lots must be an explicit list or tuple")
        lots = tuple(initial_lots)
        for lot in lots:
            if type(lot) is not LotPosition:
                raise LedgerError("initial_lots must contain LotPosition values")
            _id(lot.lot_id, "lot_id")
            _id(lot.symbol, "symbol")
            _quantity(lot.qty, lot.lot_size)
            _date(lot.acquire_date, "acquire_date")
            _date(lot.sellable_date, "sellable_date")
            if lot.sellable_date <= lot.acquire_date:
                raise LedgerError("lot sellable_date must follow acquire_date")
            if type(lot.reserved_qty) is not int or lot.reserved_qty != 0:
                raise LedgerError("initial lots must be entirely unreserved")
        if len({lot.lot_id for lot in lots}) != len(lots):
            raise LedgerError("duplicate initial lot_id")
        for symbol in {lot.symbol for lot in lots}:
            if len({lot.lot_size for lot in lots if lot.symbol == symbol}) != 1:
                raise LedgerError("inconsistent lot_size for symbol")
        self._fee_model = fee_model
        self._state = LedgerSnapshot(cash, _ZERO, cash, lots, (), (), (), (), frozenset(), 0, _ZERO)

    def snapshot(self) -> LedgerSnapshot:
        return self._state

    def _commit(self, **changes) -> LedgerSnapshot:
        candidate = replace(self._state, **changes, ledger_version=self._state.ledger_version + 1)
        reserved = sum(money_cents(r.cash, "reservation cash") for r in candidate.reservations)
        cash = money_cents(candidate.cash, "cash")
        if cash < reserved:
            raise LedgerError("fill would spend another order's reserved cash")
        candidate = replace(
            candidate, reserved_cash=from_cents(reserved), free_cash=from_cents(cash - reserved)
        )
        self._state = candidate
        return candidate

    def _symbol_lot(self, symbol: str, lot_size: int) -> None:
        _id(symbol, "symbol")
        _integer(lot_size, "lot_size", 1)
        existing = [x.lot_size for x in self._state.lots if x.symbol == symbol]
        existing += [x.lot_size for x in self._state.reservations if x.symbol == symbol]
        existing += [x.lot_size for x in self._state.buckets if x.symbol == symbol]
        if any(size != lot_size for size in existing):
            raise LedgerError("inconsistent lot_size for symbol")

    def _new_order(
        self, order_id: str, symbol: str, limit: Decimal, qty: int, lot_size: int
    ) -> None:
        _id(order_id, "order_id")
        if order_id in self._state.used_order_ids:
            raise LedgerError("order_id already used; a new submit needs a new ID")
        self._symbol_lot(symbol, lot_size)
        _quantity(qty, lot_size)
        if money_cents(limit, "limit") == 0:
            raise LedgerError("limit must be positive")

    def _reserve(
        self, reservation: Reservation, *, lots: tuple[LotPosition, ...] | None = None
    ) -> Reservation:
        self._commit(
            reservations=self._state.reservations + (reservation,),
            lots=self._state.lots if lots is None else lots,
            order_totals=self._state.order_totals
            + (OrderTotals(reservation.order_id, reservation.side, _ZERO, _ZERO),),
            used_order_ids=self._state.used_order_ids | {reservation.order_id},
        )
        return reservation

    def _reject(
        self,
        order_id: str,
        reason: ResourceRejectReason,
        required: Decimal | int,
        available: Decimal | int,
    ) -> ReservationRejected:
        result = ReservationRejected(order_id, reason, required, available)
        # Identity only: no pending order, resource claim, resizing or revival.
        self._commit(used_order_ids=self._state.used_order_ids | {order_id})
        return result

    def reserve_buy(
        self,
        order_id: str,
        *,
        symbol: str,
        limit: Decimal,
        remaining_qty: int,
        lot_size: int,
        fee_upper: Decimal,
    ) -> Reservation | ReservationRejected:
        self._new_order(order_id, symbol, limit, remaining_qty, lot_size)
        upper = money_cents(fee_upper, "fee_upper")
        expected = self._fee_model.buy_fee_upper_bound(_ZERO, limit, remaining_qty)
        if fee_upper != expected:
            raise LedgerError("fee_upper must equal the configured model's bound")
        required = from_cents(money_cents(limit, "limit") * remaining_qty + upper)
        if required > self._state.free_cash:
            return self._reject(
                order_id, ResourceRejectReason.INSUFFICIENT_CASH, required, self._state.free_cash
            )
        return self._reserve(
            Reservation(
                order_id, symbol, Side.BUY, limit, remaining_qty, lot_size, required, fee_upper
            )
        )

    def reserve_sell(
        self,
        order_id: str,
        *,
        symbol: str,
        limit: Decimal,
        qty: int,
        lot_size: int,
        trade_date: date,
    ) -> Reservation | ReservationRejected:
        self._new_order(order_id, symbol, limit, qty, lot_size)
        _date(trade_date, "trade_date")
        eligible = sorted(
            (
                lot
                for lot in self._state.lots
                if lot.symbol == symbol and lot.sellable_date <= trade_date
            ),
            key=lambda lot: (lot.acquire_date, lot.lot_id),
        )
        available = sum(lot.free_qty for lot in eligible)
        if qty > available:
            return self._reject(
                order_id, ResourceRejectReason.INSUFFICIENT_SELLABLE, qty, available
            )
        remaining = qty
        allocations = []
        for lot in eligible:
            take = min(remaining, lot.free_qty)
            if take:
                allocations.append(LotAllocation(lot.lot_id, take))
                remaining -= take
        amounts = {a.lot_id: a.qty for a in allocations}
        lots = tuple(
            replace(lot, reserved_qty=lot.reserved_qty + amounts.get(lot.lot_id, 0))
            for lot in self._state.lots
        )
        return self._reserve(
            Reservation(
                order_id, symbol, Side.SELL, limit, qty, lot_size, _ZERO, _ZERO, tuple(allocations)
            ),
            lots=lots,
        )

    def _reservation(self, order_id: str, side: Side) -> Reservation:
        _id(order_id, "order_id")
        reservation = next((r for r in self._state.reservations if r.order_id == order_id), None)
        if reservation is None or reservation.side is not side:
            raise LedgerError("no active reservation for this order and side")
        return reservation

    def _release(self, order_id: str, side: Side) -> Reservation:
        reservation = self._reservation(order_id, side)
        amounts = {a.lot_id: a.qty for a in reservation.lots}
        lots = tuple(
            replace(lot, reserved_qty=lot.reserved_qty - amounts.get(lot.lot_id, 0))
            for lot in self._state.lots
        )
        self._commit(
            lots=lots,
            reservations=tuple(r for r in self._state.reservations if r.order_id != order_id),
        )
        return reservation

    def release_buy(self, order_id: str) -> Reservation:
        """Release all remaining resources; paid fees and fills are unchanged."""
        return self._release(order_id, Side.BUY)

    def release_sell(self, order_id: str) -> Reservation:
        return self._release(order_id, Side.SELL)

    def register_bucket(
        self,
        *,
        symbol: str,
        bucket_id: str,
        trade_date: date,
        lot_size: int,
        capacity: int,
    ) -> BucketCapacity:
        """Install explicit capacity once; repeat registration cannot refill it."""
        self._symbol_lot(symbol, lot_size)
        _id(bucket_id, "bucket_id")
        _date(trade_date, "trade_date")
        _integer(capacity, "capacity")
        if capacity % lot_size:
            raise LedgerError("initial bucket capacity must be lot-aligned")
        existing = next(
            (b for b in self._state.buckets if (b.symbol, b.bucket_id) == (symbol, bucket_id)), None
        )
        bucket = BucketCapacity(symbol, bucket_id, trade_date, lot_size, capacity, capacity)
        if existing is not None:
            if replace(existing, remaining=existing.capacity) != bucket:
                raise LedgerError("conflicting symbol+bucket capacity facts")
            return existing
        self._commit(buckets=self._state.buckets + (bucket,))
        return bucket

    def _validate_fill(self, p: FillProposal) -> None:
        _id(p.fill_id, "fill_id")
        _id(p.order_id, "order_id")
        _id(p.symbol, "symbol")
        _id(p.bucket_id, "bucket_id")
        if not isinstance(p.side, Side):
            raise LedgerError("side must be Side.BUY or Side.SELL")
        _quantity(p.qty, p.lot_size)
        _integer(p.capacity_consumed, "capacity_consumed", 1)
        if p.capacity_consumed != p.qty:
            raise LedgerError("capacity consumption must equal absolute fill qty")
        if money_cents(p.price, "price") == 0:
            raise LedgerError("price must be positive")
        money_cents(p.fee_delta, "fee_delta")
        _integer(p.expected_version, "expected_version")
        _date(p.trade_date, "trade_date")
        if p.side is Side.BUY:
            _date(p.sellable_date, "sellable_date")
            if p.sellable_date <= p.trade_date:
                raise LedgerError("BUY needs an explicit later sellable trading date")
        elif p.sellable_date is not None:
            raise LedgerError("SELL must not specify a new sellable_date")

    def apply_fill(self, proposal: FillProposal) -> FillApplied:
        if type(proposal) is not FillProposal:
            raise LedgerError("only an explicit FillProposal can be applied")
        p = proposal
        self._validate_fill(p)
        for applied in self._state.applied_fills:
            if applied.proposal.fill_id == p.fill_id:
                if applied.proposal != p:
                    raise LedgerError("fill_id conflict: different payload")
                return replace(applied, duplicate=True)
        if p.expected_version != self._state.ledger_version:
            raise LedgerError("stale ledger version")
        reservation = self._reservation(p.order_id, p.side)
        if reservation.symbol != p.symbol or reservation.lot_size != p.lot_size:
            raise LedgerError("fill differs from reserved symbol or lot_size")
        if p.qty > reservation.remaining_qty:
            raise LedgerError("fill exceeds reserved remaining qty")
        if (p.side is Side.BUY and p.price > reservation.limit) or (
            p.side is Side.SELL and p.price < reservation.limit
        ):
            raise LedgerError("fill price does not cross reserved limit")
        bucket = next(
            (b for b in self._state.buckets if (b.symbol, b.bucket_id) == (p.symbol, p.bucket_id)),
            None,
        )
        if bucket is None or bucket.trade_date != p.trade_date or bucket.lot_size != p.lot_size:
            raise LedgerError("missing or inconsistent registered bucket")
        if bucket.remaining < p.qty:
            raise LedgerError("insufficient shared bucket capacity")
        totals = next(t for t in self._state.order_totals if t.order_id == p.order_id)
        notional = money_cents(p.price, "price") * p.qty
        after = from_cents(money_cents(totals.notional, "notional") + notional)
        expected_fee = self._fee_model.fee_delta(p.side, totals.notional, after)
        if p.fee_delta != expected_fee:
            raise LedgerError("fee_delta differs from configured cumulative fee")
        fee = money_cents(p.fee_delta, "fee_delta")
        remaining = reservation.remaining_qty - p.qty
        cash = money_cents(self._state.cash, "cash")
        lots = self._state.lots
        if p.side is Side.BUY:
            fee_upper = self._fee_model.buy_fee_upper_bound(after, reservation.limit, remaining)
            remaining_cash = money_cents(reservation.limit, "limit") * remaining + money_cents(
                fee_upper, "fee_upper"
            )
            if notional + fee + remaining_cash > money_cents(reservation.cash, "reserved cash"):
                raise LedgerError("BUY exceeds its reserved cash including remainder")
            lot_id = "fill:" + p.fill_id
            if any(lot.lot_id == lot_id for lot in lots):
                raise LedgerError("BUY lot_id conflicts with an existing lot")
            lots += (
                LotPosition(lot_id, p.symbol, p.trade_date, p.sellable_date, p.qty, p.lot_size),
            )
            cash -= notional + fee
            updated = replace(
                reservation,
                remaining_qty=remaining,
                cash=from_cents(remaining_cash),
                fee_upper=fee_upper,
            )
        else:
            lots, allocations = self._consume_sell(reservation, p)
            cash += notional - fee
            updated = replace(reservation, remaining_qty=remaining, lots=allocations)
        if cash < 0:
            raise LedgerError("fill would make cash negative")
        reservations = tuple(
            updated if r.order_id == p.order_id else r
            for r in self._state.reservations
            if r.order_id != p.order_id or remaining
        )
        new_totals = replace(
            totals, notional=after, fees_paid=from_cents(money_cents(totals.fees_paid, "fees") + fee)
        )
        result = FillApplied(p, self._state.ledger_version + 1)
        self._commit(
            cash=from_cents(cash),
            lots=lots,
            reservations=reservations,
            order_totals=tuple(
                new_totals if t.order_id == p.order_id else t for t in self._state.order_totals
            ),
            fees_paid=from_cents(money_cents(self._state.fees_paid, "fees_paid") + fee),
            buckets=tuple(
                replace(b, remaining=b.remaining - p.qty) if b == bucket else b
                for b in self._state.buckets
            ),
            applied_fills=self._state.applied_fills + (result,),
        )
        return result

    def _consume_sell(
        self, reservation: Reservation, p: FillProposal
    ) -> tuple[tuple[LotPosition, ...], tuple[LotAllocation, ...]]:
        remaining = p.qty
        amounts = {}
        allocations = []
        lots_by_id = {lot.lot_id: lot for lot in self._state.lots}
        for allocation in reservation.lots:
            take = min(remaining, allocation.qty)
            lot = lots_by_id[allocation.lot_id]
            if take and (
                lot.sellable_date > p.trade_date or take > lot.reserved_qty or take > lot.qty
            ):
                raise LedgerError("SELL can consume only its reserved sellable lots")
            amounts[lot.lot_id] = take
            remaining -= take
            if allocation.qty > take:
                allocations.append(replace(allocation, qty=allocation.qty - take))
        if remaining:
            raise LedgerError("insufficient reserved sellable qty")
        lots = tuple(
            replace(
                lot,
                qty=lot.qty - amounts.get(lot.lot_id, 0),
                reserved_qty=lot.reserved_qty - amounts.get(lot.lot_id, 0),
            )
            for lot in self._state.lots
            if lot.qty > amounts.get(lot.lot_id, 0)
        )
        return lots, tuple(allocations)
