"""Minute layout switches: variable/fixed length and frame/array store."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from backtest.research.csv_minute_backtest import (
    _buy_px,
    _chase_quotes,
    _finite_hm_bucket,
    _open_quote_for,
)
from backtest.research.minute_grid import (
    SESSION_BARS,
    SESSION_HM,
    MinuteBars,
    apply_minute_layout,
    densify_frame,
    resolve_minute_layout,
)
from backtest.research.minute_held_scan_core import HeldMinuteCursor


def _frame(rows, ymd="20251104"):
    return pd.DataFrame(
        {
            "open": [row[1] for row in rows],
            "high": [row[2] for row in rows],
            "low": [row[3] for row in rows],
            "close": [row[4] for row in rows],
            "ymd": ymd,
            "hm": [row[0] for row in rows],
        }
    )


def test_session_grid_is_242_and_keeps_open_and_close():
    assert SESSION_BARS == 242
    assert int(SESSION_HM[0]) == 9 * 60 + 30
    assert int(SESSION_HM[120]) == 11 * 60 + 30
    assert int(SESSION_HM[121]) == 13 * 60
    assert int(SESSION_HM[241]) == 15 * 60
    assert 12 * 60 not in set(SESSION_HM.tolist())


def test_resolve_env_and_explicit_override(monkeypatch):
    monkeypatch.setenv("OSKH_MINUTE_LENGTH", "fixed")
    monkeypatch.setenv("OSKH_MINUTE_STORE", "array")
    assert resolve_minute_layout(None, None) == ("fixed", "array")
    assert resolve_minute_layout("variable", "frame") == ("variable", "frame")
    with pytest.raises(ValueError):
        resolve_minute_layout("240", "frame")


def test_default_layout_is_the_same_object():
    bars = {"600000.SH": _frame([(9 * 60 + 30, 1, 1, 1, 1)])}
    assert apply_minute_layout(bars, "variable", "frame") is bars


def test_fixed_frame_leaves_gaps_empty_and_keeps_last_duplicate():
    src = _frame(
        [
            (9 * 60 + 30, 10.0, 10.2, 9.8, 10.1),
            (9 * 60 + 30, 11.0, 11.2, 10.8, 11.1),
            (9 * 60 + 32, 12.0, 12.2, 11.8, 12.1),
            (12 * 60, 99.0, 99.0, 99.0, 99.0),
        ]
    )
    dense = densify_frame(src)
    assert len(dense) == 242
    assert len(src) == 4
    assert dense["close"].iloc[0] == pytest.approx(11.1)
    assert np.isnan(dense["close"].iloc[1])
    assert dense["close"].iloc[2] == pytest.approx(12.1)
    assert int(dense["hm"].iloc[0]) == 9 * 60 + 30
    assert 12 * 60 not in set(dense["hm"].tolist())
    assert list(dense["ymd"].unique()) == ["20251104"]


def test_day_without_session_bars_stays_absent():
    src = _frame([(12 * 60, 1.0, 1.0, 1.0, 1.0)])
    assert densify_frame(src).empty


def test_array_store_matches_frame_values():
    src = _frame(
        [
            (9 * 60 + 30, 10.0, 10.4, 9.9, 10.2),
            (15 * 60, 10.2, 10.5, 10.1, 10.3),
        ]
    )
    book = {"600000.SH": src}
    fixed = apply_minute_layout(book, "fixed", "frame")["600000.SH"]
    arrays = apply_minute_layout(book, "fixed", "array")["600000.SH"]
    variable = apply_minute_layout(book, "variable", "array")["600000.SH"]
    assert isinstance(fixed, pd.DataFrame)
    assert isinstance(arrays, MinuteBars)
    assert len(fixed) == 242
    assert len(arrays) == 242
    assert len(variable) == 2
    np.testing.assert_allclose(arrays.close, fixed["close"].to_numpy(np.float64), equal_nan=True)
    day = arrays.iloc[0:242]
    assert len(day) == 242
    assert day["low"].min() == pytest.approx(9.9)
    assert arrays.spans["20251104"] == (0, 242)


def test_empty_1455_falls_through_and_does_not_quote():
    sparse = _frame(
        [
            (14 * 60 + 50, 9.0, 9.2, 8.9, 9.1),
            (15 * 60, 9.1, 9.3, 9.0, 9.2),
        ]
    )
    dense = densify_frame(sparse)
    assert _buy_px(sparse) == pytest.approx(9.1)
    assert _buy_px(dense) == pytest.approx(9.1)
    arrays = MinuteBars.from_frame(dense)
    assert _buy_px(arrays) == pytest.approx(9.1)
    slot = int(np.flatnonzero(dense["hm"].to_numpy() == 14 * 60 + 55)[0])
    assert np.isnan(dense["close"].iloc[slot])


def test_chase_and_open_skip_empty_slots():
    sparse = _frame(
        [
            (9 * 60 + 31, 10.0, 10.2, 9.9, 10.1),
            (9 * 60 + 40, 10.1, 10.3, 10.0, 10.2),
            (14 * 60 + 55, 10.2, 10.4, 10.1, 10.3),
        ]
    )
    dense = densify_frame(sparse)
    assert _chase_quotes(sparse) == pytest.approx(_chase_quotes(dense))
    assert _open_quote_for(sparse) is None
    assert _open_quote_for(dense) is None
    opened = _frame([(9 * 60 + 30, 8.5, 8.6, 8.4, 8.55)])
    quote = _open_quote_for(opened)
    assert float(quote["open"]) == pytest.approx(8.5)
    assert _open_quote_for(densify_frame(opened))["open"] == pytest.approx(8.5)


def test_bucket_ignores_empty_target_slot():
    dense = densify_frame(
        _frame(
            [
                (14 * 60 + 50, 9.0, 9.1, 8.9, 9.05),
                (15 * 60, 9.1, 9.2, 9.0, 9.15),
            ]
        )
    )
    assert _finite_hm_bucket(dense, 14 * 60 + 55, 14 * 60 + 30) == 14 * 60 + 50
    present = _frame([(14 * 60 + 55, 9.0, 9.1, 8.9, 9.2)])
    assert _finite_hm_bucket(present, 14 * 60 + 55, 14 * 60 + 30) == 14 * 60 + 55


def test_last_finite_bar_owns_close_clear_and_nan_does_not_move_peak():
    cursor = HeldMinuteCursor(
        o=np.array([10.0, 10.0, np.nan]),
        h=np.array([10.0, 10.0, np.nan]),
        c=np.array([10.0, 11.0, np.nan]),
        cost=10.0,
        peak=10.0,
        n_days=2,
        can_sell=True,
        stop_pct=None,
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([570, 571, 572]),
        close_clear=lambda _cost, _peak, _n: "close_clear",
    )
    assert cursor.advance(2, "open") is None
    assert cursor.peak == pytest.approx(10.0)
    found = None
    for idx in range(3):
        for phase in ("open", "close"):
            event = cursor.advance(idx, phase)
            if event is not None:
                found = event
                break
        if found is not None:
            break
    assert found is not None
    assert found[0] == 1
    assert found[2] == "close_clear"
