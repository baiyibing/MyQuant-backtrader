"""Independent synthetic action oracles for L2-S1, not full fill/ledger traces."""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from backtest.research.minute_orders_backend import (
    BucketQuote,
    CandidateMatch,
    LimitOrderMatchInput,
    MatchContractError,
    MatchReason,
    NoMatch,
    Side,
    compute_bucket_capacity,
    match_candidates,
)


START = datetime.fromisoformat("2026-09-28T09:30:00+08:00")
END = datetime.fromisoformat("2026-09-28T09:31:00+08:00")


def order(**changes):
    values = dict(order_id="O1", symbol="X", side=Side.BUY, limit=Decimal("10.00"),
                  remaining_qty=300, lot_size=100)
    return LimitOrderMatchInput(**(values | changes))


def bucket(**changes):
    values = dict(symbol="X", bucket_id="D0-0930", start=START, end=END,
                  close=Decimal("10.00"))
    return BucketQuote(**(values | changes))


@pytest.mark.parametrize("side,close,expected_price", [
    (Side.BUY, "9.99", "9.99"),
    (Side.BUY, "10.00", "10.00"),
    (Side.BUY, "10.01", None),
    (Side.SELL, "10.01", "10.01"),
    (Side.SELL, "10.00", "10.00"),
    (Side.SELL, "9.99", None),
])
def test_inclusive_limit_close_oracle(side, close, expected_price):
    result = match_candidates(order(side=side), bucket(close=Decimal(close)),
                              capacity_remaining=200)
    if expected_price is None:
        assert result == NoMatch("O1", "X", "D0-0930", MatchReason.PRICE_NOT_CROSSED)
        assert result.reason == "price_not_crossed"
    else:
        assert result == CandidateMatch(
            order_id="O1", symbol="X", side=side,
            candidate_price=Decimal(expected_price), proposed_qty=200,
            bucket_id="D0-0930", bucket_start=START, bucket_end=END,
        )
        assert result.reason == "price_crossed"


def test_candidate_keeps_exact_decimal_close_and_bucket_evidence():
    quote = bucket(close=Decimal("9.9000"))
    with localcontext() as context:
        context.prec = 2
        result = match_candidates(order(), quote, capacity_remaining=200)
    assert isinstance(result, CandidateMatch)
    assert result.candidate_price is quote.close
    assert result.candidate_price.as_tuple() == Decimal("9.9000").as_tuple()
    assert (result.bucket_id, result.bucket_start, result.bucket_end) == (
        "D0-0930", START, END
    )


@pytest.mark.parametrize("remaining,capacity,lot,expected", [
    (300, 250, 100, 200),
    (100, 299, 100, 100),
    (300, 500, 100, 300),
    (300, 99, 100, 0),
    (300, 0, 100, 0),
    (0, 200, 100, 0),
    (600, 550, 200, 400),
])
@pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
def test_lot_floor_and_minimum_proposal(remaining, capacity, lot, expected, side):
    result = match_candidates(
        order(side=side, remaining_qty=remaining, lot_size=lot), bucket(),
        capacity_remaining=capacity,
    )
    if expected == 0:
        assert result == NoMatch("O1", "X", "D0-0930", MatchReason.ZERO_AFTER_LOT)
        assert result.reason == "zero_after_lot"
    else:
        assert isinstance(result, CandidateMatch)
        assert result.proposed_qty == expected


def test_price_no_match_precedes_zero_proposal():
    result = match_candidates(order(), bucket(close=Decimal("10.01")),
                              capacity_remaining=0)
    assert result.reason is MatchReason.PRICE_NOT_CROSSED


def test_sketch_a_actions_use_caller_supplied_remaining_capacity():
    # S0 sketch A, action projection only. These are explicit caller snapshots;
    # no local fill application, capacity store, lifecycle or cash simulation.
    o1, o2 = order(), order(order_id="O2", remaining_qty=200)
    q1 = bucket()
    first = match_candidates(o1, q1, capacity_remaining=200)
    second = match_candidates(o2, q1, capacity_remaining=0)
    assert isinstance(first, CandidateMatch)
    assert first.proposed_qty == 200
    assert second == NoMatch("O2", "X", "D0-0930", MatchReason.ZERO_AFTER_LOT)

    q2 = bucket(bucket_id="D0-0931", start=END,
                end=datetime.fromisoformat("2026-09-28T09:32:00+08:00"))
    next_o1 = match_candidates(replace(o1, remaining_qty=100), q2, capacity_remaining=200)
    next_o2 = match_candidates(o2, q2, capacity_remaining=100)
    assert isinstance(next_o1, CandidateMatch) and next_o1.proposed_qty == 100
    assert isinstance(next_o2, CandidateMatch) and next_o2.proposed_qty == 100


def test_sketch_d_both_sides_consume_caller_supplied_shared_remainder():
    # Caller supplies the post-SELL remainder; this does not test sell-first order.
    sell = match_candidates(order(order_id="S1", side=Side.SELL, remaining_qty=100),
                            bucket(), capacity_remaining=200)
    buy = match_candidates(order(remaining_qty=200), bucket(), capacity_remaining=100)
    assert isinstance(sell, CandidateMatch) and sell.proposed_qty == 100
    assert isinstance(buy, CandidateMatch) and buy.proposed_qty == 100


def test_inputs_and_actions_are_frozen_and_calls_have_no_capacity_state():
    snapshot, quote = order(), bucket()
    before = asdict(snapshot), asdict(quote)
    first = match_candidates(snapshot, quote, capacity_remaining=200)
    repeated = match_candidates(snapshot, quote, capacity_remaining=200)
    empty = match_candidates(snapshot, quote, capacity_remaining=0)
    assert repeated == first  # Merely proposing did not consume the supplied 200.
    assert (asdict(snapshot), asdict(quote)) == before
    for value, name, replacement in (
        (snapshot, "remaining_qty", 0), (quote, "close", Decimal("1.00")),
        (first, "proposed_qty", 0), (empty, "reason", MatchReason.PRICE_NOT_CROSSED),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, name, replacement)


@pytest.mark.parametrize("lot,volume,rate,expected", [
    (100, 1000, "0.20", 200),  # S0 sketch A.
    (100, 500, "0.20", 100),   # S0 sketch E, second bucket.
    (100, 499, "0.20", 0),
    (100, 1499, "0.20", 200),
    (100, 0, "0.20", 0),
    (100, 1000, "0", 0),
    (100, 1050, "1", 1000),
    (200, 1500, "0.30", 400),
])
def test_capacity_hand_calculations(lot, volume, rate, expected):
    assert compute_bucket_capacity(lot, volume, Decimal(rate)) == expected


def test_capacity_never_rounds_up_at_decimal_context_boundary():
    with localcontext() as context:
        context.prec = 3
        context.clear_flags()
        flags_before = context.flags.copy()
        # Just below 200 shares; multiplication at precision 3 would round to 200.
        assert compute_bucket_capacity(
            100, 1000, Decimal("0.19999999999999999999999999999")
        ) == 100
        assert context.flags == flags_before


@pytest.mark.parametrize("bad", [
    None, "10.00", 10, 10.0, True, Decimal("NaN"), Decimal("sNaN"),
    Decimal("Infinity"), Decimal("-Infinity"), Decimal("0"), Decimal("-0"),
    Decimal("-1.00"), Decimal("10.001"),
])
@pytest.mark.parametrize("field", ["close", "limit"])
def test_bad_price_fails_closed_with_typed_contract_error(field, bad):
    with pytest.raises(MatchContractError, match=field):
        if field == "close":
            bucket(close=bad)
        else:
            order(limit=bad)


@pytest.mark.parametrize("changes", [
    {"order_id": None}, {"order_id": ""}, {"symbol": "  "},
    {"side": None}, {"side": "BUY"}, {"side": "HOLD"},
    {"order_type": "MARKET"}, {"order_type": "STOP"}, {"order_type": None},
    {"remaining_qty": None}, {"remaining_qty": -100}, {"remaining_qty": 150},
    {"remaining_qty": 100.0}, {"remaining_qty": True},
    {"lot_size": None}, {"lot_size": 0}, {"lot_size": -100},
    {"lot_size": 100.0}, {"lot_size": True},
])
def test_invalid_order_facts_fail_closed(changes):
    with pytest.raises(MatchContractError):
        order(**changes)


@pytest.mark.parametrize("changes", [
    {"symbol": None}, {"bucket_id": ""}, {"bucket_id": None},
    {"start": None}, {"end": None}, {"start": "09:30"},
    {"start": START.replace(tzinfo=None)}, {"end": END.replace(tzinfo=None)},
    {"end": START}, {"start": END, "end": START},
])
def test_missing_or_invalid_bucket_evidence_fails_closed(changes):
    with pytest.raises(MatchContractError):
        bucket(**changes)


@pytest.mark.parametrize("bad", [None, -1, True, 200.0, Decimal(200), "200"])
def test_bad_capacity_is_an_error_even_when_price_does_not_cross(bad):
    with pytest.raises(MatchContractError, match="capacity_remaining"):
        match_candidates(order(), bucket(close=Decimal("11.00")), capacity_remaining=bad)


def test_wrong_symbols_or_snapshot_types_fail_closed():
    with pytest.raises(MatchContractError, match="symbols"):
        match_candidates(order(), bucket(symbol="Y"), capacity_remaining=0)
    with pytest.raises(MatchContractError, match="order"):
        match_candidates(None, bucket(), capacity_remaining=200)
    with pytest.raises(MatchContractError, match="quote"):
        match_candidates(order(), {"close": Decimal("10.00")}, capacity_remaining=200)


@pytest.mark.parametrize("lot,volume,rate", [
    (0, 1000, Decimal("0.2")), (True, 1000, Decimal("0.2")),
    (100, None, Decimal("0.2")), (100, -1, Decimal("0.2")),
    (100, True, Decimal("0.2")), (100, 1000.0, Decimal("0.2")),
    (100, 1000, None), (100, 1000, 0.2), (100, 1000, "0.2"),
    (100, 1000, Decimal("NaN")), (100, 1000, Decimal("sNaN")),
    (100, 1000, Decimal("Infinity")), (100, 1000, Decimal("-0.01")),
    (100, 1000, Decimal("1.01")),
])
def test_capacity_helper_rejects_missing_or_invalid_explicit_inputs(lot, volume, rate):
    with pytest.raises(MatchContractError):
        compute_bucket_capacity(lot, volume, rate)


def test_fresh_import_allows_only_stdlib_and_matchcore_package():
    code = textwrap.dedent("""
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        allowed = {
            'backtest', 'backtest.research',
            'backtest.research.minute_orders_backend',
            'backtest.research.minute_orders_backend.types',
            'backtest.research.minute_orders_backend.match',
            'backtest.research.minute_orders_backend.fees',
            'backtest.research.minute_orders_backend.ledger',
        }
        def permitted(name):
            return name in allowed or name.split('.')[0] in sys.stdlib_module_names
        class ImportFence:
            def find_spec(self, fullname, path=None, target=None):
                assert permitted(fullname), 'forbidden import: ' + fullname
                return None
        sys.meta_path.insert(0, ImportFence())
        before = set(sys.modules)
        context = os.getcwd(), dict(os.environ)
        import backtest.research.minute_orders_backend as backend
        assert all(hasattr(backend, name) for name in backend.__all__)
        assert not hasattr(backend, 'run_minute_orders_research')
        unexpected = {name for name in set(sys.modules) - before if not permitted(name)}
        assert not unexpected, sorted(unexpected)
        assert (os.getcwd(), dict(os.environ)) == context
    """)
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", code, str(Path(__file__).resolve().parents[1])],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
