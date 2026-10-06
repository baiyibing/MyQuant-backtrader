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

