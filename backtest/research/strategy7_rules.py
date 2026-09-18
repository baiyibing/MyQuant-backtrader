# -*- coding: utf-8 -*-
"""Pure Strategy 7 rule calculations.

This module deliberately contains no market-data or execution-engine imports.  Prices
passed to these helpers are unadjusted prices, and callers remain responsible for
lot accounting, T+1 eligibility, and execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import prod
from typing import Mapping, Sequence


TRIAL = "trial"
FOUR = "four"
SIX = "six"
EIGHT = "eight"
FULL = "full"
TRIAL_FRACTION = 0.20
ADD_FRACTION = 0.20
ADD_HM_START = 14 * 60 + 45  # 14:45
ADD_HM_END = 14 * 60 + 55    # 14:55 inclusive
TIMER_SESSIONS = 10


def in_add_window(hm: int) -> bool:
    return ADD_HM_START <= int(hm) <= ADD_HM_END


@dataclass(frozen=True)
class RuleDecision:
    action: str
    line: float | None = None
    fraction: float = 0.0


def stop_decision(
    stage: str,
    *,
    entry_a: float,
    average_cost: float,
    add1_a1: float | None = None,
    trial_lot_present: bool = True,
) -> RuleDecision:
    """Return the sole stop rule for a stage (without testing the current price)."""
    if min(entry_a, average_cost) <= 0:
        raise ValueError("entry and average cost must be positive")
    if stage == TRIAL:
        return RuleDecision("dump_trial", entry_a * 0.90, 1.0)
    if stage == FOUR:
        return RuleDecision("clear_four", average_cost * 0.95, 1.0)
    if stage == SIX:
        return RuleDecision("clear_six", average_cost * 0.965, 1.0)
    if stage == EIGHT:
        return RuleDecision("clear_eight", average_cost * 0.975, 1.0)
    if stage == FULL:
        return RuleDecision("clear_full", average_cost * 0.98, 1.0)
    return RuleDecision("none")


def ladder_decision(
    stage: str,
    price: float,
    *,
    entry_a: float,
    add1_a1: float | None = None,
) -> RuleDecision:
    """Choose at most one add action; jump-to-nine has priority over +3 then +2."""
    if price <= 0 or entry_a <= 0:
        raise ValueError("price and entry_a must be positive")
    def reached(mult: float) -> bool:
        return price + 1e-9 >= entry_a * mult

    if stage == TRIAL and reached(1.04):
        return RuleDecision("add_a104", entry_a * 1.04, ADD_FRACTION)
    if stage == FOUR and reached(1.08):
        return RuleDecision("add_a108", entry_a * 1.08, ADD_FRACTION)
    if stage == SIX and reached(1.12):
        return RuleDecision("add_a112", entry_a * 1.12, ADD_FRACTION)
    if stage == EIGHT and reached(1.16):
        return RuleDecision("add_a116", entry_a * 1.16, ADD_FRACTION)
    return RuleDecision("none")


TP_MULTIPLIERS = (1.30, 1.50, 1.80, 2.00)
TP_FRACTIONS = (0.30, 0.20, 0.30, 0.20)


def alternate_tp_decision(price: float, moving_average: float, start_band: int = 0) -> RuleDecision:
    """Combine all consecutively crossed alternate-TP bands in one bar."""
    if moving_average <= 0 or not 0 <= start_band <= len(TP_MULTIPLIERS):
        raise ValueError("invalid moving_average or start_band")
    crossed = 0
    for multiplier in TP_MULTIPLIERS[start_band:]:
        if price < moving_average * multiplier:
            break
        crossed += 1
    if not crossed:
        return RuleDecision("none")
    ratios = TP_FRACTIONS[start_band : start_band + crossed]
    fraction = 1.0 - prod(1.0 - ratio for ratio in ratios)
    return RuleDecision(f"tp_bands_{start_band + 1}_{start_band + crossed}", fraction=fraction)


def drawdown_threshold(peak_gain: float) -> float:
    if peak_gain <= 0:
        raise ValueError("peak must be above cost")
    if peak_gain <= 0.20:
        return 0.50
    if peak_gain <= 0.50:
        return 0.40
    return 0.20


def drawdown_tp_triggered(stage: str, *, price: float, peak: float, cost: float) -> bool:
    if stage != FULL or cost <= 0 or peak <= cost:
        return False
    profit_drawdown = (peak - price) / (peak - cost)
    return profit_drawdown >= drawdown_threshold((peak - cost) / cost)


def timer_due(sessions: Sequence[date], anchor: date, today: date, stage: str) -> bool:
    """The anchor is day 0; trial-only clear is due from the 10th later session close."""
    if stage != TRIAL:
        return False
    try:
        anchor_index = sessions.index(anchor)
        today_index = sessions.index(today)
    except ValueError as exc:
        raise ValueError("anchor and today must be trading sessions") from exc
    return today_index - anchor_index >= TIMER_SESSIONS


def next_add_target(stage: str, *, entry_a: float, add1_a1: float | None = None) -> float | None:
    if stage == TRIAL:
        return entry_a * 1.04
    if stage == FOUR:
        return entry_a * 1.08
    if stage == SIX:
        return entry_a * 1.12
    if stage == EIGHT:
        return entry_a * 1.16
    return None


def validate_index_symbol(symbol: str) -> str:
    if symbol != "000001.SH":
        raise ValueError("Strategy 7 index symbol must be exactly 000001.SH")
    return symbol


def build_index_gate(
    closes: Mapping[date, float], *, symbol: str = "000001.SH"
) -> dict[date, bool]:
    """Build ``block_new`` by session using only closes through the prior session.

    The first returned session follows eleven warmup sessions.  This ensures both
    completed days in the two-day test have independently computable MA10 values.
    """
    validate_index_symbol(symbol)
    items = sorted(closes.items())
    if len(items) < 12:
        raise ValueError("index gate requires 11 warmup sessions plus a gate session")
    if any(value <= 0 for _, value in items):
        raise ValueError("index closes must be positive")
    dates = [day for day, _ in items]
    values = [float(value) for _, value in items]
    ma10: list[float | None] = [None] * len(values)
    for index in range(9, len(values)):
        ma10[index] = sum(values[index - 9 : index + 1]) / 10.0

    blocked = False
    gate: dict[date, bool] = {}
    for session_index in range(11, len(values)):
        completed = session_index - 1
        completed_ma = ma10[completed]
        previous_ma = ma10[completed - 1]
        assert completed_ma is not None and previous_ma is not None
        if values[completed] >= completed_ma:
            blocked = False
        elif values[completed - 1] < previous_ma:
            blocked = True
        gate[dates[session_index]] = blocked
    return gate
