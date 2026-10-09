from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.research.csv_ledger import (
    IndependentExitPosition,
    IndependentGroup,
    IndependentPosition,
    SimState,
)
from backtest.research.minute_cash_order import (
    drive_independent_exit_bars,
    _independent_skip_supported,
)
from backtest.research.minute_held_scan_core import HeldMinuteCursor
from backtest.research.strategy6_53_rules import take_profit_reason

CODE = "600000.SH"
PID = "600000.SH@20251103"
DAY = pd.Timestamp("2025-11-04")


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
        pos_trail=0.0, limit_down=0.01, hm=hm, peak_hm=peak_hm,
        peak_gap_min=15, take_profit=take_profit, sell_gate=sell_gate,
        l=low if attach_low else None,
        minute_stop_trigger="close",
    )
    return st, pos, cursor, (1000.0, 0.01)


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


def _drive(skip_quiet, **kwargs):
    st, pos, cursor, limits = _session(**kwargs)
    quiet, evaluated = drive_independent_exit_bars(
        st, CODE, pos, cursor, limits,
        day=DAY, day_i=1, side_hooks=SIDE, skip_quiet=skip_quiet,
    )
    return st, pos, quiet, evaluated


def _pair(**kwargs):
    skipped = _drive(True, **kwargs)
    full = _drive(False, **kwargs)
    return skipped, full


def _same_outcome(skipped, full):
    st_s, pos_s, _q, _e = skipped
    st_f, pos_f, _q2, _e2 = full
    assert [(t["side"], t["reason"], t["shares"], t["price"]) for t in st_s.trades] == [
        (t["side"], t["reason"], t["shares"], t["price"]) for t in st_f.trades
    ]
    assert pos_s.peak == pos_f.peak
    assert pos_s.peak_hm == pos_f.peak_hm
    assert pos_s.group.scale_steps == pos_f.group.scale_steps
    assert pos_s.group.peak_dd_start == pos_f.group.peak_dd_start
    assert pos_s.shares == pos_f.shares


def test_quiet_session_skips_and_matches_full_peak():
    skipped, full = _pair(n_days=2)
    _same_outcome(skipped, full)
    _st, _pos, quiet, evaluated = skipped
    assert quiet == 19
    assert evaluated == 1
    assert full[2] == 0
    assert full[3] > 0


def test_stop_touch_matches_full_path():
    n = 20
    closes = [10.0] * (n - 1) + [9.40]
    skipped, full = _pair(closes=closes, lows=[9.90] * (n - 1) + [9.30])
    _same_outcome(skipped, full)
    assert any(t["reason"].startswith("stop_loss") for t in skipped[0].trades)


def test_ladder_trail_after_peak_gap_matches_full_path():
    n = 20
    highs = [10.05] * n
    highs[0] = 12.0
    closes = [10.8] * n
    closes[-1] = 10.20
    skipped, full = _pair(highs=highs, closes=closes, opens=[10.8] * n, lows=[10.2] * n)
    _same_outcome(skipped, full)
    assert any(str(t["reason"]).startswith("trail:") for t in skipped[0].trades)


def test_scale_out_threshold_matches_full_path():
    n = 20
    closes = [10.0] * (n - 1) + [10.60]
    highs = [10.05] * (n - 1) + [10.60]
    skipped, full = _pair(closes=closes, highs=highs, opens=[10.0] * (n - 1) + [10.50])
    _same_outcome(skipped, full)
    assert skipped[1].group.scale_steps >= 1


def test_peak_dd_latch_and_reset_match_full_path():
    n = 20
    closes = [8.40] + [10.0] * (n - 1)
    lows = [8.30] + [9.90] * (n - 1)
    skipped, full = _pair(closes=closes, lows=lows, peak_dd_start=None)
    _same_outcome(skipped, full)
    recovered_s, recovered_f = _pair(
        closes=[10.0] * n, highs=[10.0] * n, opens=[10.0] * n, lows=[10.0] * n,
        peak_dd_start=0, peak=10.0,
    )
    _same_outcome(recovered_s, recovered_f)
    assert recovered_s[1].group.peak_dd_start is None


def test_t0_peak_stays_at_buy_price():
    n = 20
    kwargs = dict(
        n=n, n_days=0, can_sell=False,
        highs=[12.0] * n, closes=[10.0] * n, opens=[10.0] * n, lows=[9.9] * n,
    )
    outcomes = []
    for skip in (True, False):
        st, pos, cursor, limits = _session(**kwargs)
        quiet, evaluated = drive_independent_exit_bars(
            st, CODE, pos, cursor, limits,
            day=DAY, day_i=1, side_hooks=None, skip_quiet=skip,
        )
        outcomes.append((st, pos, quiet, evaluated))
    _same_outcome(outcomes[0], outcomes[1])
    assert outcomes[0][1].peak == 10.0
    assert outcomes[1][1].peak == 10.0
    assert outcomes[0][2] == 0
    assert outcomes[0][3] == n


def test_300017_t1_stop_host_like_no_low_array():
    """20260129 300017.SZ: T+1 09:31 close 14.85 vs cost 15.68, host l=None."""
    opens = [15.32, 15.18, 14.90]
    highs = [15.32, 15.50, 14.94]
    lows = [15.32, 14.68, 14.86]
    closes = [15.32, 14.85, 14.92]
    skipped, full = _pair(
        n=3, base=15.68, cost=15.68, peak=15.68, peak_hm=895, shares=100,
        opens=opens, highs=highs, lows=lows, closes=closes, attach_low=False,
    )
    _same_outcome(skipped, full)
    assert any(
        t["reason"] == "stop_loss:touch" and abs(float(t["price"]) - 14.85) < 1e-9
        for t in skipped[0].trades
    )
    assert skipped[3] >= 1


def test_002996_t2_trail_needs_prior_day_peak():
    """20260129 002996.SZ makes a T+1 high 9.16; next open 8.45 must trail."""
    day1 = dict(
        n=3, base=8.87, cost=8.87, peak=8.87, peak_hm=895, shares=200,
        n_days=1, can_sell=True, attach_low=False,
        opens=[9.08, 9.08, 8.95], highs=[9.08, 9.13, 9.00],
        lows=[9.08, 8.93, 8.95], closes=[9.08, 8.95, 8.98],
    )
    skipped, full = _pair(**day1)
    _same_outcome(skipped, full)
    assert skipped[1].peak == full[1].peak
    assert skipped[1].peak > 8.87

    day2 = dict(
        n=2, base=8.87, cost=8.87, peak=skipped[1].peak, peak_hm=skipped[1].peak_hm,
        shares=200, n_days=2, can_sell=True, attach_low=False,
        opens=[8.45, 8.49], highs=[8.45, 8.55], lows=[8.45, 8.41],
        closes=[8.45, 8.55],
    )
    trail_s, trail_f = _pair(**day2)
    _same_outcome(trail_s, trail_f)
    assert any(str(t["reason"]).startswith("trail:") for t in trail_s[0].trades)


def test_301265_t1_intraday_peak_then_trail():
    """20260129 301265.SZ: T+1 high 16.33 then 15.02 trail after the gap."""
    n = 20
    opens = [15.40] * n
    highs = [15.40] * n
    lows = [15.20] * n
    closes = [15.40] * n
    highs[0] = 16.33
    closes[-1] = 15.02
    lows[-1] = 15.00
    skipped, full = _pair(
        n=n, base=15.33, cost=15.33, peak=15.33, peak_hm=-1, shares=100,
        n_days=1, can_sell=True, attach_low=False,
        opens=opens, highs=highs, lows=lows, closes=closes,
    )
    _same_outcome(skipped, full)
    assert skipped[1].peak == 16.33
    sold = [t for t in skipped[0].trades if str(t["reason"]).startswith("trail:")]
    assert sold
    assert abs(float(sold[0]["price"]) - 15.02) < 1e-9


def test_002556_t3_trail_needs_t2_new_high():
    """20260202 002556.SZ: T+2 high 6.70 then T+3 6.37 trail."""
    day1 = dict(
        n=3, base=6.47, cost=6.47, peak=6.47, peak_hm=-1, shares=300,
        n_days=1, can_sell=True, attach_low=False,
        opens=[6.50, 6.55, 6.50], highs=[6.50, 6.63, 6.52],
        lows=[6.45, 6.48, 6.48], closes=[6.50, 6.52, 6.50],
    )
    skipped, full = _pair(**day1)
    _same_outcome(skipped, full)
    assert skipped[1].peak == 6.63

    day2 = dict(
        n=5, base=6.47, cost=6.47, peak=skipped[1].peak, peak_hm=skipped[1].peak_hm,
        shares=300, n_days=2, can_sell=True, attach_low=False,
        opens=[6.55, 6.60, 6.58, 6.56, 6.54],
        highs=[6.55, 6.70, 6.60, 6.58, 6.56],
        lows=[6.50, 6.58, 6.54, 6.52, 6.50],
        closes=[6.55, 6.62, 6.58, 6.56, 6.54],
    )
    skipped2, full2 = _pair(**day2)
    _same_outcome(skipped2, full2)
    assert skipped2[1].peak == 6.70

    n = 19
    opens = [6.50] * n
    highs = [6.55] * n
    lows = [6.40] * n
    closes = [6.50] * n
    opens[-1], highs[-1], lows[-1], closes[-1] = 6.52, 6.52, 6.36, 6.37
    day3 = dict(
        n=n, base=6.47, cost=6.47, peak=skipped2[1].peak, peak_hm=skipped2[1].peak_hm,
        shares=300, n_days=3, can_sell=True, attach_low=False,
        opens=opens, highs=highs, lows=lows, closes=closes,
    )
    trail_s, trail_f = _pair(**day3)
    _same_outcome(trail_s, trail_f)
    sold = [t for t in trail_s[0].trades if str(t["reason"]).startswith("trail:")]
    assert sold
    assert abs(float(sold[0]["price"]) - 6.37) < 1e-9


def test_000422_t2_trail_after_peak_gap():
    """20260130 000422.SZ: T+1 peak 17.35@571, T+2 16.47 trail after 15m gap."""
    day1 = dict(
        n=3, base=17.17, cost=17.17, peak=17.17, peak_hm=-1, shares=100,
        n_days=1, can_sell=True, attach_low=False,
        opens=[17.22, 17.26, 17.17], highs=[17.22, 17.35, 17.29],
        lows=[17.22, 17.05, 17.16], closes=[17.22, 17.13, 17.18],
    )
    skipped, full = _pair(**day1)
    _same_outcome(skipped, full)
    assert skipped[1].peak == 17.35
    assert skipped[1].peak_hm == 571

    n = 19
    opens = [16.70] * n
    highs = [16.80] * n
    lows = [16.40] * n
    closes = [16.70] * n
    opens[0], highs[0], lows[0], closes[0] = 16.63, 16.63, 16.63, 16.63
    opens[1], highs[1], lows[1], closes[1] = 16.60, 16.60, 16.40, 16.49
    opens[-1], highs[-1], lows[-1], closes[-1] = 16.52, 16.52, 16.46, 16.47
    day2 = dict(
        n=n, base=17.17, cost=17.17, peak=skipped[1].peak, peak_hm=skipped[1].peak_hm,
        shares=100, n_days=2, can_sell=True, attach_low=False,
        opens=opens, highs=highs, lows=lows, closes=closes,
    )
    trail_s, trail_f = _pair(**day2)
    _same_outcome(trail_s, trail_f)
    sold = [t for t in trail_s[0].trades if str(t["reason"]).startswith("trail:")]
    assert sold
    assert abs(float(sold[0]["price"]) - 16.47) < 1e-9


def test_002291_t1_stop_matches_full_path():
    """20260130 002291.SZ: T+1 09:31 close 7.51 vs cost 7.97."""
    skipped, full = _pair(
        n=3, base=7.97, cost=7.97, peak=7.97, peak_hm=895, shares=200,
        opens=[7.62, 7.64, 7.50], highs=[7.62, 7.70, 7.50],
        lows=[7.62, 7.50, 7.39], closes=[7.62, 7.51, 7.46],
        attach_low=False,
    )
    _same_outcome(skipped, full)
    assert any(
        t["reason"] == "stop_loss:touch" and abs(float(t["price"]) - 7.51) < 1e-9
        for t in skipped[0].trades
    )


def test_sell_gate_disables_skip():
    st, pos, cursor, limits = _session(sell_gate=lambda *_args: None)
    assert _independent_skip_supported(cursor) is False
    quiet, evaluated = drive_independent_exit_bars(
        st, CODE, pos, cursor, limits,
        day=DAY, day_i=1, side_hooks=SIDE, skip_quiet=True,
    )
    assert quiet == 0
    assert evaluated == 20
