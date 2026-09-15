"""Numba minute_chip_distribution must bit-close match the Python reference.

Tolerances are ULP-tight (1e-15); residual comes from float64 multiply-add order
vs NumPy vector ops — not semantic drift.
"""

from __future__ import annotations

import numpy as np
import pytest

from oskh_factors.chip import core as chip_core

pytestmark = pytest.mark.skipif(
    not getattr(chip_core, "_NUMBA_MINUTE_CHIP_AVAILABLE", False),
    reason="numba not installed",
)


def _synth_minute_arr(n_days: int, minutes_per_day: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = n_days * minutes_per_day
    rets = rng.normal(0.0, 0.0015, size=n)
    close = 10.0 * np.cumprod(1.0 + rets)
    high = close * (1.0 + rng.uniform(0.0, 0.002, size=n))
    low = close * (1.0 - rng.uniform(0.0, 0.002, size=n))
    vol = rng.uniform(1e3, 5e4, size=n)
    turnover = rng.uniform(1e-5, 5e-4, size=n)
    return np.column_stack([close, high, low, vol, turnover]).astype(np.float64)


def _assert_bit_close(py, nb, *, rtol: float = 1e-15, atol: float = 1e-15):
    assert list(py.index) == list(nb.index)
    assert py.name == nb.name == "cumpdf"
    np.testing.assert_allclose(
        py.to_numpy(dtype=np.float64),
        nb.to_numpy(dtype=np.float64),
        rtol=rtol,
        atol=atol,
        equal_nan=True,
    )


def test_numba_matches_python_synth_default_window():
    arr = _synth_minute_arr(80, 240, seed=0)
    py = chip_core.minute_chip_distribution_python(arr, step=0.01, stock_code="SYNTH")
    nb = chip_core.minute_chip_distribution(arr, step=0.01, stock_code="SYNTH", use_numba=True)
    assert not py.empty and not nb.empty
    _assert_bit_close(py, nb)


def test_numba_matches_python_with_nan_and_zero_vol():
    arr = _synth_minute_arr(3, 40, seed=7)
    arr[0, 0] = np.nan
    arr[5, 3] = 0.0
    arr[10, 3] = -1.0
    arr[15, 0] = np.nan
    py = chip_core.minute_chip_distribution_python(arr, step=0.01)
    nb = chip_core.minute_chip_distribution(arr, step=0.01, use_numba=True)
    _assert_bit_close(py, nb)


def test_numba_matches_python_flat_price_empty():
    n = 20
    arr = np.column_stack(
        [
            np.full(n, 10.0),
            np.full(n, 10.0),
            np.full(n, 10.0),
            np.full(n, 1e3),
            np.full(n, 1e-4),
        ]
    ).astype(np.float64)
    py = chip_core.minute_chip_distribution_python(arr, step=0.01, stock_code="FLAT")
    nb = chip_core.minute_chip_distribution(arr, step=0.01, stock_code="FLAT", use_numba=True)
    assert py.empty and nb.empty


def test_use_numba_false_forces_python_even_if_env_numba(monkeypatch):
    monkeypatch.setenv("MINUTE_CHIP_BACKEND", "numba")
    arr = _synth_minute_arr(2, 30, seed=3)
    forced = chip_core.minute_chip_distribution(arr, step=0.01, use_numba=False)
    ref = chip_core.minute_chip_distribution_python(arr, step=0.01)
    _assert_bit_close(ref, forced)


def test_env_backend_numba_selects_numba(monkeypatch):
    monkeypatch.setenv("MINUTE_CHIP_BACKEND", "numba")
    arr = _synth_minute_arr(2, 30, seed=4)
    via_env = chip_core.minute_chip_distribution(arr, step=0.01, use_numba=None)
    ref = chip_core.minute_chip_distribution_python(arr, step=0.01)
    _assert_bit_close(ref, via_env)
