# -*- coding: utf-8 -*-
"""Research-engine fee SSOT for daily and minute CSV matchers.

Two locked schedules:

- ``BILATERAL_10BP``: 0.1% each side, no floor (CSV books 1–10 / v7 default)
- ``QLIB_PORTANA``: open 5bp / close 15bp / min 5 (qlib Exchange, ``--qlib-cost``)
- ``INDUSTRY_ACCOUNT_FEES``: 3bp each side / min 5 per strategy order,
  plus dated sell-side stamp duty

Transfer fees remain disabled until their own industry-profile slice. This
module must not import a simulate loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from backtest.research.ledger_math import (
    sell_stamp_duty as sell_stamp_duty,
    trade_commission as trade_commission,
)

COMMISSION = 0.001
QLIB_OPEN_COST = 0.0005
QLIB_CLOSE_COST = 0.0015
QLIB_MIN_COST = 5.0
INDUSTRY_COMMISSION_RATE = 0.0003
INDUSTRY_MIN_COMMISSION = 5.0


@dataclass(frozen=True)
class FeeSchedule:
    buy_rate: float = COMMISSION
    sell_rate: float = COMMISSION
    min_cost: float = 0.0
    per_order: bool = False
    dated_sell_stamp_duty: bool = False

    def buy_fee(self, notional: float) -> float:
        return trade_commission(notional, self.buy_rate, self.min_cost)

    def sell_fee(self, notional: float) -> float:
        return trade_commission(notional, self.sell_rate, self.min_cost)

    def stamp_duty_fee(self, notional: float, trade_date) -> float:
        if not self.dated_sell_stamp_duty:
            return 0.0
        return sell_stamp_duty(notional, trade_date)

    def debit_buy(self, notional: float) -> float:
        return float(notional) + self.buy_fee(notional)

    def credit_sell(self, notional: float, trade_date=None) -> float:
        if self.dated_sell_stamp_duty and trade_date is None:
            raise ValueError("dated sell stamp duty requires trade_date")
        return (
            float(notional)
            - self.sell_fee(notional)
            - self.stamp_duty_fee(notional, trade_date)
        )


BILATERAL_10BP = FeeSchedule(COMMISSION, COMMISSION, 0.0)
QLIB_PORTANA = FeeSchedule(QLIB_OPEN_COST, QLIB_CLOSE_COST, QLIB_MIN_COST)
INDUSTRY_ACCOUNT_FEES = FeeSchedule(
    INDUSTRY_COMMISSION_RATE,
    INDUSTRY_COMMISSION_RATE,
    INDUSTRY_MIN_COMMISSION,
    per_order=True,
    dated_sell_stamp_duty=True,
)
# Compatibility name introduced by P03; the active industry schedule now also
# includes P04 stamp duty.
INDUSTRY_ORDER_COMMISSION = INDUSTRY_ACCOUNT_FEES
DEFAULT_SCHEDULE = BILATERAL_10BP


def resolve_account_fee_schedule(
    enabled: bool,
    *,
    explicit_rates: tuple[float | None, float | None, float | None] = (None, None, None),
    fee_schedule: FeeSchedule | None = None,
) -> FeeSchedule:
    """Resolve the profile schedule and reject silent legacy-cost stacking."""
    if not enabled:
        return DEFAULT_SCHEDULE if fee_schedule is None else fee_schedule
    if any(value is not None for value in explicit_rates) or fee_schedule is not None:
        raise ValueError(
            "rule_profile='industry' account_fee_schedule conflicts with explicit "
            "legacy cost options (--qlib-cost / QLIB_PORTANA / custom FeeSchedule)"
        )
    return INDUSTRY_ACCOUNT_FEES


__all__ = [
    "BILATERAL_10BP",
    "COMMISSION",
    "DEFAULT_SCHEDULE",
    "FeeSchedule",
    "INDUSTRY_ACCOUNT_FEES",
    "INDUSTRY_COMMISSION_RATE",
    "INDUSTRY_MIN_COMMISSION",
    "INDUSTRY_ORDER_COMMISSION",
    "QLIB_CLOSE_COST",
    "QLIB_MIN_COST",
    "QLIB_OPEN_COST",
    "QLIB_PORTANA",
    "resolve_account_fee_schedule",
    "trade_commission",
]
