"""Independent S0 A-E hand calculations through the in-memory S3 API."""

import dataclasses
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, Inexact, ROUND_HALF_UP, localcontext
from zoneinfo import ZoneInfo

import pytest

from backtest.research.minute_orders_backend.broker import BrokerCore
from backtest.research.minute_orders_backend.clock import Clock
from backtest.research.minute_orders_backend.runner import run_minute_orders_research as run
from backtest.research.minute_orders_backend.types import (
    CalendarFacts, CancelOrder, CompletedBucket, FeeModelParams, InstrumentFacts,
    LotPosition, MarkEvent, MarkPrice, OrderStatus, Phase, RunContractError,
    RunInput, SessionBucket, Side, SubmitOrder,
)

D = Decimal
TZ = ZoneInfo("Asia/Shanghai")
PREV, D0, D1 = date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29)
ZERO_FEES = FeeModelParams(D("0"), D("0.00"), ROUND_HALF_UP)


def at(value, day=D0):
    return datetime.fromisoformat(f"{day}T{value}").replace(tzinfo=TZ)


def submit(order_id="O1", *, qty=100, side=Side.BUY, symbol="X", time="09:29:00",
           effective="09:30:00", expiry="09:35:00", sequence=1, day=D0, limit="10.00"):
    return SubmitOrder(
        "submit:" + order_id, order_id, symbol, side, qty, D(limit), at(time, day),
        at(time, day), at(effective, day), at(expiry, day), sequence,
    )


def cancel(order_id="O1", *, time="09:30:30", effective="09:31:00", sequence=10,
           command_id="cancel:O1"):
    return CancelOrder(command_id, order_id, at(time), at(time), at(effective), sequence)


def bucket(start="09:30:00", *, day=D0, symbol="X", close="10.00", volume=1000,
           missing=False, halted=False):
    begin = at(start, day)
    return CompletedBucket(
        symbol, begin.isoformat(), begin, begin + timedelta(minutes=1),
        None if close is None else D(close), volume, missing, halted,
    )


def facts(symbol="X", day=D0):
    return InstrumentFacts(symbol, day, "main", "raw", D("0.01"), 100,
                           D("10.00"), D("9.00"), D("11.00"))


def initial_lot(qty=200, *, symbol="X", lot_id="initial"):
    return LotPosition(lot_id, symbol, PREV, D0, qty, 100)


def mark(time, *, symbols=("X",), day=D0):
    return MarkEvent(
        f"mark:{day}:{time}", at(time, day), at(time, day),
        tuple(MarkPrice(s, D("10.00")) for s in symbols), "raw", "synthetic handcalc",
    )


def inputs(*, commands=None, buckets=None, cash="10000.00", lots=(), marks=(),
           end=None, dates=(PREV, D0, D1), instruments=None, fees=ZERO_FEES):
    commands = (submit(),) if commands is None else commands
    buckets = (bucket(),) if buckets is None else buckets
    sessions = {b.bucket_id: SessionBucket(b.bucket_id, b.start, b.end, "continuous")
                for b in buckets}
    return RunInput(
        at("09:28:00"), at("09:35:00") if end is None else end, tuple(commands), tuple(buckets),
        CalendarFacts(dates, tuple(sessions.values()), True, ()),
        (facts(),) if instruments is None else tuple(instruments), D(cash), tuple(lots),
        fees, fees, D("0.20"), tuple(marks), False,
    )


def states(result):
    return {s.order.order_id: (s.status, s.filled_qty, s.remaining_qty) for s in result.orders}


def fills(result):
    return [(f.proposal.order_id, f.proposal.qty, f.proposal.price, f.proposal.fee_delta)
            for f in result.fills]


def cash(snapshot):
    return snapshot.cash, snapshot.reserved_cash, snapshot.free_cash


def test_sketch_a_full_path_two_buys_shared_capacity_and_expiry():
    request = inputs(
        commands=(submit(qty=300, expiry="09:33:00"),
                  submit("O2", qty=200, time="09:29:01", expiry="09:33:00", sequence=2)),
        buckets=(bucket(), bucket("09:31:00"), bucket("09:32:00")),
        marks=tuple(mark(t) for t in ("09:29:01", "09:31:00", "09:32:00", "09:33:00")),
    )
    result = run(request)
    assert fills(result) == [("O1", 200, D("10"), D("0")),
                             ("O1", 100, D("10"), D("0")),
                             ("O2", 100, D("10"), D("0"))]
    assert states(result) == {"O1": (OrderStatus.FILLED, 300, 0),
                              "O2": (OrderStatus.EXPIRED, 100, 100)}
    assert [cash(m.ledger) for m in result.marks] == [
        (D("10000"), D("5000"), D("5000")),
        (D("8000"), D("3000"), D("5000")),
        (D("6000"), D("1000"), D("5000")),
        (D("6000"), D("0"), D("6000")),
    ]
    assert [(b.capacity, b.remaining) for b in result.ledger.buckets] == [(200, 0), (200, 0), (200, 200)]
    assert sum(l.qty for l in result.ledger.lots) == 400
    assert {l.sellable_date for l in result.ledger.lots} == {D1}
    assert result.ledger.fees_paid == D("0")
    assert [t.state.status for t in result.transitions if t.state.order.order_id == "O2"] == [
        OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED, OrderStatus.EXPIRED,
    ]


@pytest.mark.parametrize("case,expiry,commands,status", [
    ("B1", "09:31:00", (), OrderStatus.EXPIRED),
    ("B2", "09:32:00", (cancel(),), OrderStatus.CANCELLED),
    ("B3", "09:31:00", (cancel(),), OrderStatus.EXPIRED),
])
def test_b1_b2_b3_expiry_and_cancel_precede_match(case, expiry, commands, status):
    result = run(inputs(cash="2000", commands=(submit(expiry=expiry),) + commands))
    assert states(result) == {"O1": (status, 0, 100)}
    assert result.fills == ()
    assert cash(result.ledger) == (D("2000"), D("0"), D("2000"))
    assert [t.state.status for t in result.transitions] == [
        OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, status,
    ]


@pytest.mark.parametrize("time,effective,expiry,match_time", [
    ("09:30:00", "09:30:00", "09:32:00", None),  # B4
    ("09:30:30", "09:30:30", "09:33:00", "09:32:00"),  # B5
    ("09:31:00", "09:31:00", "09:34:00", "09:33:00"),  # B6
    ("09:29:00", "09:31:00", "09:34:00", "09:32:00"),  # effective gate
])
def test_late_submit_and_effective_gates(time, effective, expiry, match_time):
    result = run(inputs(
        commands=(submit(time=time, effective=effective, expiry=expiry),),
        buckets=(bucket(), bucket("09:31:00"), bucket("09:32:00")),
    ))
    matched = [t.event.event_time for t in result.transitions if t.event.phase is Phase.MATCH]
    assert matched == ([] if match_time is None else [at(match_time)])
    assert states(result)["O1"] == (
        (OrderStatus.EXPIRED, 0, 100) if match_time is None else (OrderStatus.FILLED, 100, 0)
    )


def test_d_rejected_buy_never_revives_new_same_timestamp_submit_uses_sell_proceeds():
    result = run(inputs(
        cash="0", lots=(initial_lot(),),
        commands=(submit("rejected", time="09:28:00"),
                  submit("sell", side=Side.SELL),
                  submit("new", time="09:31:00", effective="09:31:00")),
        buckets=(bucket(), bucket("09:31:00"), bucket("09:32:00")),
        marks=(mark("09:31:00"), mark("09:32:00")),
    ))
    assert fills(result) == [("sell", 100, D("10"), D("0")), ("new", 100, D("10"), D("0"))]
    assert states(result) == {"rejected": (OrderStatus.REJECTED, 0, 100),
                              "sell": (OrderStatus.FILLED, 100, 0),
                              "new": (OrderStatus.FILLED, 100, 0)}
    assert [cash(m.ledger) for m in result.marks] == [(D("1000"), D("1000"), D("0"))] * 2
    assert [(t.state.order.order_id, t.event.event_time) for t in result.transitions
            if t.event.phase is Phase.MATCH] == [("sell", at("09:31:00")), ("new", at("09:33:00"))]
    assert cash(result.ledger) == (D("0"), D("0"), D("0"))
    assert sum(l.qty for l in result.ledger.lots) == 200


def test_sell_before_earlier_buy_shares_capacity_and_preserves_active_remainder():
    result = run(inputs(
        cash="2000", lots=(initial_lot(100),), end=at("09:31:00"),
        commands=(submit("buy", qty=200, time="09:28:00"), submit("sell", side=Side.SELL)),
    ))
    assert fills(result) == [("sell", 100, D("10"), D("0")), ("buy", 100, D("10"), D("0"))]
    assert states(result)["buy"] == (OrderStatus.PARTIALLY_FILLED, 100, 100)
    assert cash(result.ledger) == (D("2000"), D("1000"), D("1000"))
    assert result.ledger.buckets[0].remaining == 0


def test_c_t_plus_one_and_duplicate_sell_reservations():
    result = run(inputs(
        commands=(submit("buy", qty=200),
                  submit("same_day", side=Side.SELL, time="09:32:00", effective="09:32:00"),
                  submit("S1", qty=200, side=Side.SELL, day=D1),
                  submit("S2", side=Side.SELL, day=D1, time="09:29:01", sequence=2)),
        buckets=(bucket(), bucket(day=D1)), end=at("09:35:00", D1),
        instruments=(facts(), facts(day=D1)),
    ))
    assert fills(result) == [("buy", 200, D("10"), D("0")), ("S1", 200, D("10"), D("0"))]
    assert states(result)["same_day"] == states(result)["S2"] == (OrderStatus.REJECTED, 0, 100)
    assert result.ledger.lots == ()
    assert cash(result.ledger) == (D("10000"), D("0"), D("10000"))


def test_e_cumulative_fee_and_cancel_releases_only_remaining_reservation():
    fees = FeeModelParams(D("0.001"), D("5.00"), ROUND_HALF_UP)
    result = run(inputs(
        fees=fees, commands=(submit(qty=400), cancel(time="09:32:00", effective="09:32:30")),
        buckets=(bucket(), bucket("09:31:00", volume=500)),
        marks=tuple(mark(t) for t in ("09:29:00", "09:31:00", "09:32:00", "09:32:30")),
    ))
    assert fills(result) == [("O1", 200, D("10"), D("5")), ("O1", 100, D("10"), D("0"))]
    assert [cash(m.ledger) for m in result.marks] == [
        (D("10000"), D("4005"), D("5995")), (D("7995"), D("2000"), D("5995")),
        (D("6995"), D("1000"), D("5995")), (D("6995"), D("0"), D("6995")),
    ]
    assert states(result)["O1"] == (OrderStatus.CANCELLED, 300, 100)
    rejected = run(inputs(cash="4004", fees=fees, commands=(submit(qty=400),)))
    assert states(rejected)["O1"] == (OrderStatus.REJECTED, 0, 400)
    assert rejected.fills == ()


def result_hash(result):
    def encode(value):
        if isinstance(value, (Decimal, date)):
            return str(value)
        if isinstance(value, frozenset):
            return sorted(value)
        raise TypeError(type(value))
    return hashlib.sha256(json.dumps(dataclasses.asdict(result), default=encode,
                                     sort_keys=True).encode("utf-8")).hexdigest()


def test_command_permutations_preserving_sequence_have_identical_result_and_hash():
    request = inputs(
        commands=(submit("Z", qty=200, sequence=1), submit("A", qty=200, sequence=2),
                  cancel("Z", effective="09:32:00")),
        buckets=(bucket(), bucket("09:31:00")),
    )
    expected = run(request)
    assert fills(expected) == [("Z", 200, D("10"), D("0")), ("A", 200, D("10"), D("0"))]
    for commands in itertools.permutations(request.commands):
        actual = run(dataclasses.replace(request, commands=commands))
        assert actual == expected
        assert result_hash(actual) == result_hash(expected)


def test_cross_symbol_match_global_sell_first_then_timestamp_sequence_order_id():
    result = run(inputs(
        commands=(submit("buy-X", symbol="X", time="09:28:00"),
                  submit("sell-Y", symbol="Y", side=Side.SELL)),
        buckets=(bucket(symbol="X"), bucket(symbol="Y")),
        instruments=(facts("X"), facts("Y")), lots=(initial_lot(symbol="Y"),),
    ))
    assert [f.proposal.order_id for f in result.fills] == ["sell-Y", "buy-X"]


@pytest.mark.parametrize("orders,winner", [
    ((submit("Z", time="09:29:00", sequence=9), submit("A", time="09:29:01", sequence=1)), "Z"),
    ((submit("Z", sequence=1), submit("A", sequence=2)), "Z"),
    ((submit("Z", sequence=1), submit("A", sequence=1)), "A"),
])
def test_accept_and_match_use_explicit_total_order(orders, winner):
    result = run(inputs(commands=orders, cash="1000"))
    assert [f.proposal.order_id for f in result.fills] == [winner]
    assert sum(s.status is OrderStatus.REJECTED for s in result.orders) == 1


def test_future_close_and_volume_do_not_change_earlier_observation():
    request = inputs(commands=(submit(qty=300),),
                     buckets=(bucket(), bucket("09:31:00")), marks=(mark("09:31:00"),))
    changed = dataclasses.replace(request, buckets=(request.buckets[0],
                                  dataclasses.replace(request.buckets[1], close=D("9.50"), volume_shares=0)))
    first, second = run(request), run(changed)
    assert first.marks == second.marks
    assert first.fills[:1] == second.fills[:1]
    assert len(first.fills) == 2 and len(second.fills) == 1


@pytest.mark.parametrize("first", [
    bucket(close=None, volume=None, missing=True), bucket(halted=True), bucket(volume=0),
])
def test_attested_missing_halt_or_zero_volume_keeps_order_until_next_bucket(first):
    result = run(inputs(buckets=(first, bucket("09:31:00"))))
    assert len(result.fills) == 1
    assert result.fills[0].proposal.bucket_id == at("09:31:00").isoformat()
    assert [t.event.event_time for t in result.transitions if t.event.phase is Phase.MATCH] == [at("09:32:00")]


@pytest.mark.parametrize("side,close,limit,expected", [
    (Side.BUY, "11.00", "11.00", 0), (Side.SELL, "9.00", "9.00", 0),
    (Side.SELL, "11.00", "10.00", 1), (Side.BUY, "9.00", "10.00", 1),
])
def test_conservative_directional_daily_limit_gates(side, close, limit, expected):
    result = run(inputs(commands=(submit(side=side, limit=limit),),
                        buckets=(bucket(close=close),), lots=(initial_lot(),)))
    assert len(result.fills) == expected


def test_terminal_cancels_are_noops_and_distinct_same_phase_sequences_are_valid():
    request = inputs(commands=(
        submit(qty=300), cancel(effective="09:31:30"),
        cancel(effective="09:31:30", sequence=11, command_id="cancel-again"),
        cancel(time="09:32:00", effective="09:33:00", command_id="cancel-terminal"),
    ))
    result = run(request)
    assert states(result)["O1"] == (OrderStatus.CANCELLED, 200, 100)
    assert [t.state.status for t in result.transitions].count(OrderStatus.CANCELLED) == 1
    assert cash(result.ledger) == (D("8000"), D("0"), D("8000"))


@pytest.mark.parametrize("termination", ["expiry", "cancel"])
def test_sell_remainder_release_funds_same_timestamp_new_sell_reservation(termination):
    commands = (
        submit("old", qty=200, side=Side.SELL,
               expiry="09:32:00" if termination == "expiry" else "09:35:00"),
        submit("new", qty=200, side=Side.SELL, time="09:32:00", effective="09:32:00"),
    )
    if termination == "cancel":
        commands += (cancel("old", effective="09:32:00"),)
    result = run(inputs(
        cash="0", lots=(initial_lot(300),), commands=commands,
        buckets=(bucket(volume=500), bucket("09:31:00", volume=500),
                 bucket("09:32:00"), bucket("09:33:00")),
        marks=(mark("09:32:00"),),
    ))
    assert fills(result) == [("old", 100, D("10"), D("0")), ("new", 200, D("10"), D("0"))]
    assert result.marks[0].ledger.reserved_sellable_qty("X") == 200
    assert result.ledger.lots == ()
    assert cash(result.ledger) == (D("3000"), D("0"), D("3000"))


@pytest.mark.parametrize("commands,message", [
    ((submit(), submit()), "duplicate command_id"),
    ((submit(), dataclasses.replace(submit(), command_id="another")), "duplicate order_id"),
    ((submit(), cancel(), dataclasses.replace(cancel(), command_id="another")), "conflicting"),
    ((submit(), cancel("unknown")), "unknown order"),
    ((submit(), cancel(time="09:28:00", effective="09:29:00")), "after order submission"),
])
def test_bad_command_identities_and_conflicting_keys_fail_closed(commands, message):
    with pytest.raises(RunContractError, match=message):
        run(inputs(commands=commands))


@pytest.mark.parametrize("changes", [
    {"close": None}, {"volume_shares": None}, {"volume_shares": -1}, {"volume_shares": True},
    {"close": D("NaN")}, {"close": D("11.01")}, {"close": D("10.001")},
    {"missing": True}, {"halted": None}, {"missing": None},
    {"start": at("09:30:00").replace(tzinfo=None)}, {"end": at("09:32:00")},
    {"bucket_id": "unknown"},
])
def test_bad_bucket_fields_fail_closed(changes):
    request = inputs()
    request = dataclasses.replace(request, buckets=(dataclasses.replace(request.buckets[0], **changes),))
    with pytest.raises(ValueError):
        run(request)


@pytest.mark.parametrize("change", ["duplicate", "unordered", "missing_coverage", "session_gap"])
def test_duplicate_unordered_or_unattested_missing_buckets_fail_closed(change):
    request = inputs(buckets=(bucket(), bucket("09:31:00")))
    if change == "duplicate":
        request = dataclasses.replace(request, buckets=request.buckets + request.buckets[:1])
    elif change == "unordered":
        request = dataclasses.replace(request, buckets=request.buckets[::-1])
    elif change == "missing_coverage":
        request = dataclasses.replace(request, buckets=request.buckets[:1])
    else:
        request = inputs(buckets=(bucket(), bucket("09:32:00")))
    with pytest.raises(RunContractError):
        run(request)


@pytest.mark.parametrize("start", ["09:29:00", "11:30:00", "12:59:00", "15:00:00", "09:30:01"])
def test_noncontinuous_or_misaligned_buckets_fail_closed(start):
    with pytest.raises(RunContractError):
        run(inputs(buckets=(bucket(start),), end=at("16:00:00")))


def test_explicit_lunch_gap_is_legal_and_capacity_does_not_carry():
    result = run(inputs(
        commands=(submit(qty=300, expiry="14:00:00"),),
        buckets=(bucket("11:29:00", volume=500), bucket("13:00:00", volume=500)),
        end=at("14:00:00"),
    ))
    assert [f.proposal.qty for f in result.fills] == [100, 100]
    assert states(result)["O1"] == (OrderStatus.EXPIRED, 200, 100)


@pytest.mark.parametrize("changes", [
    {"available_at": at("09:29:01")}, {"effective_at": at("09:28:00")},
    {"expires_at": at("09:30:00")}, {"expires_at": None},
    {"submitted_at": at("09:29:00").replace(tzinfo=None)},
    {"available_at": at("09:29:00").astimezone(timezone.utc)},
    {"order_type": "MARKET"}, {"qty": 0}, {"qty": 150}, {"qty": -100},
    {"symbol": "unknown"}, {"sequence": True}, {"side": "BUY"},
])
def test_invalid_order_facts_fail_closed(changes):
    with pytest.raises(ValueError):
        run(inputs(commands=(dataclasses.replace(submit(), **changes),)))


@pytest.mark.parametrize("changes", [
    {"board": "STAR"}, {"price_domain": "front"}, {"reference_price": None},
    {"tick_size": D("0")}, {"tick_size": D("0.03")}, {"limit_up": D("8")},
    {"lot_size": 0}, {"symbol": None}, {"trade_date": at("09:30:00")},
])
def test_bad_instrument_facts_fail_closed(changes):
    with pytest.raises(ValueError):
        run(inputs(instruments=(dataclasses.replace(facts(), **changes),)))


@pytest.mark.parametrize("changes", [
    {"company_actions_covered": False}, {"company_actions": ("exdiv",)},
    {"trading_dates": (D0, PREV, D1)}, {"trading_dates": (D0, D0, D1)},
    {"trading_dates": (PREV, D1)},
])
def test_bad_calendar_or_company_actions_fail_closed(changes):
    request = inputs()
    with pytest.raises(RunContractError):
        run(dataclasses.replace(request, calendar=dataclasses.replace(request.calendar, **changes)))


def test_next_trading_date_must_be_supplied_no_natural_day_fallback():
    with pytest.raises(RunContractError, match="next explicit trading date"):
        run(inputs(dates=(PREV, D0)))
    friday_order = dataclasses.replace(submit(), available_at=at("09:29:00", PREV),
        submitted_at=at("09:29:00", PREV), effective_at=at("09:30:00", PREV),
        expires_at=at("09:35:00", PREV))
    request = inputs(commands=(friday_order,), buckets=(bucket(day=PREV),),
                     instruments=(facts(day=PREV),), end=at("09:35:00", PREV))
    result = run(dataclasses.replace(request, start_at=at("09:28:00", PREV)))
    assert result.ledger.lots[0].sellable_date == D0


def test_empty_marks_opt_in_and_mark_observes_post_match_post_submit_without_trading():
    request = inputs()
    plain = run(request)
    observed = run(dataclasses.replace(request, marks=(mark("09:31:00"),), requires_marks=True))
    assert observed.fills == plain.fills
    assert observed.orders == plain.orders
    assert observed.ledger == plain.ledger
    assert observed.marks[0].ledger.cash == D("9000")
    with pytest.raises(RunContractError, match="required marks"):
        run(dataclasses.replace(request, requires_marks=True))


@pytest.mark.parametrize("bad_mark", [
    dataclasses.replace(mark("09:31:00"), available_at=at("09:32:00")),
    dataclasses.replace(mark("09:31:00"), available_at=at("09:30:00")),
    dataclasses.replace(mark("09:31:00"), prices=()),
    dataclasses.replace(mark("09:31:00"), prices=(MarkPrice("X", None),)),
    dataclasses.replace(mark("09:31:00"), prices=(MarkPrice("Y", D("10")),)),
    dataclasses.replace(mark("09:31:00"), price_domain="front"),
])
def test_provided_invalid_marks_always_fail_even_when_not_required(bad_mark):
    with pytest.raises(ValueError):
        run(inputs(marks=(bad_mark,)))


def test_low_decimal_precision_does_not_change_economics():
    request = inputs(commands=(submit(qty=300),), buckets=(bucket(), bucket("09:31:00")),
                     fees=FeeModelParams(D("0.001"), D("5.00"), ROUND_HALF_UP))
    expected = run(request)
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        assert run(request) == expected


def test_failed_mark_aborts_without_undoing_previously_committed_fill_or_retrying():
    broker = BrokerCore(inputs(marks=(dataclasses.replace(mark("09:31:00"), prices=()),)))
    with pytest.raises(RunContractError, match="held symbol"):
        broker.run()
    snapshot = broker.ledger.snapshot()
    assert cash(snapshot) == (D("9000"), D("0"), D("9000"))
    assert len(snapshot.applied_fills) == 1
    with pytest.raises(RunContractError, match="single-use"):
        broker.run()
    assert broker.ledger.snapshot() == snapshot


def test_clock_total_order_and_broker_single_use():
    request = inputs(commands=(submit(), cancel()), marks=(mark("09:31:00"),))
    clock = Clock(request)
    assert tuple(e.key for e in clock.events) == tuple(sorted(e.key for e in clock.events))
    phases = [e.phase for e in clock.events if e.event_time == at("09:31:00")]
    assert phases == [Phase.CANCEL, Phase.BUCKET, Phase.MATCH, Phase.MARK]
    broker = BrokerCore(request)
    broker.run()
    with pytest.raises(RunContractError, match="single-use"):
        broker.run()


def test_runner_import_fence_no_l1_vendor_loaders_or_io(tmp_path):
    code = textwrap.dedent("""
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        allowed = {'backtest', 'backtest.research', 'backtest.research.minute_orders_backend'}
        allowed.update('backtest.research.minute_orders_backend.' + part for part in
                       ('types', 'match', 'fees', 'ledger', 'clock', 'broker', 'runner'))
        def permitted(name):
            return name in allowed or name.split('.')[0] in sys.stdlib_module_names
        class ImportFence:
            def find_spec(self, fullname, path=None, target=None):
                assert permitted(fullname), 'forbidden import: ' + fullname
        sys.meta_path.insert(0, ImportFence())
        before = set(sys.modules)
        context = os.getcwd(), dict(os.environ)
        from backtest.research.minute_orders_backend.runner import run_minute_orders_research
        assert callable(run_minute_orders_research)
        assert all(permitted(name) for name in set(sys.modules) - before)
        assert (os.getcwd(), dict(os.environ)) == context
    """)
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", code, str(Path(__file__).resolve().parents[1])],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert list(tmp_path.iterdir()) == []


def test_run_is_in_memory_and_does_not_mutate_input_context_or_files(tmp_path, monkeypatch):
    request = inputs()
    saved = dataclasses.asdict(request)
    monkeypatch.chdir(tmp_path)
    context = os.getcwd(), dict(os.environ)
    result = run(request)
    assert result.fills
    assert dataclasses.asdict(request) == saved
    assert (os.getcwd(), dict(os.environ)) == context
    assert list(tmp_path.iterdir()) == []
