"""BT compatibility alias; implementation is owned by MyQuant."""
import importlib
import sys
import oskh_factors._consumer  # Bind host policy, never a local numerical fallback.

_shared = importlib.import_module("myquant_factors.chip.core")
sys.modules[__name__] = _shared
