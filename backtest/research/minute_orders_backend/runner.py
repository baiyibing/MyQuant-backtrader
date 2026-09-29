"""Opt-in in-memory research API; no writers, loaders, CLI or L1 registration."""

from .broker import BrokerCore
from .types import RunInput, RunResult


def run_minute_orders_research(run_input: RunInput) -> RunResult:
    """Replay explicit facts once; malformed inputs propagate, no success result.

    Empty marks are allowed only with requires_marks=False. Provided marks must
    be valid and cover held symbols at that event; S3 returns observations, not
    a NAV product. Active orders at end_at retain their remaining reservations.
    """
    return BrokerCore(run_input).run()
