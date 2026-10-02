"""Grok X-04 round 1: initial peak and traceable rejected tail children."""

from datetime import date, timedelta

import pandas as pd
import pytest
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.ashare_fees import FeeSchedule
from backtest.research.tail_window_buy import TAIL_MINUTES, TailParent

A = "600000.SH"
D = date(2026, 9, 1)
ON = {"tail_window_buy": True, "fix_minute_cash_order": True,
      "tail_volume_unit": "shares"}


def _bar(hm, price=10.0, *, opening=None, volume=1_000_000):
    return {"date": D, "ymd": D.strftime("%Y%m%d"), "hm": hm,
            "open": price if opening is None else opening,
            "high": price, "low": price, "close": price, "volume": volume}


def _shared(rows, *, tail=True, audit=None):
    bars = pd.DataFrame(rows)
    bars.index = pd.to_datetime(bars["ymd"]) + pd.to_timedelta(bars["hm"], unit="m")
    daily = pd.DataFrame({"open": 10., "high": 10., "low": 10., "close": 10.},
                         index=pd.to_datetime(["20260828", "20260831", "20260901"]))
    return minute.simulate(
        {A: bars}, {A: daily}, {"20260901": [A]}, "20260901", "20260901",
        strategy="version8", total_cash=1_000_000, name_budget=28_000,
        buy_cost_rate=0, sell_cost_rate=0, min_cost=0, audit_sink=audit,
        **{**ON, "tail_window_buy": tail},
    )


def test_shared_grok_92_to_104_preserves_initial_peak_and_unarmed_clock():
    rows = [_bar(hm, 9.2 if hm < 890 else 10.4, opening=9.2) for hm in TAIL_MINUTES]
    state = _shared(rows)
    lot, = state.positions[A]
    assert lot.shares == 2800
    assert lot.cost == pytest.approx(9.542857142857143)
    assert lot.peak == 9.2
    assert lot.peak_hm == -1


def test_v7_grok_92_to_104_merges_trial_cost_without_raising_initial_peak():
    state = v7.SimResult(1_000_000)
    parent = TailParent.from_budget(28_000, 9.2)
    for hm in TAIL_MINUTES:
        row = _bar(hm, 9.2 if hm < 890 else 10.4, opening=9.2)
        v7._buy_tail_slice(state, parent, A, D, hm, row, "shares", FeeSchedule(0, 0, 0))
    position = state.positions[A]
    lot, = position.lots
    assert lot.shares == 2800
    assert position.avg_cost == lot.price == pytest.approx(9.542857142857143)
    assert position.entry_A == position.peak == 9.2


def test_v7_new_tail_position_does_not_observe_t0_high_as_peak():
    state = v7.simulate_v7(
        {A: [_bar(870, 9.2), _bar(871, 10.4), _bar(900, 10.4)]},
        {A: {D - timedelta(days=1): 10}}, {D: [A]}, [D], **ON,
    )
    assert state.positions[A].peak == state.positions[A].entry_A == 9.2


def test_shared_tail_fills_have_clock_without_adding_off_columns():
    rows = [_bar(hm) for hm in TAIL_MINUTES]
    state = _shared(rows, audit=(audit := []))
    fills = [trade for trade in state.trades if trade["side"] == "BUY"]
    assert [trade["hm"] for trade in fills] == list(TAIL_MINUTES)
    assert [trade["hm"] for trade in audit if trade["side"] == "BUY"] == list(TAIL_MINUTES)
    assert all("hm" not in trade for trade in _shared(rows, tail=False).trades)


def test_shared_tail_rejection_counts_cover_limit_zero_volume_and_absent_quote():
    rows = [_bar(hm, 11 if hm == 875 else 10, opening=10,
                 volume=0 if hm == 876 else 1_000_000)
            for hm in TAIL_MINUTES if hm != 900]
    state = _shared(rows, audit=(audit := []))
    assert state.stats["tail_skip_limit_up"] == 1
    assert state.stats["tail_skip_quote"] == 2
    expected = [hm for hm in TAIL_MINUTES if hm not in {875, 876, 900}]
    assert [trade["hm"] for trade in state.trades if trade["side"] == "BUY"] == expected
    assert [trade["hm"] for trade in audit if trade["side"] == "BUY"] == expected
    assert not any(key.startswith("tail_") for key in _shared(rows, tail=False).stats)


def test_v7_tail_rejections_are_countable_with_actual_child_clock():
    rows = [_bar(870, 11, opening=10), _bar(872, 9), _bar(873, volume=0)]
    state = v7.simulate_v7(
        {A: rows}, {A: {D - timedelta(days=1): 10}}, {D: [A]}, [D],
        audit_sink=(audit := []), **ON,
    )
    rejects = [trade for trade in state.trades if trade["side"] == "skip"]
    by_hm = {trade["hm"]: trade["reason"] for trade in rejects}
    assert by_hm == {hm: ("skip_limit_up" if hm == 870 else "skip_limit_down" if hm == 872
                         else "skip_tail_quote") for hm in TAIL_MINUTES}
    assert [trade["hm"] for trade in audit if trade["side"] == "skip"] == list(TAIL_MINUTES)
    off = v7.simulate_v7(
        {A: rows}, {A: {D - timedelta(days=1): 10}}, {D: [A]}, [D],
        **{**ON, "tail_window_buy": False},
    )
    assert not any(trade["reason"] in {"skip_tail_quote", "skip_limit_down"} for trade in off.trades)


@pytest.mark.parametrize("duplicate_hm", [870, 875, 900])
def test_v7_reader_duplicate_marker_rejects_only_on_child(duplicate_hm):
    rows = [{**_bar(hm), "_tail_duplicate": hm == duplicate_hm} for hm in TAIL_MINUTES]
    args = ({A: rows}, {A: {D - timedelta(days=1): 10}}, {D: [A]}, [D])
    state = v7.simulate_v7(*args, **ON)
    expected = [] if duplicate_hm == 870 else [hm for hm in TAIL_MINUTES if hm != duplicate_hm]
    assert [trade["hm"] for trade in state.trades if trade["side"] == "buy"] == expected
    reason = "skip_duplicate_tail_start" if duplicate_hm == 870 else "skip_duplicate_tail_bar"
    assert reason in [trade["reason"] for trade in state.trades]
    off = v7.simulate_v7(*args, **{**ON, "tail_window_buy": False})
    clean = [{key: value for key, value in row.items() if key != "_tail_duplicate"} for row in rows]
    baseline = v7.simulate_v7(
        {A: clean}, *args[1:], **{**ON, "tail_window_buy": False},
    )
    assert off == baseline
