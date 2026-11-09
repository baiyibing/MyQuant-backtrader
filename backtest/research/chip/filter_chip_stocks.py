"""Compatibility entry; factor research implementation is owned by MyQuant."""
import importlib
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import oskh_factors._consumer

_shared = importlib.import_module("myquant_factors.research.filter_chip_stocks")
if __name__ == "__main__":
    raise SystemExit(_shared.main())
sys.modules[__name__] = _shared
