"""Compatibility entry; implementation is owned by MyQuant."""
import importlib
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import oskh_factors._consumer  # noqa: F401,E402
_shared = importlib.import_module("myquant_factors.research.entries.tr.backfill_turnover_resistance_bands")
if __name__ == "__main__":
    raise SystemExit(_shared.main())
sys.modules[__name__] = _shared
