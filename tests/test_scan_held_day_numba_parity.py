"""Numba trail path must match the Python reference on fixtures."""

from __future__ import annotations

import math

import numpy as np
import pytest

from backtest.research import csv_minute_backtest as sim

pytestmark = pytest.mark.skipif(
    not getattr(sim, "_NUMBA_SCAN_AVAILABLE", False),
    reason="numba not installed",
)


def _run_both(**kwargs):
    py = sim.scan_held_day_python(**kwargs)
    nb = sim.scan_held_day(**kwargs, use_numba=True)
    return py, nb


def _assert_same(py, nb):
    assert py[0] == nb[0]
    assert py[2] == nb[2]
    assert py[4] == nb[4]
    if py[0] < 0:
        assert math.isnan(py[1]) and math.isnan(nb[1])
    else:
        assert py[1] == pytest.approx(nb[1])
    assert py[3] == pytest.approx(nb[3])


def test_numba_gap_open_stop():
    o = np.array([9.40, 9.50], dtype=np.float64)
    h = np.array([9.50, 9.55], dtype=np.float64)
    c = np.array([9.45, 9.50], dtype=np.float64)
    py, nb = _run_both(
        o=o,
        h=h,
        c=c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
    )
    _assert_same(py, nb)
    assert py[2] == "stop_loss:gap_open"


def test_numba_t0_no_sell_no_peak_update():
    o = np.array([9.40], dtype=np.float64)
    h = np.array([10.20], dtype=np.float64)
    c = np.array([9.35], dtype=np.float64)
    py, nb = _run_both(
        o=o,
        h=h,
        c=c,
        cost=10.0,
        peak=10.0,
        n_days=0,
        can_sell=False,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
    )
    _assert_same(py, nb)
    assert py[0] == -1
    assert py[3] == pytest.approx(10.0)


def test_numba_trail_hit():
    # cost=10, peak climbs to 11 (> +1% anchor), then close pulls back into trail band
    o = np.array([10.0, 10.5, 10.2], dtype=np.float64)
    h = np.array([10.2, 11.0, 10.3], dtype=np.float64)
    c = np.array([10.1, 10.8, 10.15], dtype=np.float64)
    hm = np.array([600, 620, 640], dtype=np.int64)
    py, nb = _run_both(
        o=o,
        h=h,
        c=c,
        hm=hm,
        cost=10.0,
        peak=10.0,
        n_days=3,
        can_sell=True,
        stop_pct=0.06,
        profit_base=0.01,
        trail_ratio=0.50,
        peak_hm=-1,
        peak_gap_min=15,
    )
    _assert_same(py, nb)


def test_numba_force_sell_time():
    o = np.array([10.0], dtype=np.float64)
    h = np.array([10.0], dtype=np.float64)
    c = np.array([10.0], dtype=np.float64)
    hm = np.array([14 * 60 + 50], dtype=np.int64)
    py, nb = _run_both(
        o=o,
        h=h,
        c=c,
        hm=hm,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=None,
        profit_base=0.01,
        trail_ratio=0.50,
        force_sell_hm=14 * 60 + 50,
    )
    _assert_same(py, nb)
    assert py[2] == "force_sell:time"
