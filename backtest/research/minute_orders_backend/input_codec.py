"""Versioned, pure-data RunInput JSON. No economic defaults or engine calls.

All record fields are required (including native dataclass defaults). Wire/type
errors stop decoding; economic/coverage validation remains with the S3 runner.
"""

from dataclasses import fields
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .types import (
    CalendarFacts, CancelOrder, CompletedBucket, FeeModelParams, InstrumentFacts,
    LotPosition, MarkEvent, MarkPrice, RunInput, SessionBucket, Side, SubmitOrder,
)

SCHEMA_VERSION = "minute_orders_run_input_v1"
TIMEZONE = "Asia/Shanghai"
_SHANGHAI = ZoneInfo(TIMEZONE)


class InputCodecError(ValueError):
    """Malformed or unsupported wire input; nothing has been run or written."""


def _error(path, message):
    raise InputCodecError(f"{path}: {message}")


def _string(value, path):
    if type(value) is not str or not value.strip():
        _error(path, "expected a nonempty string")
    return value


def _integer(value, path):
    if type(value) is not int:
        _error(path, "expected an integer (not bool, float or string)")
    return value


def _boolean(value, path):
    if type(value) is not bool:
        _error(path, "expected a boolean")
    return value


def _decimal(value, path):
    if type(value) is not str or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value,
    ):
        _error(path, "expected a finite Decimal string; no numeric coercion")
    try:
        result = Decimal(value)
    except ArithmeticError as error:
        _error(path, str(error))
    if not result.is_finite():
        _error(path, "expected a finite Decimal string")
    return result


def _date(value, path):
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        _error(path, "expected YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        _error(path, str(error))


def _timestamp(value, path):
    if type(value) is not str or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]", value,
    ):
        _error(path, "expected ISO timestamp with seconds and explicit numeric offset")
    try:
        fixed = datetime.fromisoformat(value)
        named = fixed.astimezone(_SHANGHAI)
    except (ValueError, OverflowError) as error:
        _error(path, str(error))
    if fixed.utcoffset() != named.utcoffset() or fixed.replace(tzinfo=None) != named.replace(tzinfo=None):
        _error(path, "timestamp offset/wall time disagrees with Asia/Shanghai")
    return named


def _side(value, path):
    if type(value) is not str or value not in ("BUY", "SELL"):
        _error(path, "expected BUY or SELL")
    return Side(value)


def _nullable(decoder):
    return lambda value, path: None if value is None else decoder(value, path)


def _array(decoder):
    def decode(value, path):
        if type(value) is not list:
            _error(path, "expected an explicit array")
        return tuple(decoder(item, f"{path}[{index}]") for index, item in enumerate(value))
    return decode


def _object(value, keys, path):
    if type(value) is not dict or any(type(key) is not str for key in value):
        _error(path, "expected an object with string keys")
    missing, unknown = set(keys) - value.keys(), value.keys() - set(keys)
    if missing or unknown:
        _error(path, f"missing fields={sorted(missing)}; unknown fields={sorted(unknown)}")


def _record(kind):
    def decode(value, path):
        schema = _RECORDS[kind]
        _object(value, schema, path)
        return kind(**{name: decoder(value[name], f"{path}.{name}")
                       for name, decoder in schema.items()})
    return decode


def _command(value, path):
    if type(value) is not dict or value.get("kind") not in ("submit", "cancel"):
        _error(path, "command kind must be submit or cancel")
    kind = SubmitOrder if value["kind"] == "submit" else CancelOrder
    return _record(kind)({key: item for key, item in value.items() if key != "kind"}, path)


def _pure_data(value, path):
    # Corporate actions have no supported economic schema in v0. Preserve their
    # data for native rejection/archival, never construct caller-selected objects.
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is list:
        return [_pure_data(item, f"{path}[{i}]") for i, item in enumerate(value)]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _pure_data(item, f"{path}.{key}") for key, item in value.items()}
    _error(path, "expected pure JSON data; fractional values must be Decimal strings")


_COMMAND_FIELDS = dict(command_id=_string, order_id=_string, available_at=_timestamp,
                       submitted_at=_timestamp, effective_at=_timestamp, sequence=_integer)
_RECORDS = {
    SubmitOrder: dict(_COMMAND_FIELDS, symbol=_string, side=_side, qty=_integer,
                      limit=_decimal, expires_at=_timestamp, order_type=_string),
    CancelOrder: _COMMAND_FIELDS,
    SessionBucket: dict(bucket_id=_string, start=_timestamp, end=_timestamp, session=_string),
    CalendarFacts: dict(trading_dates=_array(_date), session_buckets=_array(_record(SessionBucket)),
                        company_actions_covered=_boolean, company_actions=_array(_pure_data)),
    InstrumentFacts: dict(symbol=_string, trade_date=_date, board=_string, price_domain=_string,
                          tick_size=_decimal, lot_size=_integer, reference_price=_decimal,
                          limit_down=_decimal, limit_up=_decimal),
    CompletedBucket: dict(symbol=_string, bucket_id=_string, start=_timestamp, end=_timestamp,
                          close=_nullable(_decimal), volume_shares=_nullable(_integer),
                          missing=_boolean, halted=_boolean),
    LotPosition: dict(lot_id=_string, symbol=_string, acquire_date=_date, sellable_date=_date,
                      qty=_integer, lot_size=_integer, reserved_qty=_integer),
    FeeModelParams: dict(rate=_decimal, min_fee=_decimal, rounding=_string),
    MarkPrice: dict(symbol=_string, price=_decimal),
    MarkEvent: dict(mark_id=_string, event_time=_timestamp, available_at=_timestamp,
                    prices=_array(_record(MarkPrice)), price_domain=_string, source=_string),
    RunInput: dict(start_at=_timestamp, end_at=_timestamp, commands=_array(_command),
                   buckets=_array(_record(CompletedBucket)), calendar=_record(CalendarFacts),
                   instruments=_array(_record(InstrumentFacts)), initial_cash=_decimal,
                   initial_lots=_array(_record(LotPosition)), buy_fees=_record(FeeModelParams),
                   sell_fees=_record(FeeModelParams), participation_rate=_decimal,
                   marks=_array(_record(MarkEvent)), requires_marks=_boolean),
}


def decode_run_input(document: object) -> RunInput:
    """Decode one v1 envelope, requiring every field without economic coercion."""
    _object(document, ("schema_version", "timezone", "data"), "$")
    if document["schema_version"] != SCHEMA_VERSION:
        _error("$.schema_version", f"expected {SCHEMA_VERSION}")
    if document["timezone"] != TIMEZONE:
        _error("$.timezone", f"expected {TIMEZONE}")
    return _record(RunInput)(document["data"], "$.data")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _error("$", f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_number(value):
    _error("$", f"non-integer JSON number {value!r}; use a Decimal string")


def loads_run_input(text: str) -> RunInput:
    """Parse strict JSON (duplicate keys, floats, NaN/Infinity are rejected)."""
    try:
        document = json.loads(text, object_pairs_hook=_unique_object,
                              parse_float=_reject_number, parse_constant=_reject_number)
    except (ValueError, RecursionError) as error:
        raise InputCodecError(str(error)) from error
    return decode_run_input(document)


def load_run_input(path: str | Path) -> RunInput:
    return loads_run_input(Path(path).read_text(encoding="utf-8"))


def _encode(value):
    if type(value) in _RECORDS:
        result = {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
        if type(value) in (SubmitOrder, CancelOrder):
            result["kind"] = "submit" if type(value) is SubmitOrder else "cancel"
        return result
    if type(value) is Decimal:
        return str(value)
    if type(value) is datetime:
        if getattr(value.tzinfo, "key", getattr(value.tzinfo, "zone", None)) != TIMEZONE:
            _error("$", "timestamps must use the named Asia/Shanghai timezone")
        return value.isoformat()
    if type(value) is date:
        return value.isoformat()
    if type(value) is Side:
        return value.value
    if type(value) in (list, tuple):
        return [_encode(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _encode(item) for key, item in value.items()}
    if value is None or type(value) in (str, int, bool):
        return value
    _error("$", f"unsupported value type: {type(value).__name__}")


def encode_run_input(run_input: RunInput) -> dict:
    """Return the complete v1 data envelope, including explicit nulls/defaults."""
    if type(run_input) is not RunInput:
        _error("$", "expected RunInput")
    document = dict(schema_version=SCHEMA_VERSION, timezone=TIMEZONE, data=_encode(run_input))
    decode_run_input(document)  # Validate the wire shape, never run the engine.
    return document


def dumps_run_input(run_input: RunInput) -> str:
    return json.dumps(encode_run_input(run_input), ensure_ascii=False, allow_nan=False, indent=2) + "\n"
