"""Pure accounting arithmetic shared by CSV daily, minute and native v7 fees."""

from __future__ import annotations


def trade_commission(notional: float, rate: float, min_cost: float = 0.0) -> float:
    """Fee on ``notional``. Floor applies only when ``min_cost > 0``."""
    if notional <= 0 or rate < 0:
        return 0.0
    fee = float(notional) * float(rate)
    floor = float(min_cost)
    if floor > 0:
        return max(fee, floor)
    return fee


def allocate_order_commission(
    notionals: tuple[float, ...], rate: float, min_cost: float
) -> tuple[float, ...]:
    """Allocate one order commission over its fills; the last fill takes drift."""
    positive = tuple(max(0.0, float(value)) for value in notionals)
    total_notional = sum(positive)
    if not positive or total_notional <= 0:
        return tuple(0.0 for _ in positive)
    total_fee = trade_commission(total_notional, rate, min_cost)
    allocated = [
        total_fee * notional / total_notional for notional in positive[:-1]
    ]
    allocated.append(total_fee - sum(allocated))
    allocated[-1] += total_fee - sum(allocated)
    return tuple(allocated)


class FeeAccrual:
    """Result of adding one fill to an order."""

    __slots__ = ("allocations", "fee_delta", "total_fee")

    def __init__(self, total_fee: float, fee_delta: float, allocations: tuple[float, ...]):
        self.total_fee = total_fee
        self.fee_delta = fee_delta
        self.allocations = allocations


class FeeAccumulator:
    """Accumulate actual fill notional and charge one minimum per order."""

    def __init__(self, rate: float, min_cost: float):
        self.rate = float(rate)
        self.min_cost = float(min_cost)
        self._notionals: dict[object, list[float]] = {}
        self._fees: dict[object, float] = {}

    def preview(self, order_id: object, notional: float) -> FeeAccrual:
        notionals = (*self._notionals.get(order_id, ()), float(notional))
        allocations = allocate_order_commission(notionals, self.rate, self.min_cost)
        total_fee = trade_commission(
            sum(max(0.0, value) for value in notionals), self.rate, self.min_cost
        )
        return FeeAccrual(
            total_fee=total_fee,
            fee_delta=total_fee - self._fees.get(order_id, 0.0),
            allocations=allocations,
        )

    def add_fill(self, order_id: object, notional: float) -> FeeAccrual:
        accrual = self.preview(order_id, notional)
        self._notionals.setdefault(order_id, []).append(max(0.0, float(notional)))
        self._fees[order_id] = accrual.total_fee
        return accrual

    def total_fee(self, order_id: object) -> float:
        return self._fees.get(order_id, 0.0)
