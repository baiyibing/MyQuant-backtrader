"""Strict wire boundary; economics remain independently tested in S1-S4."""

from copy import deepcopy
from dataclasses import fields, replace
from datetime import timezone
from decimal import Decimal, Inexact, localcontext
import json
from pathlib import Path

import pytest

from backtest.research.minute_orders_backend import input_codec as codec
from backtest.research.minute_orders_backend.types import LotPosition, Side

FIXTURE = Path(__file__).parent / "fixtures/minute_orders/partial_cancel_expiry_v1.json"


def document():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def set_path(data, path, value):
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


def test_complete_fixture_roundtrip_preserves_decimals_named_zone_and_types():
    raw = document()
    before = deepcopy(raw)
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        run = codec.decode_run_input(raw)
        assert codec.loads_run_input(codec.dumps_run_input(run)) == run
    assert codec.encode_run_input(run) == raw == before
    assert run.start_at.tzinfo.key == "Asia/Shanghai"
    assert run.commands[0].side is Side.BUY
    assert run.initial_cash.as_tuple() == Decimal("10000.00").as_tuple()
    assert run.participation_rate.as_tuple() == Decimal("0.20").as_tuple()
    assert run.buy_fees.rate == Decimal("0.001")
    assert type(run.commands[0].qty) is int and type(run.commands) is tuple
    for kind, schema in codec._RECORDS.items():
        assert set(schema) == {field.name for field in fields(kind)}


def test_lots_missing_halts_and_company_action_data_are_lossless():
    run = codec.load_run_input(FIXTURE)
    lot = LotPosition("L", "X", run.calendar.trading_dates[0], run.start_at.date(), 200, 100, 0)
    run = replace(run, initial_lots=(lot,), buckets=(
        replace(run.buckets[0], close=None, volume_shares=None, missing=True),
        replace(run.buckets[1], halted=True), *run.buckets[2:],
    ), calendar=replace(run.calendar, company_actions_covered=False,
                        company_actions=({"type": "unsupported", "amount": "0.50"},)))
    wire = codec.encode_run_input(run)
    assert wire["data"]["buckets"][0]["close"] is None
    assert wire["data"]["buckets"][0]["volume_shares"] is None
    assert wire["data"]["initial_lots"][0]["reserved_qty"] == 0
    assert codec.loads_run_input(codec.dumps_run_input(run)) == run


def record_paths(value, path=()):
    if type(value) is dict:
        yield path, value
        for key, item in value.items():
            yield from record_paths(item, (*path, key))
    elif type(value) is list:
        for i, item in enumerate(value):
            yield from record_paths(item, (*path, i))


@pytest.mark.parametrize("path,key", [
    (path, key) for path, record in record_paths(document()) for key in record
])
def test_every_fixture_field_is_required(path, key):
    raw = document()
    record = raw
    for part in path:
        record = record[part]
    del record[key]
    with pytest.raises(codec.InputCodecError):
        codec.decode_run_input(raw)


@pytest.mark.parametrize("path", [path for path, _ in record_paths(document())])
def test_unknown_fields_never_silently_disappear(path):
    raw = document()
    record = raw
    for part in path:
        record = record[part]
    record["python_object"] = "arbitrary.module:factory"
    with pytest.raises(codec.InputCodecError, match="unknown fields"):
        codec.decode_run_input(raw)


@pytest.mark.parametrize("path,value", [
    (("schema_version",), "future"), (("timezone",), "UTC"),
    (("data", "initial_cash"), 10000), (("data", "initial_cash"), 10000.0),
    (("data", "initial_cash"), "NaN"), (("data", "initial_cash"), "Infinity"),
    (("data", "initial_cash"), "1_000"), (("data", "initial_cash"), " 1000 "),
    (("data", "commands", 0, "qty"), True), (("data", "commands", 0, "qty"), "400"),
    (("data", "commands", 0, "sequence"), 1.5), (("data", "commands", 0, "side"), "buy"),
    (("data", "commands", 0, "kind"), "python"), (("data", "requires_marks"), 1),
    (("data", "buckets", 0, "volume_shares"), True), (("data", "marks"), None),
    (("data", "calendar", "trading_dates", 0), "20260925"),
    (("data", "calendar", "trading_dates", 0), "2026-02-30"),
    (("data", "start_at"), "2026-09-28T09:28:00"),
    (("data", "start_at"), "2026-09-28T01:28:00+00:00"),
    (("data", "start_at"), "2026-09-28T09:28:00+09:00"),
    (("data", "start_at"), "2026-09-28T09:28:00+07:60"),
    (("data", "start_at"), "2026-09-28T09:28:00.1234567+08:00"),
    (("data", "start_at"), "2026-09-28T25:28:00+08:00"),
])
def test_wire_types_do_not_coerce(path, value):
    raw = document()
    set_path(raw, path, value)
    with pytest.raises(codec.InputCodecError):
        codec.decode_run_input(raw)


@pytest.mark.parametrize("text", [
    "{", "[]", "null", '{"schema_version":1,"schema_version":2}',
    '{"x":NaN}', '{"x":Infinity}', '{"x":1.0}',
    '\ufeff{}', '{"x":{"a":1,"a":2}}',
])
def test_strict_json(text):
    with pytest.raises(codec.InputCodecError):
        codec.loads_run_input(text)


def test_encoder_rejects_arbitrary_objects_and_unnamed_timezone():
    run = codec.load_run_input(FIXTURE)
    for bad in (
        object(), replace(run, initial_cash=1.0),
        replace(run, start_at=run.start_at.astimezone(timezone.utc)),
        replace(run, calendar=replace(run.calendar, company_actions=(object(),))),
    ):
        with pytest.raises(codec.InputCodecError):
            codec.dumps_run_input(bad)


@pytest.mark.parametrize("key", ["lot_id", "symbol", "acquire_date", "sellable_date", "qty", "lot_size", "reserved_qty"])
def test_initial_lot_fields_including_native_default_are_required(key):
    raw = document()
    lot = dict(lot_id="L", symbol="X", acquire_date="2026-09-25", sellable_date="2026-09-28",
               qty=200, lot_size=100, reserved_qty=0)
    del lot[key]
    raw["data"]["initial_lots"] = [lot]
    with pytest.raises(codec.InputCodecError, match="missing fields"):
        codec.decode_run_input(raw)
