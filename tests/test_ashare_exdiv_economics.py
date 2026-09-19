"""P3 δ6 C/A/B/B/A: explicit entitlements, integer shares, no inferred events."""

from dataclasses import asdict, replace
from decimal import Decimal, localcontext

import pandas as pd
import pytest

from backtest.research.ashare_exdiv_economics import ExDivEconomics, ExDivEvent
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.csv_ledger import (
    Position, SimState, _sell, apply_exdiv_economics, rescale_position,
)
from backtest.research.csv_simulate_loop import append_equity_and_eod_marks

CODE, EX, PAY = "600000.SH", "20260902", "20260903"
EVENT = ExDivEvent("dividend-1", Decimal("1"), Decimal("1"), EX, PAY)


def ledger(event=EVENT, quantities=(100,)):
    state = SimState(cash=2000, positions={CODE: [
        Position(CODE, q, 10, 0, 12, lot_id=i) for i, q in enumerate(quantities)
    ]})
    state.exdiv_economics = ExDivEconomics({(CODE, EX): event}, state.stats)
    return state


@pytest.mark.parametrize("bonus,cash,price", [(1, 0, 5), (0, 1, 9), (1, 1, 4.5)])
def test_ledger_b3_b4_b5_conserve_without_reference_share_inflate(bonus, cash, price):
    state = ledger(replace(EVENT, bonus_ratio=bonus, cash_div_per_share=cash))
    pos = state.positions[CODE][0]
    apply_exdiv_economics(state, CODE, EX)
    assert (pos.cost, pos.peak) == (10, 12)  # economics never changes refs
    rescale_position(pos, price / 10)
    day = pd.Timestamp(EX)
    bars = {CODE: pd.DataFrame({"close": [price]}, index=[day])}
    append_equity_and_eod_marks(state, ds=EX, day=day, calendar_last=day, mark_bars=bars)
    assert pos.shares == 100 * (1 + bonus)
    assert (pos.cost, pos.peak) == pytest.approx((price, 12 * price / 10))
    assert (state.cash, state.exdiv_economics.receivable_total) == (2000, 100 * cash)
    assert state.equity_curve == [(EX, 3000)]
    assert [(t["side"], t["commission"]) for t in state.trades] == [("EOD_MARK", 0)]


def test_integer_floor_per_lot_and_idempotent_snapshot():
    event = replace(EVENT, bonus_ratio=Decimal("0.29"), cash_div_per_share=Decimal("0.01"))
    state = ledger(event, (100, 103))
    with localcontext() as ctx:
        ctx.prec = 2  # floor cannot depend on decimal context rounding
        apply_exdiv_economics(state, CODE, EX)
    assert [p.shares for p in state.positions[CODE]] == [129, 132]
    assert state.exdiv_economics.receivable_total == 2.03  # eligible 203, not 261
    before = [asdict(p) for p in state.positions[CODE]]
    apply_exdiv_economics(state, CODE, EX)
    assert [asdict(p) for p in state.positions[CODE]] == before
    assert state.exdiv_economics.receivable_total == 2.03
    assert state.stats["exdiv_econ_duplicate_event"] == 1
    assert state.exdiv_economics.settle(PAY) == 2.03
    assert state.exdiv_economics.settle(PAY) == 0


@pytest.mark.parametrize("event", [
    {}, "garbage", replace(EVENT, event_id=""), replace(EVENT, event_id=1),
    replace(EVENT, bonus_ratio=-1), replace(EVENT, bonus_ratio=float("nan")),
    replace(EVENT, cash_div_per_share=Decimal("Infinity")),
    replace(EVENT, cash_div_per_share="1"), replace(EVENT, bonus_ratio=True),
    replace(EVENT, ex_date=PAY), replace(EVENT, ex_date="20260230"),
    replace(EVENT, pay_date="20260901"), replace(EVENT, pay_date="2026-09-03"),
    replace(EVENT, list_date="20260901"), replace(EVENT, list_date=""),
])
def test_invalid_event_is_diagnosed_without_partial_state(event):
    state = ledger(event)
    apply_exdiv_economics(state, CODE, EX)
    assert (state.positions[CODE][0].shares, state.cash) == (100, 2000)
    assert state.exdiv_economics.receivable_total == 0
    assert state.exdiv_economics.applied_ids == set()
    assert state.trades == []
    assert state.stats["exdiv_econ_invalid_event"] == 1


def test_missing_none_and_callable_lookup_and_no_k_inference():
    account = ExDivEconomics(lambda symbol, day: EVENT if (symbol, day) == (CODE, EX) else None)
    assert account.entitle(CODE, "20260901", [100]) is None
    assert account.stats == {}
    assert account.entitle(CODE, EX, [100]).bonus_shares == (100,)
    assert account.settle("20260904") == 100  # first session after a missing pay session
    assert account.settle("20260905") == 0
    state = ledger(None)
    apply_exdiv_economics(state, CODE, EX)
    rescale_position(state.positions[CODE][0], .5)
    assert (state.positions[CODE][0].shares, state.cash) == (100, 2000)
    assert not any(k.startswith("exdiv_econ") for k in state.stats)


def test_same_day_payment_and_duplicate_id_across_lookup_dates():
    same_day = replace(EVENT, pay_date=EX)
    state = ledger(same_day)
    apply_exdiv_economics(state, CODE, EX)
    assert state.cash == 2100 and state.exdiv_economics.receivable_total == 0
    state.exdiv_economics.lookup[(CODE, PAY)] = replace(same_day, ex_date=PAY, pay_date=PAY)
    apply_exdiv_economics(state, CODE, PAY)
    assert state.cash == 2100 and state.positions[CODE][0].shares == 200
    assert state.stats["exdiv_econ_cash_posted"] == 100


def test_malformed_lookup_is_diagnosed_but_callback_bugs_propagate():
    account = ExDivEconomics([])
    assert account.entitle(CODE, EX, [100]) is None
    assert account.stats["exdiv_econ_invalid_event"] == 1

    def broken(*_):
        raise AttributeError("caller bug")

    with pytest.raises(AttributeError, match="caller bug"):
        ExDivEconomics(broken).entitle(CODE, EX, [100])


@pytest.mark.parametrize("cap", [False, True])
def test_book_t1_listing_partial_exit_and_real_trade_fees(cap):
    state = ledger(replace(EVENT, list_date=PAY))
    if cap:
        state.volume_cap = VolumeCap(1, {
            (CODE, ds, 895): BucketVolume(100, 895, "raw_shares_incremental")
            for ds in (EX, PAY, "20260904")
        })
    pos = state.positions[CODE][0]
    apply_exdiv_economics(state, CODE, EX)
    assert state.cash == 2000 and state.trades == []
    if cap:
        assert state.volume_cap.used == {}  # entitlements are not fills
    _sell(state, CODE, pos, 4.5, pd.Timestamp(EX), "stop_loss:touch", bucket_id=895, day_i=1)
    assert pos.shares == 100  # sell only the pre-event shares
    assert state.cash == 2449.55
    _sell(state, CODE, pos, 4.5, pd.Timestamp(PAY), "stop_loss:touch", bucket_id=895, day_i=2)
    assert len(state.trades) == 1  # list day itself is also T+0
    state.cash += state.exdiv_economics.settle(PAY)
    _sell(state, CODE, pos, 4.5, pd.Timestamp("20260904"), "stop_loss:touch", bucket_id=895, day_i=3)
    assert not state.positions and not state.exdiv_economics.bonus_locks
    assert state.cash == pytest.approx(2999.1)
    assert [t["commission"] for t in state.trades] == [.45, .45]
    if cap:
        assert state.volume_cap.used == {(CODE, EX, 895): 100, (CODE, "20260904", 895): 100}


def test_book_linked_exit_waits_for_bonus_t1_without_orphaning_rider():
    state = ledger(quantities=(100, 100))
    parent, child = state.positions[CODE]
    child.ride_with = parent.lot_id
    apply_exdiv_economics(state, CODE, EX)
    _sell(state, CODE, parent, 4.5, pd.Timestamp(EX), "stop_loss:touch")
    assert state.trades == [] and [p.shares for p in state.positions[CODE]] == [200, 200]
    assert state.stats["exdiv_econ_defer_linked_t1"] == 1
    _sell(state, CODE, parent, 4.5, pd.Timestamp(PAY), "stop_loss:touch")
    assert not state.positions and len(state.trades) == 2
    assert state.exdiv_economics.receivable_total == 200  # surviving cash rights


def test_cap_pending_exit_stays_atomic_while_bonus_is_locked():
    state = ledger()
    state.volume_cap = VolumeCap(1, {
        (CODE, ds, 895): BucketVolume(q, 895, "raw_shares_incremental")
        for ds, q in ((EX, 1000), (PAY, 100), ("20260904", 200))
    })
    pos = state.positions[CODE][0]
    pos.pending_exit = "trail:pending"
    apply_exdiv_economics(state, CODE, EX)
    _sell(state, CODE, pos, 4.5, pd.Timestamp(EX), pos.pending_exit, bucket_id=895, day_i=1)
    assert not state.trades and state.volume_cap.used == {} and pos.shares == 200
    assert state.stats["exdiv_econ_defer_pending_t1"] == 1
    _sell(state, CODE, pos, 4.5, pd.Timestamp(PAY), pos.pending_exit, bucket_id=895, day_i=2)
    assert state.trades[-1]["reason"] == "skip_volume_cap:atomic_exit"
    assert pos.shares == 200 and state.volume_cap.used == {}
    _sell(state, CODE, pos, 4.5, pd.Timestamp("20260904"), pos.pending_exit, bucket_id=895, day_i=3)
    assert not state.positions and state.trades[-1]["shares"] == 200
    assert state.volume_cap.used == {(CODE, "20260904", 895): 200}
