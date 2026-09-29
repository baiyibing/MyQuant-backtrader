"""Independent constants from S0 A-E; explicit commands, no broker or lake."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import ROUND_05UP, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, Inexact, localcontext

import pytest
from backtest.research.minute_orders_backend import (
    BucketQuote,
    CandidateMatch,
    FeeContractError,
    FeeModel,
    FeeModelParams,
    FillProposal,
    Ledger,
    LedgerError,
    LimitOrderMatchInput,
    LotPosition,
    Reservation,
    ReservationRejected,
    ResourceRejectReason,
    Side,
    match_candidates,
)

D = Decimal
D0 = date(2026, 9, 28)
D1 = date(2026, 9, 29)
ZERO = D("0.00")


def model(rate="0", minimum="0", *, sell_rate=None, sell_minimum=None):
    return FeeModel(
        FeeModelParams(D(rate), D(minimum), ROUND_HALF_UP),
        FeeModelParams(
            D(sell_rate if sell_rate is not None else rate),
            D(sell_minimum if sell_minimum is not None else minimum),
            ROUND_HALF_UP,
        ),
    )


def ledger(cash="10000", lots=(), fees=None):
    return Ledger(D(cash), list(lots), fee_model=model() if fees is None else fees)


def initial_lot(qty=200, *, lot_id="initial", symbol="X", acquired=date(2026, 9, 25), sellable=D0):
    return LotPosition(lot_id, symbol, acquired, sellable, qty, 100)


def buy(book, order="O1", qty=300, *, limit="10", fee="0", symbol="X"):
    return book.reserve_buy(
        order, symbol=symbol, limit=D(limit), remaining_qty=qty, lot_size=100, fee_upper=D(fee)
    )


def sell(book, order="S1", qty=100, *, day=D0, limit="10", symbol="X"):
    return book.reserve_sell(
        order, symbol=symbol, limit=D(limit), qty=qty, lot_size=100, trade_date=day
    )


def bucket(book, name="b1", cap=200, *, day=D0, symbol="X"):
    return book.register_bucket(
        symbol=symbol, bucket_id=name, trade_date=day, lot_size=100, capacity=cap
    )


def proposal(
    book,
    fill="f1",
    order="O1",
    qty=100,
    *,
    side=Side.BUY,
    price="10",
    fee="0",
    name="b1",
    day=D0,
    unlock=D1,
    symbol="X",
):
    return FillProposal(
        fill,
        order,
        symbol,
        side,
        qty,
        D(price),
        D(fee),
        name,
        qty,
        100,
        day,
        unlock if side is Side.BUY else None,
        book.snapshot().ledger_version,
    )


def cash_path(book, cash, reserved, free):
    state = book.snapshot()
    assert (state.cash, state.reserved_cash, state.free_cash) == (D(cash), D(reserved), D(free))


def test_sketch_a_two_buys_partial_shared_capacity_and_expiry_release():
    book = ledger()
    assert isinstance(buy(book), Reservation)
    assert isinstance(buy(book, "O2", 200), Reservation)
    cash_path(book, "10000", "5000", "5000")
    bucket(book)
    book.apply_fill(proposal(book, qty=200))
    cash_path(book, "8000", "3000", "5000")
    before = book.snapshot()
    with pytest.raises(LedgerError, match="capacity"):
        book.apply_fill(proposal(book, "over", "O2"))
    assert book.snapshot() == before
    bucket(book, "b2")
    book.apply_fill(proposal(book, "f2", name="b2"))
    book.apply_fill(proposal(book, "f3", "O2", name="b2"))
    cash_path(book, "6000", "1000", "5000")
    assert [b.remaining for b in book.snapshot().buckets] == [0, 0]
    assert sum(l.qty for l in book.snapshot().lots) == 400
    assert all(l.acquire_date == D0 and l.sellable_date == D1 for l in book.snapshot().lots)
    # Caller drives the 09:33 expiry phase before offering any further fill.
    bucket(book, "b3")
    book.release_buy("O2")
    cash_path(book, "6000", "0", "6000")
    before = book.snapshot()
    with pytest.raises(LedgerError, match="no active reservation"):
        book.apply_fill(proposal(book, "late", "O2", name="b3"))
    assert book.snapshot() == before
    assert len(before.applied_fills) == 3
    assert before.fees_paid == ZERO


@pytest.mark.parametrize("phase", ["expiry", "cancel", "expiry_then_cancel"])
def test_sketch_b_caller_releases_before_match_at_right_open_boundary(phase):
    book = ledger("2000", fees=model("0.001", "5"))
    buy(book, qty=100, fee="5")
    bucket(book)
    book.release_buy("O1")
    before = book.snapshot()
    if phase == "expiry_then_cancel":
        with pytest.raises(LedgerError):
            book.release_buy("O1")  # no second release or fee refund
    with pytest.raises(LedgerError):
        book.apply_fill(proposal(book, fee="5"))
    assert book.snapshot() == before
    cash_path(book, "2000", "0", "2000")
    assert before.applied_fill_ids == frozenset()
    assert before.fees_paid == ZERO
    assert before.buckets[0].remaining == 200


def test_sketch_c_t_plus_one_double_reserve_reject_and_d1_sale():
    book = ledger("5000")
    buy(book, qty=200)
    bucket(book)
    book.apply_fill(proposal(book, qty=200))
    rejected = sell(book, "S0")
    assert rejected == ReservationRejected("S0", ResourceRejectReason.INSUFFICIENT_SELLABLE, 100, 0)
    assert isinstance(sell(book, qty=200, day=D1), Reservation)
    assert book.snapshot().reserved_sellable_qty("X") == 200
    assert book.snapshot().lots[0].free_qty == 0
    assert isinstance(sell(book, "S2", day=D1), ReservationRejected)
    bucket(book, "d1", day=D1)
    book.apply_fill(proposal(book, "s1", "S1", 200, side=Side.SELL, name="d1", day=D1))
    cash_path(book, "5000", "0", "5000")
    assert book.snapshot().lots == ()
    assert book.snapshot().reserved_sellable_qty("X") == 0


def test_explicit_friday_to_monday_unlock_no_natural_day_calendar():
    friday, saturday, monday = date(2026, 9, 25), date(2026, 9, 26), D0
    book = ledger()
    buy(book, qty=100)
    bucket(book, day=friday)
    book.apply_fill(proposal(book, day=friday, unlock=monday))
    assert isinstance(sell(book, "sat", day=saturday), ReservationRejected)
    assert isinstance(sell(book, "mon", day=monday), Reservation)
    bucket(book, "sat-bucket", day=saturday)
    before = book.snapshot()
    with pytest.raises(LedgerError, match="sellable"):
        book.apply_fill(
            proposal(book, "early", "mon", side=Side.SELL, name="sat-bucket", day=saturday)
        )
    assert book.snapshot() == before


def test_sketch_d_rejected_buy_never_revives_after_sell_posts_cash():
    book = ledger("0", [initial_lot()])
    assert buy(book, "rejected", 100) == ReservationRejected(
        "rejected", ResourceRejectReason.INSUFFICIENT_CASH, D("1000"), ZERO
    )
    sell(book)
    bucket(book)
    book.apply_fill(proposal(book, "sold", "S1", side=Side.SELL))
    cash_path(book, "1000", "0", "1000")
    before = book.snapshot()
    with pytest.raises(LedgerError, match="no active reservation"):
        book.apply_fill(proposal(book, "revive", "rejected"))
    with pytest.raises(LedgerError, match="already used"):
        buy(book, "rejected", 100)
    assert book.snapshot() == before
    assert isinstance(buy(book, "new-submit", 100), Reservation)
    cash_path(book, "1000", "1000", "0")
    assert len(book.snapshot().applied_fills) == 1
    # This slice has no submit clock. Caller must defer matching this new order.


def test_sketch_d_sell_then_buy_share_one_bilateral_capacity():
    book = ledger("2000", [initial_lot(100)])
    buy(book, qty=200)
    sell(book)
    bucket(book)
    book.apply_fill(proposal(book, "sold", "S1", side=Side.SELL))
    book.apply_fill(proposal(book, "bought"))
    cash_path(book, "2000", "1000", "1000")
    before = book.snapshot()
    with pytest.raises(LedgerError, match="capacity"):
        book.apply_fill(proposal(book, "over"))
    assert book.snapshot() == before
    assert before.buckets[0].remaining == 0
    assert sum(l.qty for l in before.lots) == 100


def test_sketch_e_cumulative_min_fee_and_cancel_remainder():
    fees = model("0.001", "5.00")
    book = ledger(fees=fees)
    assert fees.buy_fee_upper_bound(ZERO, D("10"), 400) == D("5")
    buy(book, qty=400, fee="5")
    cash_path(book, "10000", "4005", "5995")
    bucket(book)
    book.apply_fill(proposal(book, qty=200, fee="5"))
    cash_path(book, "7995", "2000", "5995")
    bucket(book, "b2", 100)
    book.apply_fill(proposal(book, "f2", name="b2"))
    cash_path(book, "6995", "1000", "5995")
    assert fees.fee_delta(Side.BUY, D("3000"), D("3000")) == ZERO
    assert fees.buy_fee_upper_bound(D("3000"), D("10"), 0) == ZERO
    book.release_buy("O1")
    cash_path(book, "6995", "0", "6995")
    assert book.snapshot().fees_paid == D("5")
    assert book.snapshot().order_totals[0].notional == D("3000")
    assert book.snapshot().order_totals[0].fees_paid == D("5")
    low = ledger("4004", fees=fees)
    assert buy(low, qty=400, fee="5") == ReservationRejected(
        "O1", ResourceRejectReason.INSUFFICIENT_CASH, D("4005"), D("4004")
    )
    cash_path(low, "4004", "0", "4004")
    assert low.snapshot().reservations == ()


def test_rounding_is_cumulative_not_per_partial_and_side_params_are_explicit():
    fees = model("0.001", "0", sell_rate="0.002", sell_minimum="5")
    assert fees.cumulative_fee(Side.BUY, ZERO) == ZERO
    assert fees.cumulative_fee(Side.SELL, ZERO) == ZERO
    assert fees.cumulative_fee(Side.BUY, D("1005")) == D("1.01")
    assert fees.fee_delta(Side.BUY, D("1005"), D("2010")) == D("1.00")
    assert fees.cumulative_fee(Side.SELL, D("2010")) == D("5.00")
    even = FeeModel(FeeModelParams(D("0.001"), ZERO, ROUND_HALF_EVEN), fees.sell)
    assert even.cumulative_fee(Side.BUY, D("1005")) == D("1.00")
    book = ledger(fees=fees)
    buy(book, qty=200, limit="10.05", fee="2.01")
    bucket(book)
    book.apply_fill(proposal(book, price="10.05", fee="1.01"))
    cash_path(book, "8993.99", "1006.00", "7987.99")
    book.apply_fill(proposal(book, "f2", price="10.05", fee="1.00"))
    cash_path(book, "7987.99", "0", "7987.99")
    assert book.snapshot().fees_paid == D("2.01")


def test_price_improvement_recomputes_upper_and_releases_excess():
    fees = model("0.001", "5")
    book = ledger(fees=fees)
    buy(book, qty=600, fee="6")
    cash_path(book, "10000", "6006", "3994")
    bucket(book)
    book.apply_fill(proposal(book, qty=200, price="9", fee="5"))
    # N=1800; max future N=5800: remaining fee 5.80-5.00=.80.
    cash_path(book, "8195", "4000.80", "4194.20")
    assert book.snapshot().reservations[0].fee_upper == D("0.80")


def test_sell_cumulative_fees_net_proceeds_and_partial_release():
    book = ledger("0", [initial_lot(300)], model("0", "0", sell_rate="0.001", sell_minimum="5"))
    sell(book, qty=300)
    bucket(book)
    book.apply_fill(proposal(book, "s1", "S1", side=Side.SELL, fee="5"))
    cash_path(book, "995", "0", "995")
    book.apply_fill(proposal(book, "s2", "S1", side=Side.SELL))
    cash_path(book, "1995", "0", "1995")
    assert book.snapshot().lots[0].reserved_qty == 100
    book.release_sell("S1")
    assert book.snapshot().lots[0].free_qty == 100
    assert book.snapshot().fees_paid == D("5")


def test_multiple_sell_reservations_own_specific_lots_and_release_only_their_claim():
    book = ledger("0", [initial_lot(200, lot_id="b"), initial_lot(100, lot_id="a")])
    sell(book, "S1", 200)
    sell(book, "S2", 100)
    assert [(a.lot_id, a.qty) for a in book.snapshot().reservations[0].lots] == [
        ("a", 100),
        ("b", 100),
    ]
    bucket(book, cap=300)
    book.apply_fill(proposal(book, "s2", "S2", side=Side.SELL))
    assert sum(l.qty for l in book.snapshot().lots) == 200
    assert book.snapshot().reserved_sellable_qty("X") == 200
    book.apply_fill(proposal(book, "s1", "S1", side=Side.SELL))
    book.release_sell("S1")
    assert [(l.lot_id, l.qty, l.free_qty) for l in book.snapshot().lots] == [("b", 100, 100)]


def test_fill_replay_after_release_and_other_activity_is_noop_conflict_fails():
    book = ledger()
    buy(book)
    bucket(book)
    p = proposal(book)
    applied = book.apply_fill(p)
    book.release_buy("O1")
    buy(book, "other", 100)
    before = book.snapshot()
    assert book.apply_fill(p) == replace(applied, duplicate=True)
    assert book.snapshot() is before
    for changed in (
        replace(p, price=D("9")),
        replace(p, order_id="other"),
        replace(p, expected_version=before.ledger_version),
    ):
        with pytest.raises(LedgerError, match="fill_id conflict"):
            book.apply_fill(changed)
        assert book.snapshot() is before


def test_stale_proposal_rejected_and_no_partial_commit():
    book = ledger()
    buy(book)
    bucket(book)
    p = proposal(book)
    buy(book, "O2", 100)
    before = book.snapshot()
    with pytest.raises(LedgerError, match="stale"):
        book.apply_fill(p)
    assert book.snapshot() is before


def test_failure_during_snapshot_preparation_is_atomic(monkeypatch):
    import backtest.research.minute_orders_backend.ledger as ledger_module

    book = ledger()
    buy(book)
    bucket(book)
    p = proposal(book)
    before = book.snapshot()
    original_replace = ledger_module.replace

    def injected_replace(obj, **changes):
        if isinstance(obj, type(before)) and "free_cash" in changes:
            raise ArithmeticError("injected after all economic calculations")
        return original_replace(obj, **changes)

    with monkeypatch.context() as patch:
        patch.setattr(ledger_module, "replace", injected_replace)
        with pytest.raises(ArithmeticError, match="injected"):
            book.apply_fill(p)
    assert book.snapshot() is before
    book.apply_fill(p)
    cash_path(book, "9000", "2000", "7000")


def test_bucket_identity_no_reset_symbol_isolation_and_no_carry_forward():
    book = ledger()
    buy(book)
    buy(book, "Y1", 100, symbol="Y")
    bucket(book)
    bucket(book, symbol="Y")
    book.apply_fill(proposal(book))
    before = book.snapshot()
    assert bucket(book).remaining == 100
    assert book.snapshot() is before
    with pytest.raises(LedgerError, match="conflicting"):
        bucket(book, cap=300)
    assert book.snapshot() is before
    bucket(book, "b2", 0)
    with pytest.raises(LedgerError, match="capacity"):
        book.apply_fill(proposal(book, "empty", name="b2"))
    book.apply_fill(proposal(book, "y-fill", "Y1", symbol="Y"))
    assert [(b.symbol, b.bucket_id, b.remaining) for b in book.snapshot().buckets] == [
        ("X", "b1", 100),
        ("Y", "b1", 100),
        ("X", "b2", 0),
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"qty": 0},
        {"qty": -100},
        {"qty": True},
        {"qty": 101},
        {"qty": 400},
        {"lot_size": 0},
        {"lot_size": 50},
        {"capacity_consumed": 0},
        {"capacity_consumed": 200},
        {"price": D("10.001")},
        {"price": D("0")},
        {"price": D("NaN")},
        {"price": D("Infinity")},
        {"price": 10.0},
        {"price": D("10.01")},
        {"fee_delta": D("-1")},
        {"fee_delta": D("1")},
        {"fee_delta": D("0.001")},
        {"trade_date": D1},
        {"trade_date": "2026-09-28"},
        {"sellable_date": D0},
        {"sellable_date": None},
        {"expected_version": True},
        {"side": "BUY"},
        {"fill_id": " "},
        {"order_id": "missing"},
        {"symbol": "Y"},
        {"bucket_id": "missing"},
    ],
)
def test_bad_fill_fails_closed_without_mutation(change):
    book = ledger()
    buy(book)
    bucket(book)
    before = book.snapshot()
    with pytest.raises(LedgerError):
        book.apply_fill(replace(proposal(book), **change))
    assert book.snapshot() is before


def test_sell_fee_cannot_spend_other_buy_reservation_or_overdraw_cash():
    for cash, reserve_other in (("0", False), ("1000", True)):
        book = ledger(cash, [initial_lot(100)], model("0", "0", sell_minimum="1001"))
        if reserve_other:
            buy(book, "other", 100)
        sell(book)
        bucket(book)
        before = book.snapshot()
        with pytest.raises(LedgerError):
            book.apply_fill(proposal(book, order="S1", side=Side.SELL, fee="1001"))
        assert book.snapshot() is before


@pytest.mark.parametrize(
    "params",
    [
        FeeModelParams(D("-0.1"), ZERO, ROUND_HALF_UP),
        FeeModelParams(0.001, ZERO, ROUND_HALF_UP),
        FeeModelParams(D("NaN"), ZERO, ROUND_HALF_UP),
        FeeModelParams(D("Infinity"), ZERO, ROUND_HALF_UP),
        FeeModelParams(ZERO, D("-1"), ROUND_HALF_UP),
        FeeModelParams(ZERO, D("1.001"), ROUND_HALF_UP),
        FeeModelParams(ZERO, ZERO, ROUND_05UP),
        FeeModelParams(ZERO, ZERO, None),
    ],
)
def test_invalid_or_unsupported_fee_model_fails_closed(params):
    with pytest.raises(FeeContractError):
        FeeModel(params, FeeModelParams(ZERO, ZERO, ROUND_HALF_UP))


def test_fee_inputs_bounds_and_no_arbitrary_model():
    fees = model("0.001", "5")
    with pytest.raises(FeeContractError):
        fees.fee_delta(Side.BUY, D("1"), ZERO)
    with pytest.raises(FeeContractError):
        fees.cumulative_fee("BUY", D("1"))
    with pytest.raises(FeeContractError):
        fees.cumulative_fee(Side.BUY, D("1.001"))
    for qty in (-1, True, 1.1):
        with pytest.raises(FeeContractError):
            fees.buy_fee_upper_bound(ZERO, D("10"), qty)
    with pytest.raises(LedgerError):
        Ledger(D("10000"), [], fee_model=object())
    book = ledger(fees=fees)
    before = book.snapshot()
    for bound in ("0", "4.99", "5.01"):
        with pytest.raises(LedgerError, match="fee_upper"):
            buy(book, fee=bound)
    assert book.snapshot() is before


def test_reservations_cannot_double_reserve_or_reopen_released_ids():
    book = ledger("4000", [initial_lot(200)])
    buy(book)
    sell(book)
    before = book.snapshot()
    for action in (
        lambda: buy(book),
        lambda: sell(book),
        lambda: book.release_sell("O1"),
        lambda: book.release_buy("S1"),
    ):
        with pytest.raises(LedgerError):
            action()
        assert book.snapshot() is before
    assert isinstance(buy(book, "too-much", 200), ReservationRejected)
    cash_path(book, "4000", "3000", "1000")
    book.release_buy("O1")
    book.release_sell("S1")
    before = book.snapshot()
    for action in (lambda: buy(book), lambda: sell(book), lambda: book.release_sell("S1")):
        with pytest.raises(LedgerError):
            action()
        assert book.snapshot() is before


@pytest.mark.parametrize(
    "change",
    [
        {"qty": 0},
        {"qty": 99},
        {"qty": True},
        {"reserved_qty": 100},
        {"acquire_date": D0},
        {"sellable_date": date(2026, 9, 24)},
        {"acquire_date": datetime.fromisoformat("2026-09-25T00:00:00+08:00")},
        {"symbol": ""},
        {"lot_size": 0},
    ],
)
def test_bad_initial_lots_rejected(change):
    with pytest.raises(LedgerError):
        ledger(lots=[replace(initial_lot(), **change)])


def test_initial_state_requires_explicit_lot_list_and_nonnegative_cent_cash():
    with pytest.raises(LedgerError, match="initial_lots"):
        Ledger(D("1000"), None, fee_model=model())
    for cash in (D("-1"), D("NaN"), D("Infinity"), D("0.001"), 1000.0):
        with pytest.raises(LedgerError):
            Ledger(cash, [], fee_model=model())


def test_initial_lot_ids_lot_sizes_and_buy_lot_collision():
    with pytest.raises(LedgerError, match="duplicate"):
        ledger(lots=[initial_lot(), initial_lot()])
    with pytest.raises(LedgerError, match="lot_size"):
        ledger(lots=[initial_lot(), replace(initial_lot(lot_id="second"), lot_size=50)])
    book = ledger(lots=[initial_lot(lot_id="fill:f1")])
    buy(book)
    bucket(book)
    before = book.snapshot()
    with pytest.raises(LedgerError, match="lot_id conflicts"):
        book.apply_fill(proposal(book))
    assert book.snapshot() is before


def test_snapshot_and_input_lots_are_immutable_and_detached():
    lots = [initial_lot()]
    book = Ledger(D("5000"), lots, fee_model=model())
    old = book.snapshot()
    lots.clear()
    buy(book, qty=100)
    assert len(old.lots) == 1 and old.reservations == ()
    with pytest.raises(FrozenInstanceError):
        old.cash = ZERO
    with pytest.raises(FrozenInstanceError):
        old.lots[0].qty = 0
    assert isinstance(old.used_order_ids, frozenset)
    assert isinstance(book.snapshot().reservations, tuple)


def test_low_decimal_precision_and_inexact_trap_cannot_round_accounting():
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        fees = model("0.001", "0")
        assert fees.cumulative_fee(Side.BUY, D("1005")) == D("1.01")
        assert fees.buy_fee_upper_bound(D("1005"), D("10.05"), 100) == D("1.00")
        book = ledger("100000.01", fees=fees)
        buy(book, qty=200, limit="10.05", fee="2.01")
        bucket(book)
        book.apply_fill(proposal(book, qty=200, price="10.05", fee="2.01"))
        cash_path(book, "97988.00", "0", "97988.00")


def test_match_action_does_not_apply_until_caller_builds_explicit_proposal():
    book = ledger()
    buy(book)
    bucket(book)
    before = book.snapshot()
    action = match_candidates(
        LimitOrderMatchInput("O1", "X", Side.BUY, D("10"), 300, 100),
        BucketQuote(
            "X",
            "b1",
            datetime.fromisoformat("2026-09-28T09:30:00+08:00"),
            datetime.fromisoformat("2026-09-28T09:31:00+08:00"),
            D("10"),
        ),
        capacity_remaining=200,
    )
    assert isinstance(action, CandidateMatch)
    assert book.snapshot() is before
    with pytest.raises(LedgerError, match="explicit FillProposal"):
        book.apply_fill(action)
    book.apply_fill(proposal(book, qty=action.proposed_qty, price=str(action.candidate_price)))
    cash_path(book, "8000", "1000", "7000")
