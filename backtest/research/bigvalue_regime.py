"""Thin re-export of the series-agnostic market regime core.

Since the 2026-10-18 unification (plan-market-regime-unify-2026-10-18.md) the
implementation lives in ``market_regime``; this module keeps the #480 import
surface (engines, books wiring, tests) unchanged. Behavior is byte-identical.
"""

from backtest.research.market_regime import (
    confirmed_days,
    flatten_reason,
    golden_cash_fraction,
    load_regime,
    regime_cash_fraction,
    with_bigvalue_gate,
    with_regime_gate,
)

__all__ = [
    "confirmed_days",
    "flatten_reason",
    "golden_cash_fraction",
    "load_regime",
    "regime_cash_fraction",
    "with_bigvalue_gate",
    "with_regime_gate",
]
