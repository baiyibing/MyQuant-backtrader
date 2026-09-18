# -*- coding: utf-8 -*-
"""Research-engine fee SSOT for daily and minute CSV matchers.

Two locked schedules:

- ``BILATERAL_10BP``: 0.1% each side, no floor (CSV books 1–10 / v7 default)
- ``QLIB_PORTANA``: open 5bp / close 15bp / min 5 (qlib Exchange, ``--qlib-cost``)

Live broker stamp + transfer stay in ``trade_fee_policy``; do not import that
here. This module must not import a simulate loop.
"""

from __future__ import annotations

from dataclasses import dataclass

COMMISSION = 0.001
QLIB_OPEN_COST = 0.0005
QLIB_CLOSE_COST = 0.0015
QLIB_MIN_COST = 5.0


def trade_commission(notional: float, rate: float, min_cost: float = 0.0) -> float:
    """Fee on ``notional``. Floor applies only when ``min_cost > 0``."""
    if notional <= 0 or rate < 0:
        return 0.0
    fee = float(notional) * float(rate)
    floor = float(min_cost)
    if floor > 0:
        return max(fee, floor)
    return fee


@dataclass(frozen=True)
class FeeSchedule:
    buy_rate: float = COMMISSION
    sell_rate: float = COMMISSION
    min_cost: float = 0.0

    def buy_fee(self, notional: float) -> float:
        return trade_commission(notional, self.buy_rate, self.min_cost)

    def sell_fee(self, notional: float) -> float:
        return trade_commission(notional, self.sell_rate, self.min_cost)

    def debit_buy(self, notional: float) -> float:
        return float(notional) + self.buy_fee(notional)

    def credit_sell(self, notional: float) -> float:
        return float(notional) - self.sell_fee(notional)


BILATERAL_10BP = FeeSchedule(COMMISSION, COMMISSION, 0.0)
QLIB_PORTANA = FeeSchedule(QLIB_OPEN_COST, QLIB_CLOSE_COST, QLIB_MIN_COST)
DEFAULT_SCHEDULE = BILATERAL_10BP


__all__ = [
    "BILATERAL_10BP",
    "COMMISSION",
    "DEFAULT_SCHEDULE",
    "FeeSchedule",
    "QLIB_CLOSE_COST",
    "QLIB_MIN_COST",
    "QLIB_OPEN_COST",
    "QLIB_PORTANA",
    "trade_commission",
]
