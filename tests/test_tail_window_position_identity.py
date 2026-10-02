"""Tail children retain their signal group and never merge price-add lots."""

from dataclasses import asdict, replace

import pandas as pd
import pytest

from backtest.research.csv_ledger import (
    IndependentPosition,
    InsufficientCashError,
    SimState,
    _sell,
    configure_s8,
    execute_buy,
    exit_positions,
)


CODE = "600000.SH"
BOOKS = ("version8", "version8_2", "version8_3", "version8_4", "version8_5", "version8_6")
DAYS = pd.to_datetime(["20260901", "20260902", "20260903"])
SIGNALS = [day.strftime("%Y%m%d") for day in DAYS]
PIDS = [f"{CODE}@{signal}" for signal in SIGNALS]


def _state(strategy="version8", cash=100_000., min_cost=5.):
    st = SimState(cash=cash, buy_cost_rate=0., sell_cost_rate=0., min_cost=min_cost)
    configure_s8(st, {"name": strategy, "sizing": "per_name", "name_budget": 28_000.})
    return st


def _child(st, px=10., shares=100, *, signal=0, day=0, merge_lot=None, **kwargs):
    return execute_buy(
        st, CODE, px, shares * px, day, DAYS[day],
        reason="pool:tail_window", shares_override=shares,
        position_id=PIDS[signal], entry_signal_date=SIGNALS[signal],
        merge_lot=merge_lot, hm=870 if merge_lot is None else 871, **kwargs,
    )


@pytest.mark.parametrize("strategy", ("version8", "version8_4", "version8_5"))
def test_children_keep_initial_group_anchor_and_add_lot_sequence(strategy):
    st = _state(strategy)
    assert _child(st, 9.2)
    first, = st.positions[CODE]
    group = st.book_state["s8_independent"]["groups"][PIDS[0]]
    assert isinstance(first, IndependentPosition)
    assert _child(st, 10.4, merge_lot=first)
    assert group.first_lot is first
    assert group.next_lot_id == 1
    assert first.cost == pytest.approx(9.8)
    assert first.peak == 9.2 and first.peak_hm == -1

    # A real price add is a separate lot. Subsequent initial-order children
    # still merge into lot 0, even though that is no longer the last list item.
    assert execute_buy(
        st, CODE, 10.5, 1_050., 0, DAYS[0], reason="add:step20",
        shares_override=100, position_id=PIDS[0], entry_signal_date=SIGNALS[0],
    )
    add = st.positions[CODE][-1]
    group.executed_steps, group.last_add_date = 1, SIGNALS[0]
    assert _child(st, 10.1, 200, merge_lot=first)

    assert st.positions[CODE] == [first, add]
    assert group.first_lot is first
    assert group.next_lot_id == 2
    assert group.executed_steps == 1 and group.last_add_date == SIGNALS[0]
    assert (first.shares, first.lot_id, first.entry_idx) == (400, 0, 0)
    assert first.cost == pytest.approx(9.95)
    assert first.peak == 9.2 and first.peak_hm == -1
    assert (add.shares, add.cost, add.lot_id) == (100, 10.5, 1)
    view, = exit_positions(st, CODE)
    assert view.cost == pytest.approx(10.06)
    assert view.peak == 9.2
    assert [trade["lot"] for trade in st.trades] == [0, 0, 1, 0]
    assert {trade["position_id"] for trade in st.trades} == {PIDS[0]}
    assert {trade["entry_signal_date"] for trade in st.trades} == {SIGNALS[0]}
    assert st.stats["buys"] == 4 and st.stats["add_lots"] == 1
    assert st.stats["invested_notional"] == pytest.approx(5_030.)
    assert st.cash == pytest.approx(94_950.)  # Four independently charged fees.


@pytest.mark.parametrize("strategy", BOOKS)
def test_same_code_signals_first_filled_on_same_day_keep_separate_initial_lots(strategy):
    st = _state(strategy)
    assert _child(st, 10., signal=0, day=1)
    first = st.positions[CODE][-1]
    assert _child(st, 9., signal=1, day=1)
    second = st.positions[CODE][-1]
    assert _child(st, 10.4, signal=0, day=1, merge_lot=first)
    assert _child(st, 9.4, signal=1, day=1, merge_lot=second)
    assert len(st.positions[CODE]) == 2
    assert (first.shares, second.shares) == (200, 200)
    assert (first.lot_id, second.lot_id) == (0, 0)
    assert first.cost == pytest.approx(10.2)
    assert second.cost == pytest.approx(9.2)
    assert [trade["position_id"] for trade in st.trades] == [PIDS[0], PIDS[1]] * 2
    assert st.stats["add_lots"] == 0


@pytest.mark.parametrize("mismatch", [
    "position_id", "entry_signal_date", "price_add", "detached", "entry_day", "code",
])
def test_invalid_merge_identity_is_rejected_before_any_cash_or_state_mutation(mismatch):
    st = _state()
    assert _child(st, signal=0, day=1)
    first = st.positions[CODE][-1]
    assert _child(st, signal=1, day=1)
    assert execute_buy(
        st, CODE, 10., 1_000., 1, DAYS[1], reason="add:step20", shares_override=100,
        position_id=PIDS[0], entry_signal_date=SIGNALS[0],
    )
    arguments = {
        "code": CODE, "px": 10., "per": 1_000., "entry_idx": 1, "day": DAYS[1],
        "reason": "pool:tail_window", "shares_override": 100, "merge_lot": first,
        "position_id": PIDS[0], "entry_signal_date": SIGNALS[0],
    }
    if mismatch == "position_id":
        arguments["position_id"] = PIDS[1]
    elif mismatch == "entry_signal_date":
        arguments["entry_signal_date"] = SIGNALS[1]
    elif mismatch == "price_add":
        arguments["merge_lot"] = st.positions[CODE][-1]
    elif mismatch == "detached":
        arguments["merge_lot"] = replace(first)
    elif mismatch == "entry_day":
        arguments.update(entry_idx=2, day=DAYS[2])
    else:
        arguments["code"] = "600001.SH"
    before = asdict(st)
    with pytest.raises(ValueError, match="merge_lot"):
        execute_buy(st, **arguments)
    assert asdict(st) == before


@pytest.mark.parametrize("first_reason", ["pool", "chase", "pool:tail_window"])
def test_tail_parent_cannot_repeat_an_existing_signal_without_its_merge_lot(first_reason):
    st = _state()
    assert execute_buy(
        st, CODE, 10., 1_000., 0, DAYS[0], reason=first_reason, shares_override=100,
        position_id=PIDS[0], entry_signal_date=SIGNALS[0],
    )
    before = asdict(st)
    assert not _child(st)
    assert asdict(st) == before


@pytest.mark.parametrize("strategy", BOOKS)
def test_child_commission_shortfall_raises_with_identity_and_lot_unchanged(strategy):
    st = _state(strategy, cash=2_005.)
    assert _child(st)
    first, = st.positions[CODE]
    before = asdict(st)
    with pytest.raises(InsufficientCashError) as caught:
        _child(st, merge_lot=first)
    error = caught.value
    assert (error.date, error.code) == (SIGNALS[0], CODE)
    assert (error.needed, error.available, error.shortfall) == (1_005., 1_000., 5.)
    assert asdict(st) == before


def test_merged_children_obey_t1_and_other_signal_exits_do_not_close_their_group():
    st = _state(min_cost=0.)
    assert _child(st)
    old = st.positions[CODE][-1]
    assert _child(st, merge_lot=old)
    assert _child(st, signal=1, day=1)
    new = st.positions[CODE][-1]
    assert _child(st, signal=1, day=1, merge_lot=new)
    old_view, new_view = exit_positions(st, CODE, day_i=1)
    assert _sell(st, CODE, old_view, 10., DAYS[1], "stop_loss:test", day_i=1) == 200
    assert old_view.group.closed
    assert st.positions[CODE] == [new]
    assert not new_view.group.closed
    assert _sell(st, CODE, new_view, 10., DAYS[1], "stop_loss:test", day_i=1) == 0
    assert new.shares == 200
    assert new.pending_exit == "stop_loss:test"
    assert _sell(st, CODE, new_view, 10., DAYS[2], new.pending_exit, day_i=2) == 200
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert [(trade["position_id"], trade["shares"]) for trade in sells] == [
        (PIDS[0], 200), (PIDS[1], 200),
    ]
    assert [trade["reason"] for trade in sells] == [
        "stop_loss:test", "stop_loss:test|t1_deferred",
    ]
    assert CODE not in st.positions
