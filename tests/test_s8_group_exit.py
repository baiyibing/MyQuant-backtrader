"""Whole-position exits keep fill identity and the A-share T+1 share lock."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from backtest.research import csv_ledger
from backtest.research.ashare_exdiv_economics import ExDivEvent
from backtest.research.ashare_volume_cap import BucketVolume
from backtest.research.csv_ledger import exit_positions
from backtest.research.csv_strategy_books import BOOKS as REGISTERED_BOOKS
from tests.test_s8_independent_positions import (
    CODE, LADDER_BOOKS, MODES, _buys, _ds, _no_exit, _pid, _run, _sells,
)


def _restore_previous_bonus_tracking(monkeypatch):
    """Reproduce the pre-fix marker rules, leaving all settlement code intact."""
    group_sell = csv_ledger._sell_s8_group

    def previous_bonus_marker(st, code, pos, px, day, reason, **kwargs):
        if st.exdiv_economics is not None:
            pos.group.t1_deferred_bonus_lots.update(
                p.lot_id for p in pos.lots
                if csv_ledger._locked_bonus(st.exdiv_economics, p, csv_ledger._ymd(day))
            )
        return group_sell(st, code, pos, px, day, reason, **kwargs)

    def previous_pending_exit(pos, value):
        if value and not pos.group.first_lot.pending_exit:
            pos.group.exit_day_idx = pos.day_i
        elif not value:
            pos.group.exit_day_idx = None
            pos.group.t1_deferred_bonus_lots.clear()
        pos.group.first_lot.pending_exit = value

    monkeypatch.setattr(csv_ledger, "_sell_s8_group", previous_bonus_marker)
    monkeypatch.setattr(
        csv_ledger.IndependentExitPosition, "pending_exit",
        csv_ledger.IndependentExitPosition.pending_exit.setter(previous_pending_exit),
    )


def _assert_only_reasons_can_differ(corrected, previous):
    def without_reason(st):
        return [{k: v for k, v in t.items() if k != "reason"} for t in st.trades]

    assert without_reason(corrected) == without_reason(previous)
    assert corrected.cash == previous.cash
    assert corrected.equity_curve == previous.equity_curve
    assert corrected.stats == previous.stats


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


@pytest.mark.parametrize("later_prices", ([11.5], [9.22, 9.3], [9.22, 7.38, 7.5]))
def test_daily_add_close_limit_down_marks_only_shares_locked_on_original_exit_day(later_prices):
    # Limit-up sessions leave the top-up unfilled. At the following limit-down
    # close the top-up changes the weighted cost and forms a new exit signal.
    # The whole order waits, including the shares acquired at that same close.
    reason = "trail:test_weighted"

    def take_profit(_px, cost, _peak, _days):
        return reason if cost > 10. else None

    initial_prices = [10., 12., 14.4, 11.52]
    pending = _run("daily", "version8_3", initial_prices, [0], take_profit=take_profit)
    assert not _sells(pending)
    assert exit_positions(pending, CODE)[0].pending_exit == reason

    st = _run("daily", "version8_3", initial_prices + later_prices, [0], take_profit=take_profit)
    initial, add = _buys(st)
    assert add["date"] == _ds(3)
    assert add["reason"] == "add:confirm3"
    sells = _sells(st)
    assert len(sells) == 2
    assert {t["date"] for t in sells} == {_ds(3 + len(later_prices))}
    assert {t["price"] for t in sells} == {later_prices[-1]}
    # Additional limit-down days do not change which lot was T+1 locked at
    # the original exit: old shares waited only because the price was blocked.
    assert {t["lot"]: t["reason"] for t in sells} == {
        initial["lot"]: reason, add["lot"]: reason + "|t1_deferred",
    }
    assert {t["lot"]: t["shares"] for t in sells} == {
        initial["lot"]: initial["shares"], add["lot"]: add["shares"],
    }
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("ex_day", (1, 2), ids=("original_exit_day", "during_defer"))
def test_bonus_t1_marker_uses_original_exit_day_without_changing_fills(mode, ex_day, monkeypatch):
    # On day 1 the original-exit case sells old shares and retains its bonus.
    # In the later-ex-date case the exit waits: daily schedules the next open,
    # while minute capacity prevents day-1 fills. Day 2's new bonus lock must
    # not turn a previously sellable lot into an original-day T+1 deferral.
    prices = [10., 4.5, 4.6] if ex_day == 1 else [10., 10., 5., 5.1]
    options = {
        "exdiv": {CODE: {_ds(ex_day): .5}},
        "exdiv_economics": {
            (CODE, _ds(ex_day)): ExDivEvent("bonus", 1, 0, _ds(ex_day), _ds(ex_day)),
        },
        "take_profit": _no_exit if ex_day == 1 else lambda *_: "trail:test_pending",
    }
    if mode != "daily" and ex_day == 2:
        volumes = {
            (CODE, _ds(i), hm): BucketVolume(
                0 if i == 1 else 100_000, hm, "raw_shares_incremental",
            )
            for i in range(len(prices)) for hm in (570, 585, 895, 900)
        }
        options.update(participation_rate=1, volume_for_bucket=volumes)
    corrected = _run(mode, "version8", prices, [0], **options)
    sells = _sells(corrected)
    assert [(t["date"], t["price"], t["shares"]) for t in sells] == [
        (_ds(ex_day), prices[ex_day], 100_000),
        (_ds(ex_day + 1), prices[ex_day + 1], 100_000),
    ]
    reason = "stop_loss:gap_open" if ex_day == 1 else "trail:test_pending"
    assert [t["reason"] for t in sells] == [
        reason, reason + ("|t1_deferred" if ex_day == 1 else ""),
    ]
    assert CODE not in corrected.positions

    _restore_previous_bonus_tracking(monkeypatch)
    previous = _run(mode, "version8", prices, [0], **options)
    _assert_only_reasons_can_differ(corrected, previous)
    if ex_day == 1:
        assert corrected.trades == previous.trades
    else:
        assert [t["reason"] for t in _sells(previous)] == [reason + "|t1_deferred"] * 2


@pytest.mark.parametrize("list_day", (1, 2), ids=("unlock_before_first_fill", "still_locked_at_first_fill"))
def test_daily_pending_only_exit_snapshots_original_bonus_lock(list_day, monkeypatch):
    # Daily profit-taking can latch an exit without calling _sell that day.
    # Capture the original lock even if it expires before the first attempt.
    reason = "trail:test_pending"
    options = {
        "take_profit": lambda *_: reason,
        "exdiv": {CODE: {_ds(1): .5}},
        "exdiv_economics": {
            (CODE, _ds(1)): ExDivEvent("bonus", 1, 0, _ds(1), _ds(1), _ds(list_day)),
        },
    }
    pending = _run("daily", "version8", [10., 5.], [0], **options)
    pos = exit_positions(pending, CODE)[0]
    assert not _sells(pending)
    assert pos.pending_exit == reason
    assert pos.group.exit_day_idx == 1
    assert pos.group.t1_deferred_bonus_lots == {0}

    prices = [10., 5., 5.1, 5.2]
    corrected = _run("daily", "version8", prices, [0], **options)
    sells = _sells(corrected)
    expected = ([(_ds(2), 5.1, 200_000)] if list_day == 1 else [
        (_ds(2), 5.1, 100_000), (_ds(3), 5.2, 100_000),
    ])
    assert [(t["date"], t["price"], t["shares"]) for t in sells] == expected
    assert {t["reason"] for t in sells} == {reason + "|t1_deferred"}
    assert CODE not in corrected.positions

    _restore_previous_bonus_tracking(monkeypatch)
    previous = _run("daily", "version8", prices, [0], **options)
    _assert_only_reasons_can_differ(corrected, previous)
    if list_day == 1:
        # The old implementation also missed an original-day lock once it had
        # expired; fixing that attribution changes only this reason suffix.
        assert [t["reason"] for t in _sells(previous)] == [reason]
    else:
        assert corrected.trades == previous.trades


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
