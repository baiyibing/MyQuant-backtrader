from __future__ import annotations

import numpy as np
import pytest

from backtest.research.csv_ledger import position_is_open
from backtest.research.csv_minute_backtest import (
    _NUMBA_SCAN_AVAILABLE,
    _independent_numba_prefix,
    independent_ladder_first_bar,
)
from backtest.research.minute_cash_order import (
    advance_independent_exit,
    fill_side_pending,
    peak_dd_clear_exits,
    scale_out_exits,
    step_stop_exits,
)
from backtest.research.minute_held_scan_core import HeldMinuteCursor
from backtest.research.strategy6_53_rules import record_strategy6_53_params, take_profit_reason
from tests.test_independent_held_skip import CODE, DAY, SIDE, _session, _drive


pytestmark = pytest.mark.skipif(
    not _NUMBA_SCAN_AVAILABLE, reason="numba not installed"
)


def _cursor(*, opens, highs, closes, cost, peak, peak_hm, n_days, can_sell=True):
    n = len(closes)
    hm = np.arange(570, 570 + n, dtype=np.int64)
    return HeldMinuteCursor(
        np.asarray(opens, dtype=np.float64),
        np.asarray(highs, dtype=np.float64),
        np.asarray(closes, dtype=np.float64),
        cost=cost, peak=peak, n_days=n_days, can_sell=can_sell,
        stop_pct=0.05, profit_base=0.0, trail_ratio=0.0,
        pos_trail=0.0, limit_down=0.01, hm=hm, peak_hm=peak_hm,
        peak_gap_min=15, take_profit=take_profit_reason,
        minute_stop_trigger="close",
    )


def _first(cursor, **overrides):
    args = dict(
        day_i=2,
        tp_min_days=1,
        band_width=0.05,
        give_base=0.05,
        give_step=0.03,
        scale_step=0.0,
        scale_steps=0,
        scale_anchor=0.0,
        peak_dd=0.0,
        peak_dd_start=-1,
        peak_dd_sessions=15,
        step_costs=[],
        step_stop_pct=0.0,
        hm_lo=0,
        hm_hi=24 * 60,
    )
    args.update(overrides)
    return independent_ladder_first_bar(cursor, **args)


def test_numba_t0_writes_no_peak_and_no_action():
    cursor = _cursor(
        opens=[10.0, 10.1], highs=[12.0, 12.0], closes=[10.0, 10.0],
        cost=10.0, peak=10.0, peak_hm=-1, n_days=0, can_sell=False,
    )
    idx, peak, peak_hm = _first(cursor)
    assert idx == -1
    assert peak == 10.0
    assert peak_hm == -1


def test_numba_stop_on_second_bar():
    cursor = _cursor(
        opens=[15.32, 15.18], highs=[15.32, 15.50], closes=[15.32, 14.85],
        cost=15.68, peak=15.68, peak_hm=895, n_days=1,
    )
    idx, peak, _peak_hm = _first(cursor)
    assert idx == 1
    assert peak == 15.68


def test_numba_000422_trail_after_peak_gap():
    n = 19
    opens = [16.70] * n
    highs = [16.80] * n
    closes = [16.70] * n
    opens[0] = highs[0] = closes[0] = 16.63
    opens[1] = highs[1] = 16.60
    closes[1] = 16.49
    opens[-1] = highs[-1] = 16.52
    closes[-1] = 16.47
    cursor = _cursor(
        opens=opens, highs=highs, closes=closes,
        cost=17.17, peak=17.35, peak_hm=571, n_days=2,
    )
    idx, peak, peak_hm = _first(cursor)
    assert idx == n - 1
    assert peak == 17.35
    assert peak_hm == 571
    assert take_profit_reason(16.47, 17.17, 17.35, 2)


def test_numba_scale_out_is_an_action():
    cursor = _cursor(
        opens=[10.0, 10.6], highs=[10.0, 10.6], closes=[10.0, 10.6],
        cost=10.0, peak=10.0, peak_hm=570, n_days=2,
    )
    idx, _peak, _hm = _first(cursor, scale_step=0.05, scale_anchor=10.0, scale_steps=0)
    assert idx == 1


def _drive_numba_prefix(**kwargs):
    """Host-shaped path: compiled prefix, then original Python from the first action."""
    hooks = kwargs.pop("side_hooks", SIDE)
    st, pos, cursor, limits = _session(**kwargs)
    record_strategy6_53_params(st, stop_pct=float(kwargs.get("stop_pct", 0.05)))
    python_from = _independent_numba_prefix(
        st, pos, cursor, day_i=1, side_hooks=hooks, hm_lo=0, hm_hi=24 * 60,
    )
    if python_from < 0:
        return st, pos
    for bar_idx, at_hm in enumerate(cursor.hm):
        if not position_is_open(st, pos):
            break
        if bar_idx < python_from:
            continue
        for phase in ("open", "close"):
            advance_independent_exit(
                st, CODE, pos, cursor, bar_idx, phase, limits,
                day=DAY, day_i=1,
            )
            if phase == "open":
                fill_side_pending(st, CODE, pos, float(cursor.o[bar_idx]), DAY, 1,
                                  limits, hm=int(at_hm))
            if hooks is None:
                continue
            if phase == "close" and hooks.get("step_stop_pct"):
                step_stop_exits(
                    st, CODE, pos, float(cursor.c[bar_idx]), DAY, 1,
                    limits, step_stop_pct=hooks["step_stop_pct"], hm=int(at_hm),
                )
            if phase == "close" and hooks.get("scale_out_step"):
                scale_out_exits(
                    st, CODE, pos, float(cursor.c[bar_idx]), DAY, 1,
                    limits, scale_step=hooks["scale_out_step"],
                    scale_frac=hooks.get("scale_out_frac", 0.05),
                    scale_anchor=hooks.get("scale_out_anchor", "first_lot"),
                    hm=int(at_hm),
                )
            if phase == "close" and hooks.get("peak_dd_exit"):
                peak_dd_clear_exits(
                    st, CODE, pos, float(cursor.c[bar_idx]), DAY, 1,
                    limits, peak_dd_exit=hooks["peak_dd_exit"],
                    peak_dd_sessions=hooks.get("peak_dd_sessions", 15),
                    hm=int(at_hm),
                )
    return st, pos


def _same_trades(left, right):
    st_l, pos_l = left
    st_r, pos_r = right
    assert [(t["side"], t["reason"], t["shares"], t["price"]) for t in st_l.trades] == [
        (t["side"], t["reason"], t["shares"], t["price"]) for t in st_r.trades
    ]
    assert pos_l.peak == pos_r.peak
    assert pos_l.peak_hm == pos_r.peak_hm
    assert pos_l.group.scale_steps == pos_r.group.scale_steps
    assert pos_l.group.peak_dd_start == pos_r.group.peak_dd_start
    assert pos_l.shares == pos_r.shares


def test_numba_prefix_matches_full_python_stop_and_trail():
    cases = [
        dict(n=20, n_days=2),
        dict(closes=[10.0] * 19 + [9.40], lows=[9.90] * 19 + [9.30]),
        dict(
            n=3, base=15.68, cost=15.68, peak=15.68, peak_hm=895, shares=100,
            opens=[15.32, 15.18, 14.90], highs=[15.32, 15.50, 14.94],
            lows=[15.32, 14.68, 14.86], closes=[15.32, 14.85, 14.92],
            attach_low=False,
        ),
        dict(
            n=19, base=17.17, cost=17.17, peak=17.35, peak_hm=571, shares=100,
            n_days=2,
            opens=[16.70] * 18 + [16.52],
            highs=[16.80] * 18 + [16.52],
            lows=[16.40] * 18 + [16.46],
            closes=[16.70] * 18 + [16.47],
            attach_low=False,
        ),
        dict(closes=[10.0] * 19 + [10.60], highs=[10.05] * 19 + [10.60],
             opens=[10.0] * 19 + [10.50]),
    ]
    cases[3]["opens"][0] = cases[3]["highs"][0] = cases[3]["lows"][0] = cases[3]["closes"][0] = 16.63
    cases[3]["opens"][1] = cases[3]["highs"][1] = 16.60
    cases[3]["lows"][1] = 16.40
    cases[3]["closes"][1] = 16.49
    for kwargs in cases:
        full = _drive(False, **kwargs)
        numba = _drive_numba_prefix(**kwargs)
        _same_trades((numba[0], numba[1]), (full[0], full[1]))


def test_numba_prefix_t0_matches_full_python():
    kwargs = dict(
        n=20, n_days=0, can_sell=False,
        highs=[12.0] * 20, closes=[10.0] * 20, opens=[10.0] * 20, lows=[9.9] * 20,
    )
    st_f, pos_f, _q, _e = _drive(False, **kwargs)
    st_n, pos_n = _drive_numba_prefix(**kwargs, side_hooks=None)
    _same_trades((st_n, pos_n), (st_f, pos_f))
    assert pos_n.peak == 10.0
