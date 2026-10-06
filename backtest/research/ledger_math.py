"""Pure accounting arithmetic shared by CSV daily, minute and native v7 fees."""

from __future__ import annotations

STAMP_DUTY_CUTOVER = 20230828
STAMP_DUTY_RATE_BEFORE_CUTOVER = 0.001
STAMP_DUTY_RATE_FROM_CUTOVER = 0.0005


def trade_commission(notional: float, rate: float, min_cost: float = 0.0) -> float:
    """Fee on ``notional``. Floor applies only when ``min_cost > 0``."""
    if notional <= 0 or rate < 0:
        return 0.0
    fee = float(notional) * float(rate)
    floor = float(min_cost)
    if floor > 0:
        return max(fee, floor)
    return fee


def stamp_duty_rate(trade_date) -> float:
    """Return the sell-side stock stamp-duty rate for one trade date.

    财政部、税务总局公告 2023 年第 39 号 applies the halved rate from
    2023-08-28. Values may be date-like objects, ISO strings, or ``YYYYMMDD``.
    """
    if isinstance(trade_date, str):
        value = trade_date.strip()
    else:
        isoformat = getattr(trade_date, "isoformat", None)
        if not callable(isoformat):
            raise TypeError("trade_date must be date-like, YYYY-MM-DD, or YYYYMMDD")
        value = isoformat()
    compact = value[:10].replace("-", "")
    if len(compact) != 8 or not compact.isdigit():
        raise ValueError(f"invalid trade date: {trade_date!r}")
    return (
        STAMP_DUTY_RATE_BEFORE_CUTOVER
        if int(compact) < STAMP_DUTY_CUTOVER
        else STAMP_DUTY_RATE_FROM_CUTOVER
    )


def sell_stamp_duty(notional: float, trade_date) -> float:
    """Sell-side stamp duty for positive stock notional; buys call no tax."""
    return max(0.0, float(notional)) * stamp_duty_rate(trade_date)


def allocate_order_commission(
    notionals: tuple[float, ...], rate: float, min_cost: float
) -> tuple[float, ...]:
    """Allocate one order commission over its fills; the last fill takes drift."""
    positive = tuple(max(0.0, float(value)) for value in notionals)
    total_notional = sum(positive)
    if not positive or total_notional <= 0:
        return tuple(0.0 for _ in positive)
    total_fee = trade_commission(total_notional, rate, min_cost)
    allocated = [total_fee * notional / total_notional for notional in positive[:-1]]
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


class StampDutyAccumulator:
    """Accumulate dated sell fills under the same order identity as commission."""

    def __init__(self):
        self._fills: dict[object, list[tuple[float, object]]] = {}
        self._fees: dict[object, float] = {}

    def preview(self, order_id: object, notional: float, trade_date) -> FeeAccrual:
        fills = (*self._fills.get(order_id, ()), (max(0.0, float(notional)), trade_date))
        allocations = tuple(sell_stamp_duty(value, stamp) for value, stamp in fills)
        total_fee = sum(allocations)
        return FeeAccrual(
            total_fee=total_fee,
            fee_delta=total_fee - self._fees.get(order_id, 0.0),
            allocations=allocations,
        )

    def add_fill(self, order_id: object, notional: float, trade_date) -> FeeAccrual:
        accrual = self.preview(order_id, notional, trade_date)
        self._fills.setdefault(order_id, []).append((max(0.0, float(notional)), trade_date))
        self._fees[order_id] = accrual.total_fee
        return accrual

    def total_fee(self, order_id: object) -> float:
        return self._fees.get(order_id, 0.0)
