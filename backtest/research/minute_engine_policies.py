"""Book-selected boundaries for the main minute loop.

Legacy books keep their existing initialization, scheduling and daily marks.
Native books can supply their calendar/state/marks without translating their
ledger. Scheduling stays in main/minute_cash_order; sessions handle one event.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Protocol

from backtest.research.rule_profile import INDUSTRY, RuleProfile


@dataclass(frozen=True)
class MinutePolicyContext:
    """Native inputs kept intact for calendar and accounting adapters."""

    index_days: Any = None
    fee_schedule: Any = None
    native_inputs: Any = None
    rule_profile: RuleProfile = INDUSTRY


@dataclass(frozen=True)
class MinuteRowToken:
    """An ordered row identity; equal-clock rows must remain distinct."""

    symbol: str
    ordinal: int
    hm: int
    row: Any


class MinuteEventSession(Protocol):
    """Single-event callbacks; no callback owns a day or minute traversal.

    The scheduler observes all rows at a clock before dispatching book phases.
    Phase names/order belong to that scheduler, including post-buy timers.
    """

    def begin_symbol(self, symbol: str) -> None: ...
    def observe_row(self, token: MinuteRowToken) -> None: ...
    def on_phase(self, token: MinuteRowToken, phase: str) -> None: ...
    def finish_symbol(self, symbol: str) -> None: ...


@dataclass(frozen=True)
class MinuteEnginePolicy:
    """Optional adapters, called at the main loop's existing boundaries.

    None means the original shared operation, not a generic native conversion.
    State factories return (state, pending_chase, names_asof), as main expects.
    A native mark callback appends the native equity row itself, preserving its
    operation order. Writer selection is metadata for native entry adapters.
    """

    schedule: Literal["legacy", "symbol_major", "chronological"] = "legacy"
    calendar: Callable[..., Any] | None = None
    initialize: Callable[..., Any] | None = None
    day_start: Callable[..., None] | None = None
    append_marks: Callable[..., None] | None = None
    writer: Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        if self.schedule not in {"legacy", "symbol_major", "chronological"}:
            raise ValueError(f"unsupported minute schedule: {self.schedule}")

    def chronological(self, hooks: Mapping[str, Any], *, fix_cash_order: bool,
                      topk_exec: str, limit_walkdown: bool) -> bool:
        if self.schedule != "legacy":
            return self.schedule == "chronological"
        return bool(hooks.get("minute_session") or fix_cash_order
                    or topk_exec != "close" or limit_walkdown)


LEGACY_MINUTE_POLICY = MinuteEnginePolicy()


def minute_policy_for(hooks: Mapping[str, Any]) -> MinuteEnginePolicy:
    policy = hooks.get("minute_policy", LEGACY_MINUTE_POLICY)
    if not isinstance(policy, MinuteEnginePolicy):
        raise TypeError("minute_policy must be a MinuteEnginePolicy")
    return policy
