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
_BOUND_SUBJECTS = {"units", "instruments", "status"}
_FACT_PACKAGES = ("bl2_instruments_v1", "bl2_status_v1")
_RATIO_GO_SHA256 = "bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe"
_WALL_SHANGHAI_ENCODING = "epoch_ms_wall_shanghai_as_utc"
# attestation_packages/sources/time_encoding_approval.json: exact saved HOST
# approval, including source/column/window and material hashes.
# Synthetic tests replace only this trust anchor with explicitly fabricated bytes.
_TIME_ENCODING_APPROVAL_SHA256 = "8fedbb2833675a18c9d434f0c38592b2fd2f74e24cb08a283aeeeecb0b8f71b7"


def _units_evidence(data, row, evidence, store, where):
    """Check saved declarations, or the one explicitly scoped Human exception.

    This validates pinned assertions, not vendor authenticity or a lake run.
    Raw CSV reconciliation belongs to the offline evidence remapper.
    """
    require(type(evidence) is dict, f"{where}: structured units evidence required")
    binding = row["binding"]
    declaration = {k: binding[k] for k in ("column", "kind", "unit", "shares_per_unit")}
    if row["basis"] == "source_declaration":
        require(evidence.get("basis") == "source_declaration"
                and canonical(evidence.get("unit_declaration")) == canonical(declaration),
                f"{where}: source_declaration requires an explicit matching unit declaration")
        return
    require(evidence.get("basis") == "cross_source_ratio"
            and evidence.get("unit_declaration") is None
            and store.specs[row["source"]]["schema"] == "bl2_cross_source_ratio_v1",
            f"{where}: cross_source_ratio cannot masquerade as source_declaration")
    require(_symbols(data["filter"]["symbols"]) == ["603196.SH"]
            and data["filter"]["from_date"] == "2025-10-23"
            and data["filter"]["through_date"] == "2025-11-04"
            and _symbol(store.specs[binding["source"]]["location"]["symbol"]) == "603196.SH"
            and declaration == {"column": "volume", "kind": "incremental", "unit": "lots", "shares_per_unit": 100},
            f"{where}: cross_source_ratio outside Human GO probe scope")
    go_ref = evidence.get("human_go")
    require(type(go_ref) is str and go_ref in data["source_refs"]
            and store.specs[go_ref]["schema"] == "bl2_human_go_v1",
            f"{where}: cross_source_ratio requires pinned Human GO marker")
    go = store.data[go_ref]
    require(type(go) is dict and type(go.get("rows")) is list and len(go["rows"]) == 1,
            f"{where}: invalid Human GO marker")
    marker = go["rows"][0]
    require(type(marker) is dict and canonical(marker) == canonical({
        "approval_id": "b_l2_remap_r4_20260930",
        "source_document_sha256": _RATIO_GO_SHA256,
        "cue": "人裁：①量单位接受直接对账（basis=cross_source_ratio），然后 remap",
        "basis": "cross_source_ratio", "symbols": ["603196.SH"],
        "from_date": "2025-10-23", "through_date": "2025-11-04",
        "unit": "手", "shares_per_unit": 100, "kind": "incremental",
        "scope": "docs/fixtures remap only", "r4_authorized": False,
    }), f"{where}: Human GO marker mismatch")
    refs = evidence.get("evidence_refs")
    object_fields(refs, ("daqmt_1m", "daqmt_1d", "ths_daily", "ratio_table"), where + " ratio evidence")
    require(all(type(ref) is str and ref in data["source_refs"]
                and store.specs[ref]["schema"] == "bl2_raw_excerpt_v1" for ref in refs.values()),
            f"{where}: ratio evidence needs four pinned raw excerpts")
    require(len({store.specs[ref]["sha256"] for ref in refs.values()}) == 4,
            f"{where}: ratio evidence sources must be distinct")


def _binding_key(subject, binding):
    """Identity of a saved assertion, separate from its asserted values."""
    require(type(binding) is dict, f"{subject}: structured proof binding required")
    if subject == "units":
        object_fields(binding, ("source", "column", "kind", "unit", "shares_per_unit"), "units binding")
        return nonempty(binding["source"], "units source"), nonempty(binding["column"], "units column")
    if subject == "status":
        object_fields(binding, ("symbol", "start", "end", "missing", "halted", "reason", "issuer"), "status binding")
        return (_symbol(binding["symbol"]), _timestamp(binding["start"], "status binding start").isoformat(),
                _timestamp(binding["end"], "status binding end").isoformat())
    object_fields(binding, ("facts", "effective_from", "effective_through", "available_at",
                           "ordinary_listing", "origin", "derivation"), "instrument binding")
    facts = binding["facts"]
    object_fields(facts, ("symbol", "trade_date", "board", "price_domain", "tick_size", "lot_size",
                          "reference_price", "limit_down", "limit_up"), "instrument binding facts")
    return _symbol(facts["symbol"]), _date(facts["trade_date"], "instrument binding date")


def _instrument_binding(row):
    return {**{k: v for k, v in row.items() if k not in ("proofs", "derivation")},
            "derivation": {k: v for k, v in row["derivation"].items() if k != "independent_verification"}}


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


def _proof(data, store, identity):
    """Require saved, scoped evidence; authenticity remains a host review task."""
    where = f"{identity}: proof"
    object_fields(data, ("issuer", "subject", "source_refs", "filter", "result", "limitations"), where)
    nonempty(data["issuer"], where + " issuer")
    require(type(data["subject"]) is str and data["subject"] in _CLAIMS,
            f"{where}: unknown subject")
    refs = data["source_refs"]
    require(type(refs) is list and bool(refs)
            and all(type(ref) is str and ref in store.data for ref in refs),
            f"{where}: pinned source refs required")
    require(all(store.specs[ref]["schema"] not in ("bl2_proof_v1", "bl2_attestation_v1")
                for ref in refs), f"{where}: proof/attestation cannot be its own evidence")
    if data["subject"] in _BOUND_SUBJECTS:
        require(all(store.specs[ref]["schema"] not in _FACT_PACKAGES for ref in refs),
                f"{where}: fact packages cannot be their own evidence")
    scope = data["filter"]
    object_fields(scope, ("symbols", "from_date", "through_date", "predicate"), where + " filter")
    _symbols(scope["symbols"])
    require(_date(scope["from_date"], where) <= _date(scope["through_date"], where),
            f"{where}: reversed filter dates")
    nonempty(scope["predicate"], where + " filter predicate")
    result = data["result"]
    object_fields(result, ("complete", "summary", "rows"), where + " result")
    require(result["complete"] is True, f"{where}: complete saved result required")
    nonempty(result["summary"], where + " result summary")
    require(type(result["rows"]) is list, f"{where}: saved result rows required")
    bindings = {}
    if data["subject"] == "actions":
        require(result["rows"] == [], f"{where}: company actions must have an empty saved filter result")
    else:
        require(bool(result["rows"]), f"{where}: saved observations required")
        for index, row in enumerate(result["rows"]):
            bound = data["subject"] in _BOUND_SUBJECTS
            object_fields(row, ("source", "row", "observation", *(("basis", "binding") if bound else ())),
                          where + " observation")
            require(type(row["source"]) is str and row["source"] in refs
                    and type(row["row"]) is int and row["row"] >= 0,
                    f"{where}: observation needs a source ref and row index")
            nonempty(row["observation"], where + " observation")
            source = store.data[row["source"]]
            observations = source.get("rows") if type(source) is dict else source
            require(type(observations) is list and row["row"] < len(observations),
                    f"{where}: observation row outside pinned source rows")
            if bound:
                allowed = {"units": ("source_declaration", "cross_source_ratio"), "status": ("explicit_status",),
                           "instruments": ("source_fact", "approved_derivation")}[data["subject"]]
                require(row["basis"] in allowed, f"{where}: unsupported evidence basis; heuristics are not attestation")
                key = _binding_key(data["subject"], row["binding"])
                require(key not in bindings, f"{where}: duplicate/conflicting proof binding")
                bindings[key] = (index, row)
                if data["subject"] == "units":
                    binding = row["binding"]
                    require(binding["source"] in store.specs
                            and store.specs[binding["source"]]["location"]["kind"] == "minute"
                            and binding["column"] in store.specs[binding["source"]]["schema"],
                            f"{where}: units binding needs a pinned minute source/column")
                    require(binding["kind"] == "incremental" and binding["unit"] in ("shares", "lots")
                            and type(binding["shares_per_unit"]) is int and binding["shares_per_unit"] > 0
                            and (binding["unit"] != "shares" or binding["shares_per_unit"] == 1),
                            f"{where}: invalid units binding factor")
                    bar_hashes = {spec["sha256"] for spec in store.specs.values()
                                  if spec["location"]["kind"] in ("minute", "daily")}
                    require(all(store.specs[ref]["location"]["kind"] not in ("minute", "daily")
                                and store.specs[ref]["sha256"] not in bar_hashes for ref in refs),
                            f"{where}: units need independent source declaration, not bar heuristics")
                    _units_evidence(data, row, observations[row["row"]], store, where)
    require(type(data["limitations"]) is list and bool(data["limitations"]),
            f"{where}: limitations required")
    for limitation in data["limitations"]:
        nonempty(limitation, where + " limitation")
    return bindings


def _refs(values, store, where, *, subject=None, symbols=None, from_date=None, through_date=None):
    require(type(values) is list and bool(values), f"{where}: proof refs required")
    require(all(type(v) is str and v in store.data for v in values),
            f"{where}: unknown proof source ref")
    require(all(store.specs[v]["schema"] == "bl2_proof_v1" for v in values),
            f"{where}: independently pinned bl2_proof_v1 material required")
    require(all(store.data[v]["subject"] == (subject or where) for v in values),
            f"{where}: proof subject mismatch")
    if symbols is not None:
        for value in values:
            scope = store.data[value]["filter"]
            require(set(symbols) <= set(_symbols(scope["symbols"]))
                    and _date(scope["from_date"], where) <= from_date
                    and _date(scope["through_date"], where) >= through_date,
                    f"{where}: proof scope coverage gap")


def _bound_refs(values, store, subject, binding, basis, **scope):
    """Require exact saved assertions; never infer facts from narrative text."""
    _refs(values, store, subject, **scope)
    key = _binding_key(subject, binding)
    matches = []
    for ref in values:
        saved = store.proof_bindings[ref].get(key)
        if saved is not None:
            index, observation = saved
            require(observation["basis"] in (basis if isinstance(basis, tuple) else (basis,))
                    and canonical(observation["binding"]) == canonical(binding),
                    f"{subject}: proof binding mismatch")
            matches.append({"proof": ref, "row": index, "source": observation["source"],
                            "source_row": observation["row"]})
    require(bool(matches), f"{subject}: matching proof binding required")
    return matches


def _time_encoding_refs(recipe, store, sid, column, time_spec):
    """Require the one approved wall encoding binding through the timing claim.

    This is deliberately narrower than a general timezone override. An approval
    for another source snapshot/window requires a new named implementation GO.
    The pure _time decoder is called only after this gate by bars and marks.
    """
    object_fields(time_spec, ("encoding", "timezone", "label"), "time encoding")
    if time_spec["encoding"] != _WALL_SHANGHAI_ENCODING:
        return []
    where = "time encoding"
    source = store.specs[sid]
    require(source["location"]["kind"] == "minute" and source["schema"].get(column) == "int64",
            f"{where}: approved int64 minute source required")
    first, last = (_timestamp(recipe[k], k).date() for k in ("start_at", "end_at"))
    symbol = _symbol(source["location"]["symbol"])
    refs = store.role(recipe["roles"]["attestation"], "attestation")["claims"]["timing"]["proofs"]
    _refs(refs, store, where, subject="timing", symbols=[symbol], from_date=first, through_date=last)
    matches = []
    for ref in refs:
        proof = store.data[ref]
        for index, observation in enumerate(proof["result"]["rows"]):
            evidence_id = observation["source"]
            evidence_spec = store.specs[evidence_id]
            if evidence_spec["schema"] != "bl2_time_encoding_approval_v1":
                continue
            require(evidence_spec["sha256"] == _TIME_ENCODING_APPROVAL_SHA256,
                    f"{where}: HOST approval pin mismatch")
            evidence = store.data[evidence_id]["rows"][observation["row"]]
            binding = evidence["binding"]
            require(canonical({k: v for k, v in binding.items() if k not in ("from_date", "through_date")})
                    == canonical({"source": sid, "source_sha256": source["sha256"], "column": column,
                                  "source_type": "int64", "symbol": symbol, **time_spec,
                                  "availability": "bucket_end"}),
                    f"{where}: source/column/mapping binding mismatch")
            require(_date(binding["from_date"], where) <= first <= last
                    <= _date(binding["through_date"], where), f"{where}: approval window coverage gap")
            for material, pin in evidence["evidence_refs"].items():
                require(material in proof["source_refs"] and store.specs[material]["sha256"] == pin,
                        f"{where}: pinned approval material missing or changed: {material}")
            require(evidence["r4_authorized"] is False, f"{where}: R4 authorization is separate")
            matches.append({"proof": ref, "row": index, "source": evidence_id,
                            "source_row": observation["row"], "approval_id": evidence["approval_id"]})
    require(bool(matches), f"{where}: matching pinned HOST approval binding required")
    return matches


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
        if encoding == _WALL_SHANGHAI_ENCODING:
            require(type(value) is int, f"{where}: wall epoch ms must be an integer")
            utc_wall = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=value * 1000)
            return utc_wall.replace(tzinfo=None).replace(tzinfo=_TZ)
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
        self._minute_bindings = {}
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
            self.data[identity], self.specs[identity] = data, spec
            self.snapshots.append({"id": identity, "ref": str(path), "sha256": spec["sha256"],
                                   "format": spec["format"], "schema": spec["schema"], "rows": rows})
        # Index only validated assertions from this pinned snapshot. No cross-load cache.
        self.proof_bindings = {}
        for identity, spec in self.specs.items():
            if spec["schema"] == "bl2_proof_v1":
                self.proof_bindings[identity] = _proof(self.data[identity], self, identity)
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

    def minute_table(self, identity, symbol_column, columns):
        """Bind identity to the pinned locator; never add a physical column.

        Check identity on *all* rows, including excluded/mark-only rows. An
        existing physical symbol column remains evidence even in partition mode.
        """
        partition_only = type(symbol_column) is dict
        if partition_only:
            object_fields(symbol_column, ("kind",), "partition symbol selector")
            require(symbol_column["kind"] == "partition", "unknown symbol selector")
        else:
            nonempty(symbol_column, "symbol column")
        rows, schema = self.table(identity, [*columns, *([] if partition_only else [symbol_column])])
        key = identity, None if partition_only else symbol_column
        if key in self._minute_bindings:
            symbol, binding = self._minute_bindings[key]
            return rows, schema, symbol, binding
        location = self.specs[identity]["location"]
        require(location["kind"] == "minute", "bars must come from the raw minute resolver")
        symbol = _symbol(location["symbol"])
        checked_columns = set() if partition_only else {symbol_column}
        if "symbol" in schema:
            checked_columns.add("symbol")
        for index, row in enumerate(rows):
            for column in sorted(checked_columns):
                require(_symbol(row[column]) == symbol,
                        f"{identity}#{index}: partition/symbol mismatch in {column}")
        binding = {"kind": "partition" if partition_only else "column", "location": location,
                   "partition_key": to_partition_key(symbol), "checked_columns": sorted(checked_columns)}
        if not partition_only:
            binding["column"] = symbol_column
        # Reuse only within this pinned in-memory snapshot, never across loads.
        self._minute_bindings[key] = symbol, binding
        return rows, schema, symbol, binding


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
        scope = ({"symbols": symbols, "from_date": _timestamp(recipe["start_at"], "start_at").date(),
                  "through_date": last_day} if name in ("status", "instruments") else {})
        _refs(claim["proofs"], store, name, **scope)
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
        _refs(row["proofs"], store, "status", symbols=[symbol],
              from_date=_timestamp(start, "status start").date(),
              through_date=_timestamp(end, "status end").date())
        binding = {**{k: v for k, v in row.items() if k != "proofs"},
                   "symbol": symbol, "start": start, "end": end}
        claim = store.role(recipe["roles"]["attestation"], "attestation")["claims"]["status"]
        require(set(row["proofs"]) <= set(claim["proofs"]), "status: row proofs must be registered in claim")
        _bound_refs(claim["proofs"], store, "status", binding, "explicit_status")
        _bound_refs(row["proofs"], store, "status", binding, "explicit_status")
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
        rows, schema, symbol, binding = store.minute_table(
            sid, cols["symbol"], [cols[key] for key in ("time", "close", "volume")])
        partition_symbols.append(symbol)
        require(spec["availability"] == "bucket_end" and spec["price_domain"] == "raw",
                "late/unknown availability or mixed price domain")
        object_fields(spec["time"], ("encoding", "timezone", "label"), "bar time")
        label = spec["time"]["label"]
        require(label in ("START", "END"), "explicit START/END timestamp label required")
        time_proofs = _time_encoding_refs(recipe, store, sid, cols["time"], spec["time"])
        volume = spec["volume"]
        object_fields(volume, ("kind", "unit", "shares_per_unit"), "volume")
        require(volume["kind"] == "incremental" and volume["unit"] in ("shares", "lots"),
                "cumulative/unknown volume units unsupported")
        factor = volume["shares_per_unit"]
        require(type(factor) is int and factor > 0
                and (volume["unit"] != "shares" or factor == 1), "invalid explicit volume conversion factor")
        claim = store.role(recipe["roles"]["attestation"], "attestation")["claims"]["units"]
        volume_proofs = _bound_refs(
            claim["proofs"], store, "units", {"source": sid, "column": cols["volume"], **volume},
            ("source_declaration", "cross_source_ratio"), symbols=[symbol],
            from_date=_timestamp(recipe["start_at"], "start_at").date(),
            through_date=_timestamp(recipe["end_at"], "end_at").date())
        seen = set()
        excluded_rows = []
        for index, row in enumerate(rows):
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
            audit.append({"source": sid, "row": index, "columns": cols, "symbol_binding": binding,
                          "original_time": str(row[cols["time"]]), "symbol": symbol,
                          "time": spec["time"], "time_source_type": schema[cols["time"]],
                          "time_proofs": time_proofs,
                          "start": key[1], "end": key[2], "available_at": key[2],
                          "price": price_record, "volume": qty_record,
                          "shares_per_unit": factor, "volume_shares": shares, "volume_proofs": volume_proofs,
                          "status_row": status_index, "target": "buckets/" + symbol + "/" + key[1]})
        exclusions.append({"source": sid, "total_rows": len(rows), "excluded_count": len(excluded_rows),
                           "time": spec["time"], "time_source_type": schema[cols["time"]],
                           "time_proofs": time_proofs,
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
            require(sid in store.specs, f"{sid}: unknown mark source")
            binding = None
            if store.specs[sid]["location"]["kind"] == "minute":
                mapping = next((b for b in recipe["bars"] if b["source"] == sid), None)
                require(mapping is not None and ref["time"] == mapping["time"]
                        and ref["symbol_column"] == mapping["columns"]["symbol"]
                        and ref["time_column"] == mapping["columns"]["time"]
                        and ref["price_column"] == mapping["columns"]["close"],
                        "mark must preserve the minute source's time/close mapping")
                rows, schema, partition_symbol, binding = store.minute_table(
                    sid, ref["symbol_column"], [ref["time_column"], ref["price_column"]])
                require(symbol == partition_symbol, "mark source symbol mismatch")
            else:
                rows, schema = store.table(sid, (ref["symbol_column"], ref["time_column"], ref["price_column"]))
            require(type(index) is int and 0 <= index < len(rows), "missing mark source row")
            row = rows[index]
            if binding is None:
                require(_symbol(row[ref["symbol_column"]]) == symbol, "mark source symbol mismatch")
            time_proofs = _time_encoding_refs(recipe, store, sid, ref["time_column"], ref["time"])
            stamp = _time(row[ref["time_column"]], ref["time"], "mark source time")
            label = ref["time"]["label"]
            require(label in ("START", "END", "INSTANT"), "unknown mark time label")
            if label == "START":
                stamp += timedelta(minutes=1)
            require(stamp == event, "mark source time/availability gap; no last-value or synthetic fallback")
            price, conversion = _decimal(row[ref["price_column"]], schema[ref["price_column"]], "mark price")
            prices.append({"symbol": symbol, "price": str(price)})
            audit.append({"source": sid, "row": index, "columns": ref, "conversion": conversion,
                          "symbol_binding": binding,
                          "original_time": str(row[ref["time_column"]]),
                          "time_source_type": schema[ref["time_column"]], "time_proofs": time_proofs,
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
    _refs(actions["proofs"], store, "company actions", subject="actions")
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
        _refs(row["proofs"], store, "instrument", subject="instruments", symbols=[facts["symbol"]],
              from_date=day, through_date=day)
        require(row["origin"] in ("source_fact", "approved_derivation"), "unknown instrument fact origin")
        if row["origin"] == "approved_derivation":
            object_fields(row["derivation"], ("inputs", "approved_rule_version", "independent_verification"), "derivation")
            require(type(row["derivation"]["inputs"]) is list and bool(row["derivation"]["inputs"])
                    and all(type(s) is str and s in store.data
                            and store.specs[s]["schema"] not in ("bl2_proof_v1", "bl2_attestation_v1")
                            and store.specs[s]["schema"] not in _FACT_PACKAGES
                            for s in row["derivation"]["inputs"]), "derived facts need pinned inputs")
            nonempty(row["derivation"]["approved_rule_version"], "approved rule")
            _refs(row["derivation"]["independent_verification"], store, "derivation verification",
                  subject="instruments", symbols=[facts["symbol"]], from_date=day, through_date=day)
            verification = row["derivation"]["independent_verification"]
            require(not set(verification) & set(row["proofs"]), "derivation verification must use independent proofs")
            require(not {store.data[p]["issuer"] for p in verification}
                    & {store.data[p]["issuer"] for p in row["proofs"]},
                    "derivation verification must use independent issuers")
            for proof in [*row["proofs"], *verification]:
                require(set(row["derivation"]["inputs"]) <= set(store.data[proof]["source_refs"]),
                        "derivation proof must bind all pinned inputs")
        else:
            require(row["derivation"] == {}, "source facts cannot hide a derivation")
            verification = []
        claim = attestation["claims"]["instruments"]
        require(set([*row["proofs"], *verification]) <= set(claim["proofs"]),
                "instruments: row/verification proofs must be registered in claim")
        binding = _instrument_binding(row)
        for refs in (claim["proofs"], row["proofs"], *([verification] if verification else [])):
            _bound_refs(refs, store, "instruments", binding, row["origin"])
        instruments.append(facts)
        facts_audit.append({"source": recipe["roles"]["instruments"], "row": index,
                            "proofs": row["proofs"], "origin": row["origin"],
                            "effective_from": row["effective_from"], "effective_through": row["effective_through"],
                            "available_at": row["available_at"], "derivation": row["derivation"],
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
                         "status": [{"source": recipe["roles"]["status"], "row": index, **row,
                                     "target": "buckets/" + symbol + "/" + start}
                                    for (symbol, start, _), (row, index) in sorted(coverage.items())],
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
