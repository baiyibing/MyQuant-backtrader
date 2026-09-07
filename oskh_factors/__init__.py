# -*- coding: utf-8 -*-
"""Factor computation domain (RFC-003 · zero oskh_data dependency)."""

from oskh_factors.chip.bands import classify_tr_bb_signal, compute_tr_bb_columns
from oskh_factors.chip.core import adapt_columns, compute_crossday_turnover_resistance
from oskh_factors.price_bb import bb_position
from oskh_factors.weekly_macd_divergence import DivergenceSignal, detect_weekly_macd_divergence

__all__ = (
    "DivergenceSignal",
    "adapt_columns",
    "bb_position",
    "classify_tr_bb_signal",
    "compute_crossday_turnover_resistance",
    "compute_tr_bb_columns",
    "detect_weekly_macd_divergence",
)
