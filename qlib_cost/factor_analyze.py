"""Compatibility alias; factor implementation is owned by MyQuant."""
import sys
from myquant_factors import factor_analyze as _shared

sys.modules[__name__] = _shared
