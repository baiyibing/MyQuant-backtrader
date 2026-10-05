"""TC2 narrow X1: unit builders + handcalc-style e2e through the named consumer."""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from backtest.research.minute_orders_backend.types import (
    CalendarFacts,
    CompletedBucket,
    FeeModelParams,
    InstrumentFacts,
    MarkEvent,
    MarkPrice,
    OrderStatus,
    SessionBucket,
    Side,
    SubmitOrder,
)
from backtest.research.minute_orders_intent_x1 import (
    ADAPTER_ID,
    CancelIntent,
    IntentBuildError,
    LimitIntent,
    assemble_run_input,
    build_cancel_order,
    build_submit_order,
    freeze_command_batch,
    run_x1_frozen_batch,
)

D = Decimal
TZ = ZoneInfo("Asia/Shanghai")
PREV, D0, D1 = date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29)
ZERO_FEES = FeeModelParams(D("0"), D("0.00"), ROUND_HALF_UP)


def at(value, day=D0):
    return datetime.fromisoformat(f"{day}T{value}").replace(tzinfo=TZ)


def limit_intent(order_id="O1", *, qty=100, side=Side.BUY, symbol="X",
                 time="09:29:00", effective="09:30:00", expiry="09:35:00",
                 sequence=1, day=D0, limit="10.00", command_id=None):
    return LimitIntent(
        order_id, symbol, side, qty, D(limit), at(time, day), at(time, day),
        at(effective, day), at(expiry, day), sequence, command_id,
    )


def cancel_intent(order_id="O1", *, time="09:30:30", effective="09:31:00",
                  sequence=10, command_id=None):
    return CancelIntent(
        order_id, at(time), at(time), at(effective), sequence, command_id,
    )


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


def mark(time, *, symbols=("X",), day=D0):
    return MarkEvent(
        f"mark:{day}:{time}", at(time, day), at(time, day),
        tuple(MarkPrice(s, D("10.00")) for s in symbols), "raw", "synthetic x1",
    )


def calendar_for(buckets, dates=(PREV, D0, D1)):
    sessions = {
        b.bucket_id: SessionBucket(b.bucket_id, b.start, b.end, "continuous")
        for b in buckets
    }
    return CalendarFacts(dates, tuple(sessions.values()), True, ())


def test_build_submit_order_maps_limit_intent():
    intent = limit_intent(qty=300, expiry="09:33:00")
    command = build_submit_order(intent)
    assert type(command) is SubmitOrder
    assert command.command_id == "submit:O1"
    assert command.order_id == "O1"
    assert command.side is Side.BUY
    assert command.qty == 300
    assert command.limit == D("10.00")
    assert command.order_type == "LIMIT"
    assert command.expires_at == at("09:33:00")


def test_build_cancel_order_maps_cancel_intent():
    command = build_cancel_order(cancel_intent())
    assert command.command_id == "cancel:O1"
    assert command.order_id == "O1"
    assert command.sequence == 10
    assert command.effective_at == at("09:31:00")


def test_freeze_command_batch_is_fixed_tuple_before_any_run():
    intents = [limit_intent(), limit_intent("O2", time="09:29:01", sequence=2)]
    batch = freeze_command_batch(intents)
    assert type(batch) is tuple
    assert len(batch) == 2
    assert [c.order_id for c in batch] == ["O1", "O2"]
    # Mutating the source list after freeze must not affect the batch.
    intents.append(limit_intent("O3", time="09:29:02", sequence=3))
    assert len(batch) == 2
    assert [c.order_id for c in batch] == ["O1", "O2"]


def test_freeze_rejects_duplicate_command_id_and_non_intent():
    with pytest.raises(IntentBuildError, match="duplicate command_id"):
        freeze_command_batch((limit_intent(), limit_intent(command_id="submit:O1")))
    with pytest.raises(IntentBuildError, match="LimitIntent or CancelIntent"):
        freeze_command_batch(("not-an-intent",))  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [
    dataclasses.replace(limit_intent(), order_type="MARKET"),
    dataclasses.replace(limit_intent(), qty=0),
    dataclasses.replace(limit_intent(), limit=D("10.001")),
    dataclasses.replace(limit_intent(), available_at=at("09:29:00").replace(tzinfo=None)),
    dataclasses.replace(limit_intent(), side="BUY"),  # type: ignore[arg-type]
])
def test_build_submit_rejects_invalid_intent_facts(bad):
    with pytest.raises((IntentBuildError, TypeError, ValueError)):
        build_submit_order(bad)


def test_assemble_run_input_keeps_frozen_batch_identity():
    commands = freeze_command_batch((limit_intent(),))
    buckets = (bucket(),)
    run_input = assemble_run_input(
        commands=commands,
        start_at=at("09:28:00"),
        end_at=at("09:35:00"),
        buckets=buckets,
        calendar=calendar_for(buckets),
        instruments=(facts(),),
        initial_cash=D("10000.00"),
        initial_lots=(),
        buy_fees=ZERO_FEES,
        sell_fees=ZERO_FEES,
        participation_rate=D("0.20"),
    )
    assert run_input.commands is commands


def test_handcalc_sketch_a_through_x1_consumer_batch_fixed_before_run():
    """Mirror test_minute_orders_runner sketch A via run_x1_frozen_batch."""
    intents = (
        limit_intent(qty=300, expiry="09:33:00"),
        limit_intent("O2", qty=200, time="09:29:01", expiry="09:33:00", sequence=2),
    )
    frozen = freeze_command_batch(intents)
    assert [c.command_id for c in frozen] == ["submit:O1", "submit:O2"]

    buckets = (bucket(), bucket("09:31:00"), bucket("09:32:00"))
    outcome = run_x1_frozen_batch(
        intents,
        start_at=at("09:28:00"),
        end_at=at("09:35:00"),
        buckets=buckets,
        calendar=calendar_for(buckets),
        instruments=(facts(),),
        initial_cash=D("10000.00"),
        buy_fees=ZERO_FEES,
        sell_fees=ZERO_FEES,
        participation_rate=D("0.20"),
        marks=tuple(mark(t) for t in ("09:29:01", "09:31:00", "09:32:00", "09:33:00")),
    )

    # Prove the consumer carried the a-priori freeze (identity + content).
    assert outcome.adapter_id == ADAPTER_ID
    assert outcome.commands == frozen
    assert outcome.run_input.commands is outcome.commands
    assert outcome.run_input.commands == frozen

    fills = [
        (f.proposal.order_id, f.proposal.qty, f.proposal.price, f.proposal.fee_delta)
        for f in outcome.result.fills
    ]
    assert fills == [
        ("O1", 200, D("10"), D("0")),
        ("O1", 100, D("10"), D("0")),
        ("O2", 100, D("10"), D("0")),
    ]
    states = {
        s.order.order_id: (s.status, s.filled_qty, s.remaining_qty)
        for s in outcome.result.orders
    }
    assert states == {
        "O1": (OrderStatus.FILLED, 300, 0),
        "O2": (OrderStatus.EXPIRED, 100, 100),
    }
    assert outcome.result.ledger.fees_paid == D("0")
    assert sum(l.qty for l in outcome.result.ledger.lots) == 400


def test_cancel_intent_in_frozen_batch_cancels_before_match():
    intents = (limit_intent(expiry="09:32:00"), cancel_intent())
    buckets = (bucket(),)
    outcome = run_x1_frozen_batch(
        intents,
        start_at=at("09:28:00"),
        end_at=at("09:35:00"),
        buckets=buckets,
        calendar=calendar_for(buckets),
        instruments=(facts(),),
        initial_cash=D("2000.00"),
        buy_fees=ZERO_FEES,
        sell_fees=ZERO_FEES,
        participation_rate=D("0.20"),
    )
    assert len(outcome.commands) == 2
    assert type(outcome.commands[0]) is SubmitOrder
    assert outcome.commands[1].command_id == "cancel:O1"
    states = {s.order.order_id: s.status for s in outcome.result.orders}
    assert states == {"O1": OrderStatus.CANCELLED}
    assert outcome.result.fills == ()


def test_consumer_is_in_memory_and_does_not_mutate_intents_or_files(tmp_path, monkeypatch):
    intents = (limit_intent(),)
    saved = dataclasses.asdict(intents[0])
    monkeypatch.chdir(tmp_path)
    context = os.getcwd(), dict(os.environ)
    buckets = (bucket(),)
    outcome = run_x1_frozen_batch(
        intents,
        start_at=at("09:28:00"),
        end_at=at("09:35:00"),
        buckets=buckets,
        calendar=calendar_for(buckets),
        instruments=(facts(),),
        initial_cash=D("10000.00"),
        buy_fees=ZERO_FEES,
        sell_fees=ZERO_FEES,
        participation_rate=D("0.20"),
    )
    assert outcome.result.fills
    assert dataclasses.asdict(intents[0]) == saved
    assert (os.getcwd(), dict(os.environ)) == context
    assert list(tmp_path.iterdir()) == []


def test_adapter_import_fence_types_and_runner_only(tmp_path):
    """Adapter may import types + runner (+ package self); not broker/match/ledger."""
    code = textwrap.dedent("""
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        allowed = {
            'backtest', 'backtest.research',
            'backtest.research.minute_orders_backend',
            'backtest.research.minute_orders_backend.types',
            'backtest.research.minute_orders_backend.runner',
            'backtest.research.minute_orders_intent_x1',
            'backtest.research.minute_orders_intent_x1.builders',
            'backtest.research.minute_orders_intent_x1.consumer',
        }
        # runner transitively needs broker/clock/ledger/... — fence applies to
        # *direct* adapter module imports only; validate via package source scan
        # in the parent test. Here we only assert the public consumer import works.
        from backtest.research.minute_orders_intent_x1 import (
            ADAPTER_ID, freeze_command_batch, run_x1_frozen_batch,
        )
        assert ADAPTER_ID == 'minute_orders_intent_x1'
        assert callable(freeze_command_batch) and callable(run_x1_frozen_batch)
        assert (os.getcwd(),)  # touch cwd without writing
    """)
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", code, str(Path(__file__).resolve().parents[1])],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_adapter_source_does_not_import_broker_match_ledger():
    root = Path(__file__).resolve().parents[1] / "backtest" / "research" / "minute_orders_intent_x1"
    forbidden = (
        "minute_orders_backend.broker",
        "minute_orders_backend.match",
        "minute_orders_backend.ledger",
        "minute_orders_backend.fees",
        "minute_orders_backend.clock",
        "csv_minute_backtest",
        "simulate_v7",
        "StrategyPort",
    )
    for path in sorted(root.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.name} must not reference {token}"
