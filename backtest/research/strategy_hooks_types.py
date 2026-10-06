"""Static descriptions of a practical subset of CSV strategy apply() hooks.

Every key is optional. Legacy callers remain dict-compatible; this module does
not validate, wrap, coerce, or supply defaults for hook dictionaries. Callback
signatures vary by book, so their arguments stay intentionally unconstrained.
"""

from collections.abc import Callable, Mapping
from typing import Any, TypedDict


class StrategyHooks(TypedDict, total=False):
    """Optional common hook keys, not an exhaustive registry schema."""

    name: str
    sizing: str
    stop_pct: float | None
    take_profit: Callable[..., Any] | None
    record_params: Callable[..., Any] | None
    name_lot_budget: Callable[..., Any] | None
    name_budget: float
    allow_new_name: Callable[..., Any] | None
    add_step: float
    step_frac: float
    allow_add: bool
    peak_gap_min: int
    buy_gate: Callable[..., Any] | None
    add_gate: Callable[..., Any] | None
    sell_gate: Callable[..., Any] | None
    step_add: Callable[..., Any] | None
    cost_anchor: str
    step_cap: int | None
    step_stop_pct: float | None


# Book apply functions have different named parameters.
StrategyApply = Callable[..., Mapping[str, Any]]
