"""Explicit batch4 research execution: H2 lifetime and Q2 fill-price sizing.

Production entry points never import this module. The default adapters delegate
directly to their original engines; experimental runs own their event queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import heapq
import itertools
import math
from typing import Callable


DEFAULT_CLOCK = "production_default"
NEXT_OPEN = "next_tradable_open_research"


@dataclass(frozen=True)
class ResearchFillConfig:
    clock_mode: str = DEFAULT_CLOCK
    slip_bp_per_side: int = 0

    def __post_init__(self):
        if self.clock_mode not in (DEFAULT_CLOCK, NEXT_OPEN):
            raise ValueError(f"unsupported research clock: {self.clock_mode}")
        if self.slip_bp_per_side not in (0, 5, 10, 20):
            raise ValueError("slip must be 0/5/10/20 bp per side")
        if self.clock_mode != DEFAULT_CLOCK and self.slip_bp_per_side:
            raise ValueError("clock XOR slip: select only one axis")

    @property
    def baseline(self):
        return self.clock_mode == DEFAULT_CLOCK and self.slip_bp_per_side == 0

    def price(self, price, side):
        return float(price) * (
            1 + (1 if side == "buy" else -1) * self.slip_bp_per_side / 10_000
        )


def stamp(day, hm):
    # Lake timestamps are wall-clock labels, including when stored with UTC tz.
    import pandas as pd

    day = pd.Timestamp(day).to_pydatetime().replace(tzinfo=None)
    return day.replace(hour=int(hm) // 60, minute=int(hm) % 60, second=0, microsecond=0)


def available_at(day, hm, *, at_open=False):
    return stamp(day, hm) + (timedelta(0) if at_open else timedelta(minutes=1))


@dataclass(frozen=True)
class OpenCandidate:
    at: datetime
    price: float
    limits: tuple[float, float] | None


@dataclass
class ResearchOrder:
    symbol: str
    side: str
    decision_at: datetime
    signal_price: float
    tentative_shares: int
    # commit re-runs the engine sizer at this price and uses current cash.
    commit: Callable[[float, datetime], bool]
    candidates: list[OpenCandidate] = field(default_factory=list)
    buy_day: object = None
    reject_buy_limit_down: bool = False
    reason: str = ""
    on_done: Callable[[bool], None] | None = None
    status: str = "PENDING"


class ResearchSession:
    """Chronological same-day queue; no cash reservation or future booking.

    Signals at a completed START bar precede submission by 1ms. Candidate
    opens at that exact close timestamp cannot fill the new order. Previously
    submitted orders execute before strategy decisions at the same timestamp;
    insertion order within each phase preserves pool order.
    """

    def __init__(self, config, day, audit):
        self.config = config
        self.day = stamp(day, 0).date()
        self.audit = audit
        self.queue = []
        self.counter = itertools.count()
        self.orders = []
        self.now = stamp(day, 0)

    def at(self, when, action, *, fill=False):
        if when.date() != self.day:
            raise ValueError("research events must stay in their session")
        heapq.heappush(self.queue, (when, 0 if fill else 1, next(self.counter), action))

    def submit(self, order):
        if order.decision_at.date() != self.day:
            raise ValueError("order submitted outside its session")
        self.orders.append(order)
        if self.config.clock_mode == DEFAULT_CLOCK:
            px = self.config.price(order.signal_price, order.side)
            self._finish(
                order,
                order.commit(px, order.decision_at),
                px,
                order.decision_at,
                "fill_price_sizer",
            )
            return
        submit = order.decision_at + timedelta(milliseconds=1)
        for candidate in sorted(order.candidates, key=lambda bar: bar.at):
            hm = candidate.at.hour * 60 + candidate.at.minute
            if (
                candidate.at.date() == self.day
                and candidate.at >= submit
                and (570 <= hm < 690 or 780 <= hm < 897)
            ):
                self.at(
                    candidate.at, lambda c=candidate: self._try(order, c), fill=True
                )

    def _try(self, order, candidate):
        from backtest.research.ashare_session import (
            defer_sell_at_limit,
            skip_buy_at_limit,
            t1_sellable,
        )

        if order.status != "PENDING":
            return
        px, limits = candidate.price, candidate.limits
        if limits is None or not math.isfinite(px) or px <= 0:
            return
        if order.side == "sell":
            if order.buy_day is None or not t1_sellable(order.buy_day, self.day):
                return
            if defer_sell_at_limit(px, limits):
                return
        elif skip_buy_at_limit(px, limits) or (
            order.reject_buy_limit_down and defer_sell_at_limit(px, limits)
        ):
            return
        # Q2 lives in commit: passing px to the original buy primitive reruns
        # its round-lot sizer. A failed resized order ends this day's attempt.
        self._finish(
            order, order.commit(px, candidate.at), px, candidate.at, "fill_price_sizer"
        )

    def _finish(self, order, filled, px, at, reason):
        order.status = "FILLED" if filled else "UNFILLED"
        self.audit.append(
            dict(
                symbol=order.symbol,
                side=order.side,
                decision_at=order.decision_at.isoformat(),
                tentative_shares=order.tentative_shares,
                signal_price=order.signal_price,
                status=order.status,
                fill_at=at.isoformat() if filled else "",
                fill_price=px if filled else "",
                reason=reason
                if filled or reason == "same_day_expiry"
                else "resized_order_rejected",
                signal_reason=order.reason,
            )
        )
        if order.on_done:
            order.on_done(bool(filled))

    def run(self):
        while self.queue:
            self.now, _, _, action = heapq.heappop(self.queue)
            action()
        for order in self.orders:
            if order.status == "PENDING":
                self._finish(order, False, None, self.now, "same_day_expiry")
        # No exit intent or order can be picked up by the next session.
        self.orders.clear()


def simulate_book(*args, clock_mode=DEFAULT_CLOCK, slip_bp_per_side=0, **kwargs):
    config = ResearchFillConfig(clock_mode, slip_bp_per_side)
    from backtest.research import csv_minute_backtest as book

    if config.baseline:
        return book.simulate(*args, **kwargs)
    from backtest.research.fullstrat_research_book import simulate

    return simulate(*args, config=config, **kwargs)


def simulate_v7(*args, clock_mode=DEFAULT_CLOCK, slip_bp_per_side=0, **kwargs):
    config = ResearchFillConfig(clock_mode, slip_bp_per_side)
    from backtest.research import csv_minute_backtest_v7 as v7

    if config.baseline:
        return v7.simulate_v7(*args, **kwargs)
    from backtest.research.fullstrat_research_v7 import simulate

    return simulate(*args, config=config, **kwargs)


def run_modeb(*args, clock_mode=DEFAULT_CLOCK, slip_bp_per_side=0, **kwargs):
    config = ResearchFillConfig(clock_mode, slip_bp_per_side)
    from backtest.research import unified_exit_modeb as modeb

    if config.baseline:
        return modeb.run_modeb(*args, **kwargs)
    from backtest.research.fullstrat_research_modeb import run

    return run(*args, config=config, **kwargs)
