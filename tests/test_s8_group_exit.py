"""Whole-position exits keep fill identity and the A-share T+1 share lock."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from backtest.research.ashare_volume_cap import BucketVolume
from backtest.research.csv_ledger import exit_positions
from backtest.research.csv_strategy_books import BOOKS as REGISTERED_BOOKS
from tests.test_s8_independent_positions import (
    CODE, LADDER_BOOKS, MODES, _buys, _ds, _no_exit, _pid, _run, _sells,
)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("strategy", (*LADDER_BOOKS, "version8_3"))
def test_weighted_cost_stop_exits_initial_and_added_shares_together(mode, strategy):
    prices = [10., 10.4, 9.3, 9.1] if strategy == "version8_3" else [10., 11., 12.1, 10., 9.8]
    st = _run(mode, strategy, prices, [0], take_profit=_no_exit)
    buys, sells = _buys(st), _sells(st)
    assert len(buys) == len(sells) == 2
    cost = sum(t["notional"] for t in buys) / sum(t["shares"] for t in buys)
    assert prices[-2] > cost * .9 > prices[-1] > buys[0]["price"] * .9
    assert {t["date"] for t in sells} == {_ds(len(prices) - 1)}
    assert all(t["reason"].startswith("stop_loss") for t in sells)
    assert {t["position_id"] for t in sells} == {_pid(0)}
    assert {t["lot"]: t["shares"] for t in sells} == {t["lot"]: t["shares"] for t in buys}
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", MODES)
def test_add_day_exit_sells_old_shares_then_new_shares_at_next_open(mode):
    # Before the 50% top-up, 10.22 is above the original 10 * 1.02 trail.
    # Afterwards it is below the weighted cost * 1.02 trail. Peak 11 happened
    # at 14:30, so neither minute clock can suppress the signal with gap15.
    st = _run(
        mode, "version8_3", [10., 10.22, 10.6], [0],
        rows=[(10.,) * 4, (10.22, 11., 10.22, 10.22), (10.5, 10.6, 10.5, 10.6)],
        minute_rows={
            1: [(570, 10.22, 10.22, 10.22, 10.22),
                (870, 10.5, 11., 10.5, 10.5),
                (895, 10.22, 10.22, 10.22, 10.22),
                (900, 10.22, 10.22, 10.22, 10.22)],
            2: [(570, 10.5, 10.6, 10.5, 10.6),
                (585, 10.6, 10.6, 10.6, 10.6),
                (895, 10.6, 10.6, 10.6, 10.6),
                (900, 10.6, 10.6, 10.6, 10.6)],
        },
    )
    initial, add = _buys(st)
    old_exit, deferred_exit = _sells(st)
    assert initial["shares"] == 50_000
    assert add["date"] == old_exit["date"] == _ds(1)
    assert old_exit["shares"] == initial["shares"]
    assert old_exit["price"] == 10.22
    assert old_exit["reason"] == "trail:band:2"
    assert deferred_exit["date"] == _ds(2)
    assert deferred_exit["shares"] == add["shares"]
    assert deferred_exit["price"] == 10.5  # first open, rather than its 10.6 close
    assert deferred_exit["reason"] == old_exit["reason"] + "|t1_deferred"
    assert {t["position_id"] for t in _sells(st)} == {_pid(0)}
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", ("minute_off", "minute_on"))
@pytest.mark.parametrize("strategy", LADDER_BOOKS)
def test_step_day_stop_keeps_new_shares_locked_until_next_open(mode, strategy):
    st = _run(
        mode, strategy, [10., 11., 9.8, 10.5], [0], take_profit=_no_exit,
        rows=[(10.,) * 4, (11.,) * 4, (11., 12.1, 9.8, 9.8), (10.2, 10.5, 10.2, 10.5)],
        minute_rows={
            2: [(570, 11., 11., 11., 11.), (585, 11., 11., 11., 11.),
                (895, 12.1, 12.1, 12.1, 12.1), (900, 9.8, 9.8, 9.8, 9.8)],
            3: [(570, 10.2, 10.5, 10.2, 10.5), (585, 10.5, 10.5, 10.5, 10.5),
                (895, 10.5, 10.5, 10.5, 10.5), (900, 10.5, 10.5, 10.5, 10.5)],
        },
    )
    initial, step = _buys(st)
    first_exit, deferred_exit = _sells(st)
    assert first_exit["date"] == step["date"] == _ds(2)
    assert first_exit["shares"] == initial["shares"]
    assert first_exit["price"] == 9.8
    assert first_exit["reason"].startswith("stop_loss")
    assert deferred_exit["date"] == _ds(3)
    assert deferred_exit["shares"] == step["shares"]
    assert deferred_exit["price"] == 10.2
    assert deferred_exit["reason"] == first_exit["reason"] + "|t1_deferred"
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", MODES)
def test_limit_down_defers_the_whole_position(mode):
    st = _run(mode, "version8", [10., 11., 12.1, 9.68, 9.5], [0], take_profit=_no_exit)
    buys, sells = _buys(st), _sells(st)
    assert len(buys) == len(sells) == 2
    assert {t["date"] for t in sells} == {_ds(4)}
    assert {t["lot"] for t in sells} == {0, 1}
    assert all(t["price"] == 9.5 for t in sells)
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", MODES)
def test_t1_deferred_shares_keep_the_exit_reason_through_a_limit_down_day(mode):
    st = _run(
        mode, "version8_3", [10., 10.22, 8.18, 9.1], [0],
        rows=[(10.,) * 4, (10.22, 11., 10.22, 10.22), (8.18,) * 4, (9., 9.1, 9., 9.1)],
        minute_rows={1: [(570, 10.22, 10.22, 10.22, 10.22),
                         (870, 10.5, 11., 10.5, 10.5),
                         (895, 10.22, 10.22, 10.22, 10.22),
                         (900, 10.22, 10.22, 10.22, 10.22)]},
    )
    old_exit, deferred_exit = _sells(st)
    assert old_exit["date"] == _ds(1)
    assert deferred_exit["date"] == _ds(3)
    assert deferred_exit["price"] == 9.
    assert deferred_exit["reason"] == "trail:band:2|t1_deferred"
    assert sum(t["shares"] for t in _sells(st)) == sum(t["shares"] for t in _buys(st))
    assert CODE not in st.positions


def test_daily_add_close_limit_down_retains_t1_marker_for_the_new_shares():
    # Limit-up sessions leave the top-up unfilled. At the following limit-down
    # close the top-up changes the weighted cost and forms a new exit signal.
    # The whole order waits, including the shares acquired at that same close.
    st = _run(
        "daily", "version8_3", [10., 12., 14.4, 11.52, 11.5], [0],
        take_profit=lambda _px, cost, _peak, _days: (
            "trail:test_weighted" if cost > 10. else None
        ),
    )
    initial, add = _buys(st)
    assert add["date"] == _ds(3)
    assert add["reason"] == "add:confirm3"
    sells = _sells(st)
    assert len(sells) == 2
    assert {t["date"] for t in sells} == {_ds(4)}
    assert {t["price"] for t in sells} == {11.5}
    assert {t["reason"] for t in sells} == {"trail:test_weighted|t1_deferred"}
    assert {t["lot"]: t["shares"] for t in sells} == {
        initial["lot"]: initial["shares"], add["lot"]: add["shares"],
    }
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", ("minute_off", "minute_on"))
def test_partial_volume_exit_finishes_on_the_next_completed_bucket_after_price_recovers(mode):
    volumes = {
        (CODE, _ds(0), 895): BucketVolume(100_000, 895, "raw_shares_incremental"),
        (CODE, _ds(1), 570): BucketVolume(60_000, 570, "raw_shares_incremental"),
        (CODE, _ds(1), 571): BucketVolume(40_000, 571, "raw_shares_incremental"),
    }
    st = _run(
        mode, "version8", [10., 9.5], [0], take_profit=_no_exit,
        participation_rate=1, volume_for_bucket=volumes,
        rows=[(10.,) * 4, (9., 9.5, 9., 9.5)],
        minute_rows={1: [(570, 9., 9., 9., 9.), (571, 8., 9.5, 8., 9.5),
                         (895, 9.5, 9.5, 9.5, 9.5), (900, 9.5, 9.5, 9.5, 9.5)]},
    )
    sells = _sells(st)
    assert [(t["shares"], t["price"]) for t in sells] == [(60_000, 9.), (40_000, 9.5)]
    assert {t["reason"] for t in sells} == {"stop_loss:gap_open"}
    assert "t1_deferred" not in sells[1]["reason"]
    assert st.volume_cap.used[(CODE, _ds(1), 571)] == 40_000
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("strategy", LADDER_BOOKS)
def test_price_add_preserves_peak_from_before_the_add_and_initial_entry_day(mode, strategy):
    st = _run(
        mode, strategy, [10., 11., 11.5, 12.1], [0], take_profit=_no_exit,
        rows=[(10.,) * 4, (11.,) * 4, (11.5, 13., 11.5, 11.5), (12.1,) * 4],
    )
    assert len(_buys(st)) == 2
    pos = exit_positions(st, CODE)[0]
    assert pos.peak == 13.
    assert pos.entry_idx == 0
    assert pos.group.first_lot.cost == 10.
    assert pos.cost > pos.group.first_lot.cost
    assert pos.cost < _buys(st)[1]["price"]


@pytest.mark.parametrize("mode", MODES)
def test_stale_uses_first_entry_day_after_a_late_topup(mode):
    prices = [10.] * 7 + [10.4] * 3
    rows = [(px,) * 4 for px in prices]
    rows[7] = (10.4, 10.5, 10.4, 10.4)
    st = _run(mode, "version8_3", prices, [0], rows=rows)
    assert [t["date"] for t in _buys(st)] == [_ds(0), _ds(7)]
    assert len(_sells(st)) == 2
    assert {t["date"] for t in _sells(st)} == {_ds(9 if mode == "daily" else 8)}
    assert {t["reason"] for t in _sells(st)} == {"force_sell:stale"}
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", MODES)
def test_weighted_stop_of_one_signal_group_preserves_the_other_group(mode):
    st = _run(mode, "version8", [10., 10.5, 12.1, 12.7, 10.2], [0, 1], take_profit=_no_exit)
    assert len(_buys(st)) == 4
    assert len(_sells(st)) == 2
    assert {t["position_id"] for t in _sells(st)} == {_pid(1)}
    assert {t["date"] for t in _sells(st)} == {_ds(4)}
    survivor = exit_positions(st, CODE)[0]
    assert survivor.position_id == _pid(0)
    assert survivor.entry_idx == 0
    assert survivor.peak == 12.7
    assert not survivor.pending_exit
    assert survivor.group.executed_steps == 1
    assert {p.lot_id for p in survivor.lots} == {0, 1}


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("strategy", ("version8_2", "version8_6"))
@pytest.mark.parametrize("prices", ([10., 9.7, 9.7], [10., 10.1, 10.05], [10., 10., 10.]))
def test_single_lot_books_match_the_legacy_exit_path(mode, strategy, prices, monkeypatch):
    corrected = _run(mode, strategy, prices, [0])
    # One code at the default quota buys precisely the same lot in both money
    # modes. Disabling per_name only selects the original per-lot exit branch.
    book = REGISTERED_BOOKS[strategy]
    monkeypatch.setitem(REGISTERED_BOOKS, strategy, replace(book, sizing="daily_quota"))
    legacy = _run(mode, strategy, prices, [0])
    identity = {"position_id", "entry_signal_date"}
    corrected_trades = [{k: v for k, v in t.items() if k not in identity} for t in corrected.trades]
    assert corrected_trades == legacy.trades
    assert corrected.cash == legacy.cash
    assert corrected.equity_curve == legacy.equity_curve


@pytest.mark.parametrize("mode", ("minute_off", "minute_on"))
@pytest.mark.parametrize("strategy", ("version8_2", "version8_6"))
@pytest.mark.parametrize("first_capacity", (0, 60_000))
def test_single_lot_books_keep_legacy_volume_attempt_and_peak(
    mode, strategy, first_capacity, monkeypatch,
):
    volumes = {
        (CODE, _ds(0), 895): BucketVolume(100_000, 895, "raw_shares_incremental"),
        (CODE, _ds(1), 570): BucketVolume(first_capacity, 570, "raw_shares_incremental"),
        (CODE, _ds(1), 571): BucketVolume(100_000, 571, "raw_shares_incremental"),
    }
    # Use the same explicit stop in both books to isolate their unchanged
    # single-lot completed-volume behavior after one rejected/partial attempt.
    options = {
        "stop_pct": .05, "take_profit": _no_exit,
        "participation_rate": 1, "volume_for_bucket": volumes,
        "rows": [(10.,) * 4, (10., 11.5, 9.3, 9.3)],
        "minute_rows": {1: [
            (570, 10., 11., 9.4, 9.4), (571, 10., 11.5, 9.3, 9.3),
            (895, 9.3, 9.3, 9.3, 9.3), (900, 9.3, 9.3, 9.3, 9.3),
        ]},
    }
    corrected = _run(mode, strategy, [10., 9.3], [0], **options)
    book = REGISTERED_BOOKS[strategy]
    monkeypatch.setitem(REGISTERED_BOOKS, strategy, replace(book, sizing="daily_quota"))
    legacy = _run(mode, strategy, [10., 9.3], [0], **options)
    identity = {"position_id", "entry_signal_date"}
    assert [{k: v for k, v in t.items() if k not in identity} for t in corrected.trades] == legacy.trades
    assert corrected.cash == legacy.cash
    assert corrected.equity_curve == legacy.equity_curve
    assert [
        {k: v for k, v in asdict(p).items() if k not in identity}
        for p in corrected.positions[CODE]
    ] == [asdict(p) for p in legacy.positions[CODE]]
    assert corrected.positions[CODE][0].shares == 100_000 - first_capacity
    assert corrected.positions[CODE][0].peak == 11.
    assert not corrected.positions[CODE][0].pending_exit
