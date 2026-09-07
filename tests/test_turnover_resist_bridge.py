# -*- coding: utf-8 -*-
"""Tests for turnover_resist_bridge (PyO3 FFI + CLI fallback)."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


class TestBridgeMode:
    def test_bridge_mode_returns_valid_string(self):
        from oskh_core.turnover_resist_bridge import bridge_mode

        mode = bridge_mode()
        assert mode in ("pyo3_ffi", "cli_fallback")

    def test_is_ffi_available_does_not_crash(self):
        from oskh_core.turnover_resist_bridge import is_ffi_available

        result = is_ffi_available()
        assert isinstance(result, bool)


class TestCliFallback:
    def test_find_exe_returns_path(self):
        from oskh_core.turnover_resist_bridge import _find_exe

        # Should find the exe (built during this session)
        exe = _find_exe()
        assert exe.name == "turnover-resist.exe"

    def test_cli_compute_echo_fails_without_data(self):
        """CLI should fail gracefully when data_dir doesn't exist."""
        from oskh_core.turnover_resist_bridge import _cli_compute

        with pytest.raises((RuntimeError, FileNotFoundError)):
            _cli_compute(
                date="20991231",
                data_dir="Z:/nonexistent_path_for_test",
                window=20,
                step=0.01,
                sort_by="circulating",
                free_float_policy="warn-zero",
                target_date_policy="strict",
                bb_ddof=1,
                max_grid_points=250_000,
            )


class TestBridgeRespectsPreferFfi:
    def test_prefer_ffi_false_goes_cli_directly(self, monkeypatch):
        """When prefer_ffi=False, skip FFI and go straight to CLI."""
        from oskh_core.turnover_resist_bridge import compute_turnover_resist

        # With no data and prefer_ffi=False, should raise from CLI path
        with pytest.raises((RuntimeError, FileNotFoundError)):
            compute_turnover_resist(
                date="20991231",
                data_dir="Z:/nonexistent",
                prefer_ffi=False,
            )
