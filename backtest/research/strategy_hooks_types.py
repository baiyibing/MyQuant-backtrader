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
    scale_out_anchor: str
    step_cap: int | None
    step_stop_pct: float | None
    peak_dd_exit: float | None
    peak_dd_sessions: int
    peak_dd_min_rise: float | None
    cont_step_stop_pct: float | None
    cont_live_max: int | None
    cont_stop_rebuy: bool
    cont_ride_trial: bool
    cont_from_rise: float | None
    cont_stop_rebuy_lift: float | None
    cont_stop_rebuy_frac: float | None
    cont_stop_rebuy_open_frac: float | None
    cont_stop_rebuy_with_schedule: bool
    min_lot_top_up: bool
    parking_symbol: str
    parking_frac: float
    parking_buffer: float
    parking_execute: bool
    parking_open_cover: bool
    profit_skim: bool
    profit_skim_step: float | None
    profit_skim_frac: float | None
    profit_skim_pro_rata: bool
    profit_skim_keep_idle: bool
    profit_skim_to_parking: bool
    profit_skim_base: float | None
    index_cut: bool
    index_cut_frac: float | None
    index_cut_min_keep: int | None
    index_blocks_s8_add: bool
    div_to_parking: bool


# Book apply functions have different named parameters.
StrategyApply = Callable[..., Mapping[str, Any]]
