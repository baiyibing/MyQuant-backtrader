"""Explicit, read-only B-L2-01 resolver -> RunInput mapping.

No default recipe, strategy, economics, host path, cache or runner integration.
The recipe and all sidecars are pinned before reading. See the contract note
section 7 and tests/test_minute_orders_source_loader.py for the v1 schema.
"""

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from oskh_data.symbol_format import is_canonical_symbol, to_canonical_symbol, to_partition_key

from .input_codec import _date, _timestamp, decode_run_input
from .source_provenance import (
    EVIDENCE_VERSION,
    FIXTURE_NOTICE,
    PROVENANCE_VERSION,
    SOURCE_MARK_PREFIX,
    TRANSFORM_VERSION,
    SourceContractError,
    SourceProvenance,
    attestation_scope,
    canonical,
    execution_identity,
    input_binding,
    nonempty,
    object_fields,
    read_pinned,
    require,
    require_unchanged,
    sha256,
    source_checks,
    strict_json,
)
from .types import RunInput, Side, SubmitOrder

RECIPE_VERSION = "minute_orders_source_recipe_v1"
_TZ = ZoneInfo("Asia/Shanghai")
_ROLES = ("calendar", "instruments", "status", "actions", "commands", "account", "attestation")
_CLAIMS = {
    "calendar": "complete_trading_calendar",
    "timing": "completed_bucket_available_at_end",
    "units": "incremental_volume_units_verified",
    "instruments": "ordinary_main_raw_facts_verified",
    "actions": "complete_no_company_actions",
    "status": "complete_halt_missing_grid",
    "marks": "raw_contemporaneous_grid",
}


@dataclass(frozen=True)
class LoadedSource:
    run_input: RunInput
    provenance: SourceProvenance


def _symbol(value):
    nonempty(value, "symbol")
    symbol = to_canonical_symbol(value)
    require(is_canonical_symbol(symbol), f"invalid symbol tag: {value!r}")
    return symbol


def _symbols(values):
    require(type(values) is list and bool(values), "explicit nonempty symbol universe required")
    result = [_symbol(v) for v in values]
    require(len(set(result)) == len(result), "duplicate normalized symbol")
    return sorted(result)


def _refs(values, store, where):
    require(type(values) is list and bool(values), f"{where}: proof refs required")
    require(all(type(v) is str and v in store.data for v in values),
            f"{where}: unknown proof source ref")
    require(all(store.specs[v]["schema"] == "bl2_proof_v1" for v in values),
            f"{where}: independently pinned bl2_proof_v1 material required")


def _time(value, spec, where):
    object_fields(spec, ("encoding", "timezone", "label"), where)
    require(spec["timezone"] == "Asia/Shanghai", f"{where}: unknown source timezone")
    encoding = spec["encoding"]
    try:
        if encoding == "iso_offset":
            return _timestamp(value, where)
        if encoding == "naive_shanghai":
            require(type(value) is str, f"{where}: explicit naive text required")
            result = datetime.fromisoformat(value)
            require(result.tzinfo is None, f"{where}: expected naive source timestamp")
            return result.replace(tzinfo=_TZ)
        if encoding == "datetime_shanghai":
            require(isinstance(value, datetime) and value.utcoffset() is not None,
                    f"{where}: expected aware source datetime")
            require(value.utcoffset() == timedelta(hours=8), f"{where}: unexpected source offset")
            return value.astimezone(_TZ)
        require(encoding in ("epoch_s", "epoch_ms", "epoch_us"), f"{where}: unknown timestamp encoding")
        require(type(value) is int, f"{where}: epoch must be an integer")
        scale = {"epoch_s": 1_000_000, "epoch_ms": 1000, "epoch_us": 1}[encoding]
        return (datetime(1970, 1, 1, tzinfo=UTC)
                + timedelta(microseconds=value * scale)).astimezone(_TZ)
    except (ValueError, OverflowError) as error:
        raise SourceContractError(f"{where}: invalid timestamp: {error}") from error


def _decimal(value, arrow_type, where):
    require(type(value) in (str, int, float, Decimal), f"{where}: invalid numeric source type")
    if type(value) is float:
        require(arrow_type == "double", f"{where}: only pinned double repr conversion is supported")
    text = repr(value) if type(value) is float else str(value)
    try:
        result = Decimal(text)
    except ArithmeticError as error:
        raise SourceContractError(f"{where}: invalid decimal {text}") from error
    require(result.is_finite(), f"{where}: nonfinite source value")
    return result, {"source_type": arrow_type, "original": text,
                    "decimal_text": str(result), "rule": "double_repr_or_exact_decimal_v1"}


class _Sources:
    def __init__(self, specs):
        from common.infra import data_root

        root = data_root.resolve_parquet_container()
        require(root.is_absolute() and root.is_dir(), f"configured source root missing: {root}")
        self.resolver = {"container": str(root.resolve()), "environment": {
            key: os.environ.get(key) for key in (
                "OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT",
                "OSKH_PERIOD_1M_ROOT", "OSKH_PERIOD_1D_ROOT",
            )}, "basis": "SOURCE" if os.environ.get("OSKH_SOURCE_PARQUET_ROOT") else "AUTHORITY_HINT"}
        self.data, self.specs, self.snapshots = {}, {}, []
        require(type(specs) is list and bool(specs), "source snapshots required")
        for spec in specs:
            object_fields(spec, ("id", "location", "format", "schema", "sha256"), "source")
            identity = nonempty(spec["id"], "source id")
            require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", identity)
                    and identity not in self.specs, "invalid/duplicate source id")
            loc = spec["location"]
            require(type(loc) is dict, f"{identity}: explicit source locator required")
            kind = loc.get("kind")
            if kind in ("minute", "daily"):
                object_fields(loc, ("kind", "symbol"), identity)
                period = "1m" if kind == "minute" else "1d"
                period_root = data_root.resolve_period_root(period)
                path = period_root / "dividend_type=none" / f"symbol={to_partition_key(_symbol(loc['symbol']))}" / "data.parquet"
                self.resolver[period] = str(period_root.resolve())
                require(spec["format"] == "parquet", f"{identity}: partitions must be parquet")
            elif kind == "loose":
                object_fields(loc, ("kind", "name"), identity)
                require(loc["name"] in ("ex_date_index.parquet", "adj_factor.parquet"),
                        "unsupported loose source ref")
                path = data_root.resolve_source_parquet(loc["name"])
                require(spec["format"] == "parquet", f"{identity}: loose source must be parquet")
            else:
                require(kind == "sidecar", f"{identity}: unknown source locator")
                object_fields(loc, ("kind", "path"), identity)
                path = Path(nonempty(loc["path"], identity))
            require(path.is_absolute(), f"{identity}: source ref must be absolute: {path}")
            path = path.resolve()
            raw = read_pinned(path, spec["sha256"])
            if spec["format"] == "parquet":
                import pyarrow as pa
                import pyarrow.parquet as pq

                try:
                    table = pq.ParquetFile(pa.BufferReader(raw)).read()
                except pa.ArrowException as error:
                    raise SourceContractError(f"{path}: invalid parquet schema/data: {error}") from error
                actual = {field.name: str(field.type) for field in table.schema}
                require(len(actual) == len(table.schema) and actual == spec["schema"],
                        f"{path}: parquet schema mismatch: {actual}")
                data = table.to_pylist()
                rows = len(data)
            else:
                require(spec["format"] == "json", f"{identity}: unsupported source format")
                document = strict_json(raw, str(path))
                object_fields(document, ("schema_version", "data"), str(path))
                require(type(spec["schema"]) is str and document["schema_version"] == spec["schema"],
                        f"{path}: JSON source schema mismatch")
                data = document["data"]
                rows = None
                if spec["schema"] == "bl2_proof_v1":
                    require(type(data) is dict and bool(data), f"{path}: empty proof material")
            self.data[identity], self.specs[identity] = data, spec
            self.snapshots.append({"id": identity, "ref": str(path), "sha256": spec["sha256"],
                                   "format": spec["format"], "schema": spec["schema"], "rows": rows})
        if self.resolver["basis"] == "AUTHORITY_HINT":
            marker = data_root.find_authority_marker()
            require(marker is not None, "authority marker disappeared")
            self.snapshots.append({"id": "authority_marker", "ref": str(marker.resolve()),
                                   "sha256": sha256(marker.read_bytes()), "format": "authority"})

    def role(self, identity, role):
        require(identity in self.data and self.specs[identity]["format"] == "json"
                and self.specs[identity]["schema"] == f"bl2_{role}_v1", f"missing/wrong {role} source schema")
        return self.data[identity]

    def table(self, identity, columns):
        require(identity in self.data and self.specs[identity]["format"] == "parquet",
                f"{identity}: explicit parquet table required")
        schema = self.specs[identity]["schema"]
        require(all(type(c) is str and c in schema for c in columns), f"{identity}: missing mapped column")
        return self.data[identity], schema


def _sessions(recipe):
    require(type(recipe["intervals"]) is list and bool(recipe["intervals"]), "continuous intervals required")
    result = []
    for interval in recipe["intervals"]:
        object_fields(interval, ("start", "end"), "interval")
        start, end = (_timestamp(interval[key], key) for key in ("start", "end"))
        require(start < end and start.second == start.microsecond == end.second == end.microsecond == 0,
                "invalid minute interval")
        require(start.date() == end.date(), "interval crosses trading date")
        while start < end:
            stop = start + timedelta(minutes=1)
            result.append({"bucket_id": "minute:" + start.isoformat(), "start": start.isoformat(),
                           "end": stop.isoformat(), "session": "continuous"})
            start = stop
    return result


def _attestation(recipe, store, symbols, first_day, last_day):
    att = store.role(recipe["roles"]["attestation"], "attestation")
    object_fields(att, ("issuer", "issued_at", "scope_hash", "source_kind", "symbols", "from_date", "through_date",
                        "complete", "claims", "limitations"), "attestation")
    nonempty(att["issuer"], "attestation issuer")
    issued = _timestamp(att["issued_at"], "attestation issued_at")
    require(issued <= _timestamp(recipe["registered_at"], "registered_at"),
            "attestation must precede recipe registration")
    require(att["source_kind"] == recipe["source_kind"], "attestation source kind mismatch")
    require(att["scope_hash"] == attestation_scope(recipe),
            "attestation scope hash mismatch: recipe/mappings/snapshots require fresh evidence")
    require(_symbols(att["symbols"]) == symbols and att["complete"] is True,
            "attestation symbol/complete coverage missing")
    require(_date(att["from_date"], "attestation from_date") <= first_day
            and _date(att["through_date"], "attestation through_date") >= last_day,
            "attestation economic coverage gap")
    require(type(att["limitations"]) is list and bool(att["limitations"]), "attestation limitations required")
    for item in att["limitations"]:
        nonempty(item, "attestation limitation")
    object_fields(att["claims"], _CLAIMS, "attestation claims")
    for name, conclusion in _CLAIMS.items():
        claim = att["claims"][name]
        object_fields(claim, ("conclusion", "proofs"), name)
        require(claim["conclusion"] == conclusion, f"{name}: unsupported/unknown attestation conclusion")
        _refs(claim["proofs"], store, name)
    return att


def _coverage(recipe, store, symbols, sessions):
    coverage = store.role(recipe["roles"]["status"], "status")
    object_fields(coverage, ("rows",), "status")
    require(type(coverage["rows"]) is list, "status rows required")
    result = {}
    for index, row in enumerate(coverage["rows"]):
        object_fields(row, ("symbol", "start", "end", "missing", "halted", "reason", "issuer", "proofs"), "status row")
        symbol = _symbol(row["symbol"])
        start, end = (_timestamp(row[key], key).isoformat() for key in ("start", "end"))
        key = symbol, start, end
        require(key not in result, "duplicate status coverage")
        require(type(row["missing"]) is bool and type(row["halted"]) is bool,
                "explicit missing/halted booleans required")
        nonempty(row["reason"], "status reason")
        nonempty(row["issuer"], "status issuer")
        _refs(row["proofs"], store, "status")
        result[key] = (row, index)
    expected = {(symbol, s["start"], s["end"]) for symbol in symbols for s in sessions}
    require(set(result) == expected, "halt/missing coverage grid mismatch")
    return result


def _bars(recipe, store, symbols, sessions, coverage):
    require(type(recipe["bars"]) is list, "bar mappings required")
    mapped, audit, exclusions, partition_symbols = {}, [], [], []
    for spec in recipe["bars"]:
        object_fields(spec, ("source", "columns", "time", "volume", "availability", "price_domain"), "bar mapping")
        sid, cols = spec["source"], spec["columns"]
        object_fields(cols, ("symbol", "time", "close", "volume"), "bar columns")
        rows, schema = store.table(sid, cols.values())
        location = store.specs[sid]["location"]
        require(location["kind"] == "minute", "bars must come from the raw minute resolver")
        symbol = _symbol(location["symbol"])
        partition_symbols.append(symbol)
        require(spec["availability"] == "bucket_end" and spec["price_domain"] == "raw",
                "late/unknown availability or mixed price domain")
        object_fields(spec["time"], ("encoding", "timezone", "label"), "bar time")
        label = spec["time"]["label"]
        require(label in ("START", "END"), "explicit START/END timestamp label required")
        volume = spec["volume"]
        object_fields(volume, ("kind", "unit", "shares_per_unit"), "volume")
        require(volume["kind"] == "incremental" and volume["unit"] in ("shares", "lots"),
                "cumulative/unknown volume units unsupported")
        factor = volume["shares_per_unit"]
        require(type(factor) is int and factor > 0
                and (volume["unit"] != "shares" or factor == 1), "invalid explicit volume conversion factor")
        seen = set()
        excluded_rows = []
        for index, row in enumerate(rows):
            require(_symbol(row[cols["symbol"]]) == symbol, f"{sid}#{index}: partition/symbol mismatch")
            stamp = _time(row[cols["time"]], spec["time"], f"{sid}#{index}")
            start = stamp if label == "START" else stamp - timedelta(minutes=1)
            end = start + timedelta(minutes=1)
            key = symbol, start.isoformat(), end.isoformat()
            require(key not in seen, f"{sid}: duplicate/conflicting source timestamp")
            seen.add(key)
            if key not in coverage:
                excluded_rows.append({"row": index, "original_time": str(row[cols["time"]]),
                                      "start": key[1], "end": key[2], "reason": "outside_declared_grid"})
                continue
            status, status_index = coverage[key]
            require(not status["missing"], f"{sid}#{index}: missing coverage conflicts with source row")
            close, price_record = _decimal(row[cols["close"]], schema[cols["close"]], f"{sid}#{index} close")
            quantity, qty_record = _decimal(row[cols["volume"]], schema[cols["volume"]], f"{sid}#{index} volume")
            numerator, denominator = quantity.as_integer_ratio()
            require(numerator >= 0 and (numerator * factor) % denominator == 0,
                    f"{sid}#{index}: volume is negative or not exact integer shares")
            shares = numerator * factor // denominator
            require(key not in mapped, "duplicate mapped source bucket")
            mapped[key] = (str(close), shares)
            audit.append({"source": sid, "row": index, "columns": cols,
                          "original_time": str(row[cols["time"]]), "symbol": symbol,
                          "start": key[1], "end": key[2], "available_at": key[2],
                          "price": price_record, "volume": qty_record,
                          "shares_per_unit": factor, "volume_shares": shares,
                          "status_row": status_index, "target": "buckets/" + symbol + "/" + key[1]})
        exclusions.append({"source": sid, "total_rows": len(rows), "excluded_count": len(excluded_rows),
                           "excluded_rows": excluded_rows})
    require(sorted(partition_symbols) == symbols, "exactly one minute partition per declared symbol required")
    result = []
    for session in sessions:
        for symbol in symbols:
            key = symbol, session["start"], session["end"]
            status, index = coverage[key]
            require(status["missing"] or key in mapped, f"unknown source gap: {key}; no implicit missing bucket")
            close, shares = (None, None) if status["missing"] else mapped[key]
            result.append({"symbol": symbol, "bucket_id": session["bucket_id"], "start": key[1], "end": key[2],
                           "close": close, "volume_shares": shares, "missing": status["missing"], "halted": status["halted"]})
            if status["missing"]:
                audit.append({"source": recipe["roles"]["status"], "row": index,
                              "target": "buckets/" + symbol + "/" + key[1], "mapping": "explicit_covered_missing"})
    return result, audit, exclusions


def _marks(recipe, store, symbols):
    require(type(recipe["mark_grid"]) is list and len(recipe["mark_grid"]) >= 2,
            "mark grid requires final and independent spot-check points")
    result, audit = [], []
    for point in recipe["mark_grid"]:
        object_fields(point, ("mark_id", "event_time", "prices"), "mark point")
        event = _timestamp(point["event_time"], "mark event_time")
        require(type(point["prices"]) is list, "explicit mark prices required")
        prices = []
        for ref in point["prices"]:
            object_fields(ref, ("symbol", "source", "row", "symbol_column", "time_column", "price_column", "time"), "mark ref")
            sid, index, symbol = ref["source"], ref["row"], _symbol(ref["symbol"])
            rows, schema = store.table(sid, (ref["symbol_column"], ref["time_column"], ref["price_column"]))
            if store.specs[sid]["location"]["kind"] == "minute":
                mapping = next((b for b in recipe["bars"] if b["source"] == sid), None)
                require(mapping is not None and ref["time"] == mapping["time"]
                        and ref["symbol_column"] == mapping["columns"]["symbol"]
                        and ref["time_column"] == mapping["columns"]["time"]
                        and ref["price_column"] == mapping["columns"]["close"],
                        "mark must preserve the minute source's time/close mapping")
            require(type(index) is int and 0 <= index < len(rows), "missing mark source row")
            row = rows[index]
            require(_symbol(row[ref["symbol_column"]]) == symbol, "mark source symbol mismatch")
            stamp = _time(row[ref["time_column"]], ref["time"], "mark source time")
            label = ref["time"]["label"]
            require(label in ("START", "END", "INSTANT"), "unknown mark time label")
            if label == "START":
                stamp += timedelta(minutes=1)
            require(stamp == event, "mark source time/availability gap; no last-value or synthetic fallback")
            price, conversion = _decimal(row[ref["price_column"]], schema[ref["price_column"]], "mark price")
            prices.append({"symbol": symbol, "price": str(price)})
            audit.append({"source": sid, "row": index, "columns": ref, "conversion": conversion,
                          "event_time": event.isoformat(), "available_at": event.isoformat(),
                          "target": "marks/" + point["mark_id"] + "/" + symbol})
        require(sorted(p["symbol"] for p in prices) == symbols, "mark universe coverage gap")
        result.append({"mark_id": point["mark_id"], "event_time": event.isoformat(),
                       "available_at": event.isoformat(), "prices": sorted(prices, key=lambda p: p["symbol"]),
                       "price_domain": "raw", "source": SOURCE_MARK_PREFIX + recipe["source_kind"] + "/" + point["mark_id"]})
    times = [m["event_time"] for m in result]
    require(len(set(times)) == len(times) and _timestamp(recipe["end_at"], "end_at").isoformat() in times,
            "mark grid must include the final run time and distinct spot-check times")
    return result, audit


def load_minute_orders_source(recipe_path, *, expected_sha256: str) -> LoadedSource:
    """Read a frozen v1 recipe and pinned files; return explicit input + evidence.

    Success means mapping validation only. In particular, synthetic_fixture
    never establishes lake PASS, host attestation, or comparison authorization.
    """
    path = Path(recipe_path)
    require(path.is_absolute(), "recipe ref must be absolute")
    path = path.resolve()
    raw = read_pinned(path, expected_sha256)
    recipe = strict_json(raw, str(path))
    object_fields(recipe, ("schema_version", "unit", "source_kind", "registered_at", "run_id", "parent",
                           "invocation", "symbols", "start_at", "end_at", "intervals", "mark_grid",
                           "orders_observed_sample", "sources", "roles", "bars", "implementation"), "recipe")
    require(recipe["schema_version"] == RECIPE_VERSION and recipe["unit"] == "B-L2-01", "unsupported recipe version/unit")
    require(recipe["source_kind"] in ("lake", "synthetic_fixture"), "unknown recipe source kind")
    object_fields(recipe["implementation"], ("code_sha", "python_version", "pyarrow_version", "transform_version"), "implementation")
    execution = execution_identity()
    require(recipe["implementation"] == {
        "code_sha": execution["code_sha"], "python_version": execution["python_version"],
        "pyarrow_version": execution["pyarrow_version"], "transform_version": TRANSFORM_VERSION,
    }, "pre-registered implementation/runtime version mismatch")
    require(type(recipe["orders_observed_sample"]) is bool, "sample observation disclosure required")
    _timestamp(recipe["registered_at"], "registered_at")
    require(type(recipe["run_id"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", recipe["run_id"]), "invalid recipe run_id")
    require(Path(nonempty(recipe["parent"], "parent")).is_absolute(), "explicit absolute parent required")
    require(type(recipe["invocation"]) is list and bool(recipe["invocation"]), "exact invocation required")
    for arg in recipe["invocation"]:
        nonempty(arg, "invocation")
    object_fields(recipe["roles"], _ROLES, "source roles")
    require(len(set(recipe["roles"].values())) == len(_ROLES), "source roles must be independent")
    symbols = _symbols(recipe["symbols"])
    start, end = (_timestamp(recipe[k], k) for k in ("start_at", "end_at"))
    require(start < end, "invalid run window")
    store = _Sources(recipe["sources"])
    output_parent = Path(recipe["parent"]).resolve()
    for key in ("container", "1m", "1d"):
        if key in store.resolver:
            require(not output_parent.is_relative_to(Path(store.resolver[key])),
                    "artifact parent must be outside read-only source roots")
    calendar = store.role(recipe["roles"]["calendar"], "calendar")
    object_fields(calendar, ("trading_dates",), "calendar")
    account = store.role(recipe["roles"]["account"], "account")
    object_fields(account, ("origin", "initial_cash", "initial_lots", "buy_fees", "sell_fees", "participation_rate", "requires_marks"), "account")
    require(account["origin"] == "synthetic_account" and account["requires_marks"] is True,
            "B-L2-01 requires explicit synthetic account and marks")
    require(type(account["initial_lots"]) is list, "initial lots required")
    for lot in account["initial_lots"]:
        object_fields(lot, ("lot_id", "symbol", "qty", "acquire_date", "sellable_date", "lot_size", "reserved_qty"), "initial lot")
        lot["symbol"] = _symbol(lot["symbol"])
        require(lot["symbol"] in symbols and type(lot["reserved_qty"]) is int and lot["reserved_qty"] == 0,
                "initial lots must be in universe with zero reservation")
    first_day = min([start.date()] + [_date(lot["acquire_date"], "acquire_date") for lot in account["initial_lots"]])
    attestation = _attestation(recipe, store, symbols, first_day, end.date())
    if recipe["source_kind"] == "lake":
        require(not execution["code_dirty"], "lake evidence requires a clean pinned implementation")
    actions = store.role(recipe["roles"]["actions"], "actions")
    object_fields(actions, ("symbols", "from_date", "through_date", "complete", "events", "proofs"), "actions")
    require(_symbols(actions["symbols"]) == symbols and actions["complete"] is True
            and actions["events"] == [] and type(actions["events"]) is list,
            "company actions absent/unsupported or incomplete coverage")
    require(_date(actions["from_date"], "actions from_date") <= first_day
            and _date(actions["through_date"], "actions through_date") >= end.date(), "company actions coverage gap")
    _refs(actions["proofs"], store, "company actions")
    sessions = _sessions(recipe)
    coverage = _coverage(recipe, store, symbols, sessions)
    buckets, bar_audit, exclusions = _bars(recipe, store, symbols, sessions, coverage)
    marks, mark_audit = _marks(recipe, store, symbols)
    orders = store.role(recipe["roles"]["commands"], "commands")
    object_fields(orders, ("origin", "commands"), "commands")
    require(orders["origin"] == "designed_limit_batch" and type(orders["commands"]) is list
            and bool(orders["commands"]), "independently frozen synthetic LIMIT commands required")
    for command in orders["commands"]:
        require(type(command) is dict, "explicit command object required")
        if command.get("kind") == "submit":
            command["symbol"] = _symbol(command["symbol"])
    facts_source = store.role(recipe["roles"]["instruments"], "instruments")
    object_fields(facts_source, ("rows",), "instrument source")
    instruments, facts_audit = [], []
    require(type(facts_source["rows"]) is list, "instrument rows required")
    for index, row in enumerate(facts_source["rows"]):
        object_fields(row, ("facts", "effective_from", "effective_through", "available_at", "ordinary_listing", "origin", "proofs", "derivation"), "instrument row")
        facts = row["facts"]
        object_fields(facts, ("symbol", "trade_date", "board", "price_domain", "tick_size", "lot_size",
                              "reference_price", "limit_down", "limit_up"), "instrument facts")
        facts["symbol"] = _symbol(facts["symbol"])
        day = _date(facts["trade_date"], "trade_date")
        require(row["ordinary_listing"] is True and facts["symbol"] in symbols,
                "unsupported listing or instrument symbol")
        require(_date(row["effective_from"], "effective_from") <= day
                <= _date(row["effective_through"], "effective_through"), "instrument effective-date coverage gap")
        available = _timestamp(row["available_at"], "instrument available_at")
        uses = [b["start"] for b in buckets if b["symbol"] == facts["symbol"]]
        uses += [c["submitted_at"] for c in orders["commands"] if c.get("symbol") == facts["symbol"]]
        uses += [m["event_time"] for m in marks]
        if any(lot["symbol"] == facts["symbol"] for lot in account["initial_lots"]):
            uses.append(start.isoformat())
        require(all(available <= _timestamp(t, "fact use") for t in uses
                    if _timestamp(t, "fact use").date() == day), "instrument facts unavailable at use")
        _refs(row["proofs"], store, "instrument")
        require(row["origin"] in ("source_fact", "approved_derivation"), "unknown instrument fact origin")
        if row["origin"] == "approved_derivation":
            object_fields(row["derivation"], ("inputs", "approved_rule_version", "independent_verification"), "derivation")
            require(type(row["derivation"]["inputs"]) is list and bool(row["derivation"]["inputs"])
                    and all(s in store.data for s in row["derivation"]["inputs"]), "derived facts need pinned inputs")
            nonempty(row["derivation"]["approved_rule_version"], "approved rule")
            _refs(row["derivation"]["independent_verification"], store, "derivation verification")
        else:
            require(row["derivation"] == {}, "source facts cannot hide a derivation")
        instruments.append(facts)
        facts_audit.append({"source": recipe["roles"]["instruments"], "row": index,
                            "target": "instruments/" + facts["symbol"] + "/" + facts["trade_date"]})
    data = {"start_at": recipe["start_at"], "end_at": recipe["end_at"], "commands": orders["commands"],
            "buckets": buckets, "calendar": {**calendar, "session_buckets": sessions,
                                               "company_actions_covered": True, "company_actions": []},
            "instruments": instruments, "marks": marks,
            **{key: value for key, value in account.items() if key != "origin"}}
    run = decode_run_input({"schema_version": "minute_orders_run_input_v1", "timezone": "Asia/Shanghai", "data": data})
    # Reuse existing validation only. No engine event is run, no rule is changed.
    from .broker import BrokerCore

    BrokerCore(run)
    require(sorted({f.symbol for f in run.instruments}) == symbols, "instrument universe coverage gap")
    dates = run.calendar.trading_dates
    for bucket in run.buckets:
        if any(isinstance(c, SubmitOrder) and c.side is Side.BUY and c.symbol == bucket.symbol for c in run.commands):
            require(dates.index(bucket.start.date()) + 1 < len(dates), "calendar lacks next possible BUY trading date")
    for command in run.commands:
        require(start <= command.available_at <= command.submitted_at <= command.effective_at <= end,
                "command availability/effective time outside recipe window")
        if isinstance(command, SubmitOrder):
            require(command.expires_at <= end, "command expiry outside recipe window")
    recipe_ref = {"ref": str(path), "sha256": expected_sha256, "run_id": recipe["run_id"],
                  "parent": str(Path(recipe["parent"]).resolve()), "registered_at": recipe["registered_at"],
                  "invocation": recipe["invocation"], "orders_observed_sample": recipe["orders_observed_sample"]}
    doc = {"schema_version": PROVENANCE_VERSION, "evidence_version": EVIDENCE_VERSION, "unit": "B-L2-01",
           "source_kind": recipe["source_kind"],
           "notice": FIXTURE_NOTICE if recipe["source_kind"] == "synthetic_fixture" else
           "真实行情驱动的合成订单研究; source validation is not host certification or item-4 live PASS.",
           "recipe": recipe_ref, "resolver": store.resolver, "snapshots": store.snapshots,
           "attestation": attestation, "execution": execution, "binding": input_binding(run),
           "transform": {"version": TRANSFORM_VERSION, "symbol_rule": "oskh_data.symbol_format",
                         "sort_rule": "bucket(start,symbol); mark prices(symbol)",
                         "bars": bar_audit, "excluded": exclusions, "marks": mark_audit,
                         "instruments": facts_audit, "role_sources": recipe["roles"],
                         "recipe_targets": ["start_at", "end_at", "calendar/session_buckets", "marks/grid"],
                         "account_targets": [key for key in account if key != "origin"]},
           "source_checks_at_load": []}
    provisional = SourceProvenance(canonical(doc), sha256(canonical(doc)))
    checks = source_checks(provisional)
    require_unchanged(checks)
    doc["source_checks_at_load"] = checks
    payload = canonical(doc)
    return LoadedSource(run, SourceProvenance(payload, sha256(payload)))
