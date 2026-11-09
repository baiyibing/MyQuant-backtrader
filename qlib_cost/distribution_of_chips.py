"""Compatibility alias; factor implementation is owned by MyQuant."""
import sys
from myquant_factors import distribution_of_chips as _shared

sys.modules[__name__] = _shared
