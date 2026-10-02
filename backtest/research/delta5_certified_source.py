"""Pinned, read-only δ5 source preflight; no host authentication or lake PASS.

Packages bind concrete claims to independently pinned source-document excerpts.
The host must audit the originals and issuer authority: software cannot establish
the truth of a narrative. Fabricated tests remain explicitly marked as such.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

import pandas as pd

from backtest.research.delta5_volume_ingress import (
    CLOSE_MINUTES, IngressError, UNIT, _map_records, decode_time, digest, prices,
    require, session, shares,
)
from common.infra import data_root

SCHEMA = "d5_certified_real_source_v1"
PACKS = {
    "units": "source_units_declaration",
    "availability": "publication_records",
    "no_events": "corporate_action_coverage",
    "halt": "explicit_halt_missing_grid",
    "context": "calendar_instrument_and_mapping_facts",
}
DOCUMENT_TYPES = {
    "units": "publisher_field_semantics",
    "availability": "publication_log_or_contract",
    "no_events": "corporate_action_registry_coverage",
    "halt": "halt_and_missing_registry",
    "context": "calendar_listing_mapping_coverage",
}
MAPPING_VERSION = "d5_certified_mapping_v1"
UNFILLED_TEXT = {
    "null", "none", "nil", "nan", "na", "n/a", "n.a.", "not applicable",
    "not available", "not provided", "missing", "unknown", "unfilled",
    "placeholder", "todo", "tbd", "tbc", "-", "--", "?",
}


def nonempty(value, where):
    require(isinstance(value, str) and bool(value.strip()) and
            value.strip().lower() not in UNFILLED_TEXT,
            "evidence", f"{where}: unfilled text")
    return value


def strict_json(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "schema", f"duplicate JSON key {key}")
            result[key] = value
        return result

    def invalid(value):
        raise IngressError("schema", f"nonfinite JSON value {value}")

    return json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid)


def file_identity(path):
    payload = path.read_bytes()
    stat = path.stat()
    return {"path": str(path.resolve()), "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(), "device": stat.st_dev,
            "inode": stat.st_ino, "mtime_ns": stat.st_mtime_ns}


def read_pin(spec, identities):
    path = Path(nonempty(spec["path"], "pinned absolute path"))
    require(path.is_absolute(), "identity", "pinned path must be absolute")
    require(isinstance(spec["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", spec["sha256"])
            and type(spec["size"]) is int and spec["size"] > 0,
            "identity", "bytes SHA-256 and positive size required")
    before = file_identity(path)
    payload = path.read_bytes()
    after = file_identity(path)
    require(before == after and before["sha256"] == spec["sha256"]
            and len(payload) == spec["size"]
            and hashlib.sha256(payload).hexdigest() == spec["sha256"],
            "identity", f"pin mismatch / changed during read: {path}")
    require(all(item["path"] != before["path"] and item["sha256"] != before["sha256"]
                for item in identities), "identity", f"aliased/reused source bytes: {path}")
    identities.append({**before, "schema": spec["schema"]})
    return payload


def verify_unchanged(identities):
    for before in identities:
        require(file_identity(Path(before["path"])) ==
                {key: value for key, value in before.items() if key != "schema"},
                "identity", f"source changed after preflight: {before['path']}")


def scope_hash(source):
    # No circular proof hashes; all source identities and mapping assertions bind.
    return digest({k: v for k, v in source.items() if k not in {"materials", "packs"}})


def input_roots(source):
    """For output isolation, including evidence stored outside the lake."""
    roots = set()

    def walk(value):
        if isinstance(value, dict):
            path = value.get("path")
            if isinstance(path, str) and path:
                roots.add(Path(path).resolve().parent)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(source)  # Unfilled templates still get a failure receipt, not a locator crash.
    return sorted(roots)


def _raw_sources(source, identities):
    container = data_root.resolve_parquet_container()
    require(container.is_absolute() and container.is_dir(), "resolver", "configured lake root missing")
    roots = {period: data_root.resolve_period_root(period) for period in ("1m", "1d")}
    for root in roots.values():
        require(root.is_absolute() and root.is_dir(), "resolver", f"configured period root missing: {root}")
    resolver = {"container": str(container.resolve()),
                "period_roots": {k: str(v.resolve()) for k, v in roots.items()},
                "environment": {k: os.environ.get(k) for k in (
                    "OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT",
                    "OSKH_PERIOD_1M_ROOT", "OSKH_PERIOD_1D_ROOT")}}
    marker = data_root.find_authority_marker()
    if not os.environ.get("OSKH_SOURCE_PARQUET_ROOT") and marker is not None:
        resolver["authority_marker"] = file_identity(marker)
    records, ids = {"1m": [], "1d": []}, set()
    require(type(source["raw_sources"]) is list and source["raw_sources"], "source", "raw sources required")
    for spec in source["raw_sources"]:
        sid = nonempty(spec["id"], "source ID")
        require(sid not in ids, "source", f"duplicate source ID {sid}")
        ids.add(sid)
        period = spec["period"]
        require(period in roots, "source", "only raw minute/daily sources accepted")
        require(spec["representation"] == "raw_source_records" and spec["transformations"] == [],
                "source", "cleaned read_lake_minute_ohlc frames / transformed sources are not evidence")
        path = Path(spec["path"]).resolve()
        partition = roots[period].resolve() / "dividend_type=none"
        require(path.is_relative_to(partition) and partition.is_dir(),
                "resolver", f"source outside configured raw partition: {path}")
        payload = read_pin(spec, identities)
        if spec["format"] == "parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pq.ParquetFile(pa.BufferReader(payload)).read()
            actual = {field.name: str(field.type) for field in table.schema}
            require(len(actual) == len(table.schema) and actual == spec["schema"],
                    "schema", f"raw parquet schema mismatch: {sid}")
            rows = table.to_pylist()  # No projection, filtering, keep-last or cache.
        else:
            require(spec["format"] == "json" and spec["schema"] == "d5_raw_records_v1",
                    "schema", "unsupported raw file schema/format")
            document = strict_json(payload)
            require(document["schema"] == spec["schema"]
                    and document["origin"] == source["evidence_origin"]
                    and document["publisher"] == source["publisher"]
                    and document["snapshot_id"] == source["snapshot_id"],
                    "source", "raw snapshot identity/origin mismatch; synthetic relabel forbidden")
            rows = document["rows"]
        require(type(rows) is list, "source", f"raw record list required: {sid}")
        columns = spec["columns"]
        required = {"symbol", "timestamp", "volume", "open", "high", "low", "close"} if period == "1m" else {
            "symbol", "day", "open", "high", "low", "close"}
        require(set(columns) == required and all(isinstance(v, str) and v for v in columns.values())
                and len(set(columns.values())) == len(columns), "schema", f"explicit one-to-one columns: {sid}")
        if spec["format"] == "parquet":
            require(set(columns.values()) <= set(actual), "schema", f"missing physical columns: {sid}")
        for i, row in enumerate(rows):
            mapped = {key: row[column] for key, column in columns.items()}
            # Datetime physical columns preserve their encoding; no timezone guess.
            if period == "1m" and not isinstance(mapped["timestamp"], str):
                require(hasattr(mapped["timestamp"], "isoformat"), "time", "unsupported timestamp storage")
                mapped["timestamp"] = mapped["timestamp"].isoformat()
            records[period].append((sid, i, mapped))
    require({s["period"] for s in source["raw_sources"]} == set(roots),
            "source", "pinned minute and daily sources required")
    return records, resolver


def _packages(source, identities):
    require(type(source["packs"]) is dict and set(source["packs"]) == set(PACKS),
            "evidence", f"required independent packs: {', '.join(PACKS)}")
    materials = {}
    for spec in source["materials"]:
        sid = nonempty(spec["id"], "material ID")
        require(sid not in materials and sid not in {v["id"] for v in source["raw_sources"]},
                "evidence", "duplicate/self-referencing material ID")
        require(spec["schema"] == "d5_source_document_v1", "evidence", "source document required, not bars/ST lists/proofs")
        document = strict_json(read_pin(spec, identities))
        require(document["schema"] == spec["schema"] and
                document["origin"] == source["evidence_origin"], "evidence", "document schema/origin mismatch")
        for key in ("issuer", "original_reference", "extraction_method"):
            nonempty(document[key], f"{sid}.{key}")
        require(type(document["rows"]) is list and document["rows"], "evidence", "empty original evidence")
        materials[sid] = document
    require(materials, "evidence", "independent source materials missing")
    claims, used_materials, pack_ids = {}, set(), set()
    for subject, basis in PACKS.items():
        spec = source["packs"][subject]
        require(spec["schema"] == "d5_evidence_pack_v1", "evidence", f"{subject}: wrong package schema")
        pack = strict_json(read_pin(spec, identities))
        pid = nonempty(pack["package_id"], "package ID")
        require(pid not in pack_ids, "evidence", "duplicate package ID")
        pack_ids.add(pid)
        require(pack["schema"] == spec["schema"] and pack["subject"] == subject
                and pack["origin"] == source["evidence_origin"] and pack["complete"] is True,
                "evidence", f"{subject}: missing/unfilled/incomplete pack")
        for key in ("issuer", "summary"):
            nonempty(pack[key], f"{subject}.{key}")
        issued = pd.Timestamp(nonempty(pack["issued_at"], f"{subject}.issued_at"))
        require(not pd.isna(issued) and issued.tzinfo is not None, "evidence", "explicit evidence issue instant required")
        require(type(pack["limitations"]) is list and pack["limitations"], "evidence", "limitations required")
        for limitation in pack["limitations"]:
            nonempty(limitation, "limitation")
        require(pack["scope_hash"] == scope_hash(source), "evidence", f"{subject}: stale snapshot/scope binding")
        require(pack["basis"] == basis, "evidence", f"{subject}: heuristic/ST/mtime/silence is not attestation")
        require(type(pack["refs"]) is list and pack["refs"], "evidence", f"{subject}: independent evidence refs missing")
        refs = set()
        for ref in pack["refs"]:
            sid, row = ref["source"], ref["row"]
            require(sid in materials and type(row) is int and 0 <= row < len(materials[sid]["rows"]),
                    "evidence", f"{subject}: invalid original row ref")
            require((sid, row) not in refs, "evidence", "duplicate evidence ref")
            refs.add((sid, row))
            original = materials[sid]["rows"][row]
            require(materials[sid]["document_type"] == DOCUMENT_TYPES[subject],
                    "evidence", f"{subject}: heuristics/ST lists/bars are not independent source documents")
            require(original["basis"] == basis and original["subject"] == subject
                    and original["scope_hash"] == pack["scope_hash"]
                    and digest(original["binding"]) == digest(pack["binding"]),
                    "evidence", f"{subject}: original basis/concrete binding mismatch")
            nonempty(original["observation"], "original observation")
            used_materials.add(sid)
        claims[subject] = pack
    require(used_materials == set(materials), "evidence", "unreferenced evidence material")
    return claims


def _source_refs(source, period):
    return [{"id": s["id"], "sha256": s["sha256"], "columns": s["columns"]}
            for s in source["raw_sources"] if s["period"] == period]


def normalize_certified(source):
    require(source["schema"] == SCHEMA, "source", "certified-real needs its own manifest; synthetic relabel forbidden")
    for key in ("publisher", "snapshot_id", "evidence_id", "pool_origin"):
        nonempty(source[key], key)
    require(source["evidence_origin"] in {"fabricated_test", "host_supplied"},
            "evidence", "explicit fabricated_test/host_supplied origin required")
    require(not ({"minute", "daily", "native", "oracle"} & set(source)),
            "source", "inline/cleaned frames forbidden; raw pinned files required")
    require(type(source["float_exact"]) is bool, "units", "explicit float representation proof required")
    identities = []
    records, resolver = _raw_sources(source, identities)
    packs = _packages(source, identities)

    def bound(subject, expected):
        require(digest(packs[subject]["binding"]) == digest(expected), "evidence",
                f"{subject}: concrete claim/coverage mismatch")

    bound("units", {"sources": _source_refs(source, "1m"), "unit": source["unit"],
                    "incremental": source["incremental"], "price_domain": source["price_domain"],
                    "float_exact": source["float_exact"], "transformations": [],
                    "representation": "exact_integer_float_up_to_2^53_minus_1" if source["float_exact"]
                    else "integer_storage"})
    require(source["unit"] == UNIT and source["incremental"] is True and source["price_domain"] == "raw",
            "units", "only raw incremental shares; no lots/amount/cumulative/adjustment conversion")
    bound("no_events", {"symbols": sorted(source["instruments"]), **source["no_events"]})
    bound("context", {"calendar": source["calendar"], "sessions": source["sessions"],
                      "reference_day": source["reference_day"], "instruments": source["instruments"],
                      "pool": source["pool"], "pool_origin": source["pool_origin"],
                      "daily_sources": _source_refs(source, "1d"), "daily_price_domain": "raw",
                      "label": source["label"], "time_encoding": source["time_encoding"],
                      "interval_policy": source["interval_policy"],
                      "limits": {"function": "book_limit_prices", "qlib_limit_pct": None,
                                 "names": "registered_instruments"}})
    availability = packs["availability"]["binding"]
    require(set(availability) == {"rule", "records"} and
            availability["rule"] == source["availability_rule"] == "explicit_record_publication_time",
            "availability", "publication proof beyond close/mtime required")
    publication = {}
    for row in availability["records"]:
        require(set(row) == {"source", "row", "symbol", "timestamp", "begin", "end", "available_at", "volume_state"}
                and type(row["row"]) is int, "availability", "explicit per-source-row publication binding required")
        key = row["source"], row["row"]
        require(key not in publication, "availability", "duplicate publication binding")
        publication[key] = row
    require(source["label"] in {"START", "END"} and
            source["time_encoding"] in {"local_wall", "utc_instant", "utc_wall"}, "time", "unknown label/encoding")
    validated_minute, used, buckets, previous = [], set(), set(), {}
    present = set()
    for sid, i, row in records["1m"]:
        # Validate the entire pinned file, including rows outside the run window.
        symbol = row["symbol"]
        require(symbol in source["instruments"], "symbols", f"unknown symbol {symbol}")
        code = source["instruments"][symbol]["engine_symbol"]
        ts = decode_time(row["timestamp"], source["time_encoding"])
        close = ts + pd.Timedelta(minutes=1) if source["label"] == "START" else ts
        begin = close - pd.Timedelta(minutes=1)
        day = close.strftime("%Y%m%d")
        hm = close.hour * 60 + close.minute
        require(close == close.floor("min") and begin.date() == close.date()
                and hm in CLOSE_MINUTES, "time", f"outside session physical minute {begin}/{close}")
        bucket = code, day, hm
        require(bucket not in buckets, "coverage", f"duplicate bucket {bucket}")
        require(code not in previous or close > previous[code],
                "coverage", f"unordered/overlap {bucket}")
        buckets.add(bucket)
        previous[code] = close
        quantity = shares(row["volume"], source["float_exact"])
        prices(row)
        key = sid, i
        require(key in publication, "availability", f"missing publication proof {key}")
        proof = publication[key]
        require(proof["symbol"] == row["symbol"] and proof["timestamp"] == row["timestamp"],
                "availability", f"publication belongs to another raw record {key}")
        require(decode_time(proof["begin"], source["time_encoding"]) == begin
                and decode_time(proof["end"], source["time_encoding"]) == close,
                "time", "label does not identify physical interval")
        available = decode_time(proof["available_at"], source["time_encoding"])
        require(available >= close, "availability", "publication before close")
        require(available.ceil("min").date() == close.date(), "availability", "cross-session publication")
        require(proof["volume_state"] == ("zero" if quantity == 0 else "positive"),
                "volume", f"missing/contradictory zero status {bucket}")
        validated_minute.append((day, {**row, **{k: proof[k] for k in (
            "begin", "end", "available_at", "volume_state")}}))
        used.add(key)
        present.add((symbol, day, hm))
    require(used == set(publication), "availability", "extraneous publication proof")
    previous_daily = {}
    for _, _, row in records["1d"]:
        require(row["symbol"] in source["instruments"], "symbols", "unknown daily symbol")
        code = source["instruments"][row["symbol"]]["engine_symbol"]
        day = row["day"]
        session(day)
        require(code not in previous_daily or day > previous_daily[code],
                "coverage", f"duplicate/unordered daily {code}/{day}")
        previous_daily[code] = day
        prices(row)
    # Selection follows full-file row checks; requested dates and coverage stay frozen.
    minute = [row for day, row in validated_minute if source["start"] <= day <= source["end"]]
    present = {key for key in present if source["start"] <= key[1] <= source["end"]}
    halt = packs["halt"]["binding"]
    require(set(halt) == {"status", "expected_close_minutes", "missing_rule", "grid"}
            and digest(halt["status"]) == digest(source["status"])
            and halt["expected_close_minutes"] == list(CLOSE_MINUTES)
            and halt["missing_rule"] == "only_explicitly_suspended_may_be_absent",
            "coverage", "explicit complete halt/missing rules required")
    grid = set()
    expected = {(symbol, day, hm) for symbol in source["instruments"]
                for day in source["sessions"] for hm in CLOSE_MINUTES}
    for row in halt["grid"]:
        key = row["symbol"], row["day"], row["hm"]
        require(type(row["hm"]) is int and key in expected and key not in grid,
                "coverage", f"unexpected/duplicate halt grid key {key}")
        nonempty(row["reason"], "halt/missing reason")
        require(type(row["missing"]) is bool and type(row["halted"]) is bool
                and row["missing"] == (key not in present)
                and row["halted"] == (source["status"][key[0]][key[1]] == "suspended")
                and (not row["missing"] or row["halted"]),
                "coverage", f"halt/missing contradiction or active gap {key}")
        grid.add(key)
    require(grid == expected, "coverage", {"missing_halt_grid": sorted(expected - grid)})
    daily = [row for _, _, row in records["1d"] if source["reference_day"] <= row["day"] <= source["end"]]
    audit = {"mapping_version": MAPPING_VERSION, "source_kind": "certified-real",
             "source_certification": "verified", "certification_scope": "structure_and_pins_only",
             "host_attestation": "NOT_RUN", "real_lake_run": "NOT_RUN",
             "evidence_origin": source["evidence_origin"], "resolver": resolver,
             "source_identity": {k: source[k] for k in ("schema", "publisher", "snapshot_id", "evidence_id")},
             "scope_hash": scope_hash(source), "evidence_hash": digest(packs),
             "raw_row_counts": {period: {"validated": len(records[period]), "selected": len(selected),
                                         "excluded_outside_window": len(records[period]) - len(selected)}
                                for period, selected in (("1m", minute), ("1d", daily))},
             "packages": packs, "pinned_inputs": identities, "pool_origin": source["pool_origin"]}
    result = _map_records({**source, "minute": minute, "daily": daily}, audit)
    verify_unchanged(identities)
    return result
