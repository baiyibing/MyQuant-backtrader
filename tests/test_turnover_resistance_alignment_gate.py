# -*- coding: utf-8 -*-
"""Data-free exit-policy tests for the lake-backed TR alignment gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_GATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "gates"
    / "verify_turnover_resistance_alignment.py"
)
_SPEC = importlib.util.spec_from_file_location("tr_alignment_gate", _GATE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_GATE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_GATE)
alignment_exit_code = _GATE.alignment_exit_code


def test_alignment_exit_code_requires_both_metrics() -> None:
    assert alignment_exit_code(3, 3, 3) == 0
    assert alignment_exit_code(3, 2, 3) == 2
    assert alignment_exit_code(3, 3, 2) == 2
    assert alignment_exit_code(3, 2, 2) == 2


def test_alignment_exit_code_rejects_zero_valid_samples() -> None:
    assert alignment_exit_code(0, 0, 0) == 1
