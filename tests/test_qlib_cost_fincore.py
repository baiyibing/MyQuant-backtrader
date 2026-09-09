# -*- coding: utf-8 -*-
"""M3: qlib_cost.plotting uses fincore Empyrical; xtquant is win32-only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


REPO = Path(__file__).resolve().parents[1]
PLOTTING = REPO / "qlib_cost" / "plotting.py"


def test_plotting_source_uses_fincore_empyrical():
    text = PLOTTING.read_text(encoding="utf-8")
    assert "from fincore.empyrical import Empyrical" in text
    assert text.count("Empyrical.cum_returns") == 3
    assert "import empyrical" not in text


def test_import_qlib_cost_package():
    import qlib_cost

    assert hasattr(qlib_cost, "calc_dist_chips")


def test_empyrical_cum_returns_matches_known_values():
    from fincore.empyrical import Empyrical

    rets = pd.Series([0.01, 0.02, -0.015, 0.03])
    got = Empyrical.cum_returns(rets)
    expected = pd.Series([0.01, 0.0302, 0.014747, 0.04518941])
    pd.testing.assert_series_equal(got.reset_index(drop=True), expected, atol=1e-8)


def test_import_plotting_when_matplotlib_present():
    matplotlib = pytest.importorskip("matplotlib")
    import qlib_cost.plotting as plotting

    assert plotting.Empyrical.__module__.startswith("fincore")
    assert matplotlib is not None


def test_xtquant_not_a_dependency():
    """Fork policy guard: this repo is read-only for market bars — no QMT/xtquant.

    1.3 pins xtquant in deploy/requirements-runtime.txt (win32); that artifact and
    the QMT download pipeline stay with the original repo (AGENTS.md scope).
    """
    req = (REPO / "requirements.txt").read_text(encoding="utf-8")
    xtquant_lines = [
        ln
        for ln in req.splitlines()
        if ln.strip() and not ln.strip().startswith("#") and "xtquant" in ln.lower()
    ]
    assert xtquant_lines == [], xtquant_lines


def test_qlib_cost_requirements_pin_fincore():
    text = (REPO / "qlib_cost" / "requirements.txt").read_text(encoding="utf-8")
    assert "fincore==0.3.0" in text
    assert "empyrical==" not in text
