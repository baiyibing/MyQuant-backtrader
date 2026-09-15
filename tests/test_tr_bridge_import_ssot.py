# -*- coding: utf-8 -*-
"""H11: TR bridge import SSOT is data-free and points at oskh_factors.bridge."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "gates" / "verify_tr_bridge_import_ssot.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("verify_tr_bridge_import_ssot", GATE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tr_bridge_import_ssot_gate_ok():
    mod = _load_gate()
    assert mod.check_shim() == []
    assert mod.check_known_consumers() == []
    assert mod.main() == 0


def test_oskh_core_shim_is_same_objects():
    from oskh_core.turnover_resist_bridge import (
        bridge_mode,
        compute_turnover_resist,
        is_ffi_available,
    )
    from oskh_factors.bridge.turnover_resist import (
        bridge_mode as factor_mode,
        compute_turnover_resist as factor_compute,
        is_ffi_available as factor_ffi,
    )

    assert compute_turnover_resist is factor_compute
    assert bridge_mode is factor_mode
    assert is_ffi_available is factor_ffi
