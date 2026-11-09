"""Compatibility alias; factor implementation is owned by MyQuant."""
import sys
from myquant_factors import turnover_coefficient_ops as _shared

sys.modules[__name__] = _shared
