# -*- coding: utf-8 -*-
"""Compatibility re-export of the factors turnover-resist bridge."""

from oskh_factors.bridge.turnover_resist import (  # noqa: F401
    compute_turnover_resist,
    is_ffi_available,
    bridge_mode,
)

try:
    from oskh_factors.bridge.turnover_resist import _find_exe, _cli_compute
except ImportError:  # pragma: no cover
    _find_exe = None  # type: ignore[assignment]
    _cli_compute = None  # type: ignore[assignment]

__all__ = [
    "compute_turnover_resist",
    "is_ffi_available",
    "bridge_mode",
]
