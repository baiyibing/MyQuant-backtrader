from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.research.csv_ledger import (
    IndependentExitPosition,
    IndependentGroup,
    IndependentPosition,
    SimState,
    position_is_open,
)
from backtest.research.csv_minute_backtest import (
    _NUMBA_SCAN_AVAILABLE,
    _independent_numba_prefix,
    independent_ladder_first_bar,
)
from backtest.research.minute_cash_order import (
    _independent_skip_supported,
    advance_independent_exit,
    fill_side_pending,
    peak_dd_clear_exits,
    scale_out_exits,
    step_stop_exits,
)
from backtest.research.minute_held_scan_core import HeldMinuteCursor
from backtest.research.strategy6_53_rules import record_strategy6_53_params, take_profit_reason

pytestmark = pytest.mark.skipif(
    not _NUMBA_SCAN_AVAILABLE, reason="numba not installed"
)

CODE = "600000.SH"
PID = "600000.SH@20251103"
DAY = pd.Timestamp("2025-11-04")
SIDE = {
    "step_stop_pct": 0.10,
    "scale_out_step": 0.05,
    "scale_out_frac": 0.05,
    "scale_out_anchor": "weighted",
    "peak_dd_exit": 0.15,
    "peak_dd_sessions": 15,
    "fill_config": None,
    "low_arr": None,
}


def _tp(px, cost, peak, n_days=1):
    return take_profit_reason(px, cost, peak, n_days)


def _session(
    *,
    n=20,
    base=10.0,
    highs=None,
    closes=None,
    opens=None,
    lows=None,
    cost=10.0,
    peak=10.0,
    peak_hm=570,
    shares=1000,
    n_days=1,
    can_sell=True,
    stop_pct=0.05,
    extra_lots=(),
    scale_steps=0,
    peak_dd_start=None,
    take_profit=_tp,
    sell_gate=None,
    attach_low=True,
    limit_down=0.01,
):
    hm = np.arange(570, 570 + n, dtype=np.int64)
    o = np.full(n, base if opens is None else 0.0, dtype=np.float64)
    h = np.full(n, base + 0.05, dtype=np.float64)
    low = np.full(n, base - 0.05, dtype=np.float64)
    c = np.full(n, base, dtype=np.float64)
    if opens is not None:
        o[:] = np.asarray(opens, dtype=np.float64)
    if highs is not None:
        h[:] = np.asarray(highs, dtype=np.float64)
    if lows is not None:
        low[:] = np.asarray(lows, dtype=np.float64)
    if closes is not None:
        c[:] = np.asarray(closes, dtype=np.float64)
    lot = IndependentPosition(
        CODE, shares, cost, 0, peak, peak_hm=peak_hm,
        lot_id=0, position_id=PID, entry_signal_date="20251103",
    )
    group = IndependentGroup(
        CODE, "20251103", 10_000.0, lot,
        scale_steps=scale_steps, peak_dd_start=peak_dd_start, anchor_cost=cost,
    )
    st = SimState(cash=27_000_000)
    st.positions[CODE] = [lot, *list(extra_lots)]
    st.book_state["s8_independent"] = {
        "name": "version6_53",
        "name_budget": 10_000.0,
        "cost_anchor": "first_lot",
        "groups": {PID: group},
        "add_step": 0.2,
        "step_frac": 1.0,
        "min_lot_top_up": True,
    }
    st.held_fill_states = {}
    pos = IndependentExitPosition(st, PID, group, day_i=1, day=DAY)
    cursor = HeldMinuteCursor(
        o, h, c, cost=cost, peak=peak, n_days=n_days, can_sell=can_sell,
        stop_pct=stop_pct, profit_base=0.0, trail_ratio=0.0,
        pos_trail=0.0, limit_down=limit_down, hm=hm, peak_hm=peak_hm,
        peak_gap_min=15, take_profit=take_profit, sell_gate=sell_gate,
        l=low if attach_low else None,
        minute_stop_trigger="close",
    )
    return st, pos, cursor, (1000.0, float(limit_down))


def _cursor(*, opens, highs, closes, cost, peak, peak_hm, n_days, can_sell=True, limit_down=0.01):
    n = len(closes)
    hm = np.arange(570, 570 + n, dtype=np.int64)
    return HeldMinuteCursor(
        np.asarray(opens, dtype=np.float64),
        np.asarray(highs, dtype=np.float64),
        np.asarray(closes, dtype=np.float64),
        cost=cost, peak=peak, n_days=n_days, can_sell=can_sell,
        stop_pct=0.05, profit_base=0.0, trail_ratio=0.0,
        pos_trail=0.0, limit_down=limit_down, hm=hm, peak_hm=peak_hm,
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


def _run_bars(st, pos, cursor, limits, hooks, python_from=0):
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
                fill_side_pending(
                    st, CODE, pos, float(cursor.o[bar_idx]), DAY, 1,
                    limits, hm=int(at_hm),
                )
            if hooks is None:
                continue
            if phase == "close" and hooks.get("step_stop_pct"):
                step_stop_exits(
                    st, CODE, pos, float(cursor.c[bar_idx]), DAY, 1,
                    limits, step_stop_pct=hooks["step_stop_pct"],
                    open_px=float(cursor.o[bar_idx]), hm=int(at_hm),
                )
            if phase == "close" and hooks.get("scale_out_step"):
                scale_out_exits(
                    st, CODE, pos, float(cursor.c[bar_idx]), DAY, 1,
                    limits, scale_step=hooks["scale_out_step"],
                    scale_frac=hooks.get("scale_out_frac", 0.05),
                    scale_anchor=hooks.get("scale_out_anchor", "first_lot"),
                    open_px=float(cursor.o[bar_idx]), hm=int(at_hm),
                )
            if phase == "close" and hooks.get("peak_dd_exit"):
                peak_dd_clear_exits(
                    st, CODE, pos, float(cursor.c[bar_idx]), DAY, 1,
                    limits, peak_dd_exit=hooks["peak_dd_exit"],
                    peak_dd_sessions=hooks.get("peak_dd_sessions", 15),
                    open_px=float(cursor.o[bar_idx]), hm=int(at_hm),
                )
    return st, pos


def _drive_python(**kwargs):
    hooks = kwargs.pop("side_hooks", SIDE)
    st, pos, cursor, limits = _session(**kwargs)
    record_strategy6_53_params(st, stop_pct=float(kwargs.get("stop_pct", 0.05)))
    return _run_bars(st, pos, cursor, limits, hooks, python_from=0)


def _drive_numba_prefix(**kwargs):
    hooks = kwargs.pop("side_hooks", SIDE)
    st, pos, cursor, limits = _session(**kwargs)
    record_strategy6_53_params(st, stop_pct=float(kwargs.get("stop_pct", 0.05)))
    python_from = _independent_numba_prefix(
        st, pos, cursor, day_i=1, side_hooks=hooks, hm_lo=0, hm_hi=24 * 60,
    )
    return _run_bars(st, pos, cursor, limits, hooks, python_from=python_from)


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
    assert int(st_l.stats.get("defer_sell_limit_down", 0)) == int(
        st_r.stats.get("defer_sell_limit_down", 0)
    )


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


def test_numba_prefix_matches_full_python_cases():
    cases = [
        dict(n=20, n_days=2),
        dict(closes=[10.0] * 19 + [9.40], lows=[9.90] * 19 + [9.30]),
        dict(
            n=3, base=15.68, cost=15.68, peak=15.68, peak_hm=895, shares=100,
            opens=[15.32, 15.18, 14.90], highs=[15.32, 15.50, 14.94],
            lows=[15.32, 14.68, 14.86], closes=[15.32, 14.85, 14.92],
            attach_low=False,
        ),
        dict(closes=[10.0] * 19 + [10.60], highs=[10.05] * 19 + [10.60],
             opens=[10.0] * 19 + [10.50]),
        dict(
            n=3, base=7.97, cost=7.97, peak=7.97, peak_hm=895, shares=200,
            opens=[7.62, 7.64, 7.50], highs=[7.62, 7.70, 7.50],
            lows=[7.62, 7.50, 7.39], closes=[7.62, 7.51, 7.46],
            attach_low=False,
        ),
    ]
    for kwargs in cases:
        _same_trades(_drive_numba_prefix(**kwargs), _drive_python(**kwargs))


def test_numba_prefix_t0_matches_full_python():
    kwargs = dict(
        n=20, n_days=0, can_sell=False,
        highs=[12.0] * 20, closes=[10.0] * 20, opens=[10.0] * 20, lows=[9.9] * 20,
    )
    st_n, pos_n = _drive_numba_prefix(**kwargs, side_hooks=None)
    st_f, pos_f = _drive_python(**kwargs, side_hooks=None)
    _same_trades((st_n, pos_n), (st_f, pos_f))
    assert pos_n.peak == 10.0


def test_numba_prefix_000422_two_days():
    day1 = dict(
        n=3, base=17.17, cost=17.17, peak=17.17, peak_hm=-1, shares=100,
        n_days=1, can_sell=True, attach_low=False,
        opens=[17.22, 17.26, 17.17], highs=[17.22, 17.35, 17.29],
        lows=[17.22, 17.05, 17.16], closes=[17.22, 17.13, 17.18],
    )
    nb1, py1 = _drive_numba_prefix(**day1), _drive_python(**day1)
    _same_trades(nb1, py1)
    assert nb1[1].peak == 17.35
    n = 19
    opens = [16.70] * n
    highs = [16.80] * n
    lows = [16.40] * n
    closes = [16.70] * n
    opens[0] = highs[0] = lows[0] = closes[0] = 16.63
    opens[1] = highs[1] = 16.60
    lows[1] = 16.40
    closes[1] = 16.49
    opens[-1], highs[-1], lows[-1], closes[-1] = 16.52, 16.52, 16.46, 16.47
    day2 = dict(
        n=n, base=17.17, cost=17.17, peak=nb1[1].peak, peak_hm=nb1[1].peak_hm,
        shares=100, n_days=2, can_sell=True, attach_low=False,
        opens=opens, highs=highs, lows=lows, closes=closes,
    )
    nb2, py2 = _drive_numba_prefix(**day2), _drive_python(**day2)
    _same_trades(nb2, py2)
    sold = [t for t in nb2[0].trades if str(t["reason"]).startswith("trail:")]
    assert sold
    assert abs(float(sold[0]["price"]) - 16.47) < 1e-9


def test_numba_prefix_002556_three_days():
    day1 = dict(
        n=3, base=6.47, cost=6.47, peak=6.47, peak_hm=-1, shares=300,
        n_days=1, can_sell=True, attach_low=False,
        opens=[6.50, 6.55, 6.50], highs=[6.50, 6.63, 6.52],
        lows=[6.45, 6.48, 6.48], closes=[6.50, 6.52, 6.50],
    )
    nb1, py1 = _drive_numba_prefix(**day1), _drive_python(**day1)
    _same_trades(nb1, py1)
    day2 = dict(
        n=5, base=6.47, cost=6.47, peak=nb1[1].peak, peak_hm=nb1[1].peak_hm,
        shares=300, n_days=2, can_sell=True, attach_low=False,
        opens=[6.55, 6.60, 6.58, 6.56, 6.54],
        highs=[6.55, 6.70, 6.60, 6.58, 6.56],
        lows=[6.50, 6.58, 6.54, 6.52, 6.50],
        closes=[6.55, 6.62, 6.58, 6.56, 6.54],
    )
    nb2, py2 = _drive_numba_prefix(**day2), _drive_python(**day2)
    _same_trades(nb2, py2)
    n = 19
    opens = [6.50] * n
    highs = [6.55] * n
    lows = [6.40] * n
    closes = [6.50] * n
    opens[-1], highs[-1], lows[-1], closes[-1] = 6.52, 6.52, 6.36, 6.37
    day3 = dict(
        n=n, base=6.47, cost=6.47, peak=nb2[1].peak, peak_hm=nb2[1].peak_hm,
        shares=300, n_days=3, can_sell=True, attach_low=False,
        opens=opens, highs=highs, lows=lows, closes=closes,
    )
    nb3, py3 = _drive_numba_prefix(**day3), _drive_python(**day3)
    _same_trades(nb3, py3)
    sold = [t for t in nb3[0].trades if str(t["reason"]).startswith("trail:")]
    assert sold
    assert abs(float(sold[0]["price"]) - 6.37) < 1e-9


def test_numba_prefix_301265_intraday_peak_then_trail():
    n = 20
    opens = [15.40] * n
    highs = [15.40] * n
    lows = [15.20] * n
    closes = [15.40] * n
    highs[0] = 16.33
    closes[-1] = 15.02
    lows[-1] = 15.00
    kwargs = dict(
        n=n, base=15.33, cost=15.33, peak=15.33, peak_hm=-1, shares=100,
        n_days=1, can_sell=True, attach_low=False,
        opens=opens, highs=highs, lows=lows, closes=closes,
    )
    nb, py = _drive_numba_prefix(**kwargs), _drive_python(**kwargs)
    _same_trades(nb, py)
    assert nb[1].peak == 16.33
    sold = [t for t in nb[0].trades if str(t["reason"]).startswith("trail:")]
    assert sold
    assert abs(float(sold[0]["price"]) - 15.02) < 1e-9


def test_sell_gate_disables_numba_prefix():
    st, pos, cursor, _limits = _session(sell_gate=lambda *_args: None)
    record_strategy6_53_params(st, stop_pct=0.05)
    assert _independent_skip_supported(cursor) is False
    idx = _independent_numba_prefix(
        st, pos, cursor, day_i=1, side_hooks=SIDE, hm_lo=0, hm_hi=24 * 60,
    )
    assert idx == 0


def test_env_off_forces_full_python(monkeypatch):
    monkeypatch.setenv("OSKH_INDEPENDENT_NUMBA", "0")
    st, pos, cursor, _limits = _session(n_days=2)
    record_strategy6_53_params(st, stop_pct=0.05)
    idx = _independent_numba_prefix(
        st, pos, cursor, day_i=1, side_hooks=SIDE, hm_lo=0, hm_hi=24 * 60,
    )
    assert idx == 0
    assert pos.peak == 10.0


def test_numba_limit_down_open_still_returns_scale_out_bar():
    n = 8
    opens = [10.0] * n
    highs = [10.05] * n
    closes = [10.0] * 4 + [10.60] * 4
    highs[4:] = [10.60] * 4
    cursor = _cursor(
        opens=opens, highs=highs, closes=closes,
        cost=10.0, peak=10.0, peak_hm=570, n_days=2, limit_down=10.0,
    )
    idx, peak, _hm = _first(cursor, scale_step=0.05, scale_anchor=10.0, scale_steps=0)
    assert idx == 4
    assert peak == 10.05


def test_numba_prefix_limit_down_open_counts_scale_out_defer():
    n = 8
    kwargs = dict(
        n=n, n_days=2, limit_down=10.0, shares=2000,
        opens=[10.0] * n,
        highs=[10.05] * 4 + [10.60] * 4,
        lows=[9.90] * n,
        closes=[10.0] * 4 + [10.60] * 4,
    )
    nb, py = _drive_numba_prefix(**kwargs), _drive_python(**kwargs)
    _same_trades(nb, py)
    assert nb[0].trades == []
    assert int(nb[0].stats["defer_sell_limit_down"]) == 4
