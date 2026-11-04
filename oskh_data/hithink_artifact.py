"""Read-only v1 Hithink artifact contract. No network or credential dependency."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

SOURCE = "hithink:market-dumps/adjustment-factors"
DUMP_ENDPOINT = "/api/dump/market-dumps/adjustment-factors/download-url"
IDENTITY_ENDPOINT = "/api/meta/tickers/search"
EVENT_ENDPOINT = "/api/a-share/corporate-actions/adjustment-factors"
FILES = ("hithink_dump.parquet", "probes.json", "manifest.json", "COMMITTED.json")
QUARANTINE_POLICY = "negative_amounts_outside_window_v1"
NUMBERS = ("dividend_per_share", "per_share_bonus", "allotment_ratio", "allotment_price")
SHANGHAI = ZoneInfo("Asia/Shanghai")
ERRORS = {"redirect_blocked", "invalid_https_url", "credential_origin_blocked", "http_error",
          "transfer_budget_exceeded", "response_too_large", "transport_error", "invalid_json_envelope",
          "business_error", "invalid_data", "skipped_after_vendor_stop"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def code(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", value):
        raise ValueError("invalid A-share code")
    return value


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("expected ISO calendar date")
    return date.fromisoformat(value)


def number(value, *, allow_negative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("adjustment amount must be numeric")
    value = Decimal(str(value))
    if not value.is_finite() or (value < 0 and not allow_negative):
        raise ValueError("adjustment amount must be finite and nonnegative")
    pa.scalar(value, type=pa.decimal128(24, 12))
    return value


def parse_dump(path, *, quarantine_window=None):
    table = pq.ParquetFile(path).read()
    required = {"thscode", "ex_date_ms", "currency", *NUMBERS}
    if len(set(table.column_names)) != len(table.column_names) or not required <= set(table.column_names):
        raise ValueError("missing/duplicate adjustment columns")
    if not table.num_rows:
        raise ValueError("empty full-market dump")
    window = tuple(day(v) for v in quarantine_window) if quarantine_window is not None else None
    if window is not None and window[1] < window[0]:
        raise ValueError("invalid quarantine window")
    result, seen, duplicates, quarantine = [], {}, [], []
    for index, raw in enumerate(table.to_pylist()):
        code(raw["thscode"])
        if raw["currency"] != "CNY":
            raise ValueError("adjustment currency must be CNY")
        if "ticker" in raw and raw["ticker"] != raw["thscode"][:6]:
            raise ValueError("ticker/thscode mismatch")
        if type(raw["ex_date_ms"]) is not int:
            raise ValueError("ex_date_ms must be an integer")
        stamp = datetime.fromtimestamp(raw["ex_date_ms"] / 1000, SHANGHAI)
        if (stamp.hour, stamp.minute, stamp.second, stamp.microsecond) != (0, 0, 0, 0):
            raise ValueError("ex_date_ms must denote Shanghai midnight")
        amounts = {k: number(raw[k], allow_negative=window is not None) for k in NUMBERS}
        identity = json.dumps(raw, sort_keys=True, allow_nan=False, default=str)
        if identity in seen:
            duplicates.append({"kept_index": seen[identity], "duplicate_index": index})
            continue
        seen[identity] = index
        negative = [k for k in NUMBERS if amounts[k] < 0]
        if negative:
            if window is None or window[0] <= stamp.date() <= window[1]:
                raise ValueError("negative adjustment amount in incremental window")
            quarantine.append({"row_index": index, "row_sha256": hashlib.sha256(identity.encode()).hexdigest(),
                               "code": raw["thscode"], "ex_date": str(stamp.date()), "negative_fields": negative,
                               "reason": "negative_amount_outside_incremental_window"})
            continue
        result.append({**raw, **amounts, "ex_date": stamp.date()})
    stats = {"dump_rows": table.num_rows, "deduped_rows": len(seen), "duplicates": duplicates}
    if window is not None:
        stats.update(accepted_rows=len(result), quarantined_rows=len(quarantine), quarantine_records=quarantine)
    return result, stats


def present_codes(rows, stats):
    return {r["thscode"] for r in rows} | {r["code"] for r in stats.get("quarantine_records", [])}


def request_identity(config):
    codes = config["codes"]
    if not codes or codes != sorted({code(c) for c in codes}):
        raise ValueError("invalid frozen universe")
    if day(config["end"]) < day(config["start"]):
        raise ValueError("invalid artifact window")
    return {"universe_sha256": config["universe_sha256"], "codes": codes,
            "codes_sha256": hashlib.sha256(("\n".join(codes) + "\n").encode()).hexdigest(),
            "start": config["start"], "end": config["end"]}


def _probe_fields(record, *, identity):
    permitted = {"endpoint", "params", "http_status", "business_code", "response_sha256", "attempts", "error", "request_id"}
    permitted |= {"identities"} if identity else {"data_thscode", "item_count"}
    if not isinstance(record, dict) or not set(record) <= permitted:
        raise ValueError("unexpected probe fields")
    for status in ("http_status", "business_code"):
        if record.get(status) is not None and type(record[status]) is not int:
            raise ValueError("invalid probe status")
    if "error" in record and record["error"] not in ERRORS:
        raise ValueError("unexpected probe error")
    if "response_sha256" in record and not re.fullmatch(r"[0-9a-f]{64}", record["response_sha256"]):
        raise ValueError("invalid response hash")
    if "request_id" in record and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", record["request_id"]):
        raise ValueError("invalid request_id")
    if identity and (not isinstance(record.get("identities", []), list)
                     or any(code(c) != c for c in record.get("identities", []))):
        raise ValueError("invalid identities")
    if not identity:
        if record.get("data_thscode") is not None:
            code(record["data_thscode"])
        if "item_count" in record and (type(record["item_count"]) is not int or record["item_count"] < 0):
            raise ValueError("invalid event count")
    for attempt in record.get("attempts", []):
        if not isinstance(attempt, dict) or set(attempt) != {"error", "http_status", "business_code"}:
            raise ValueError("invalid probe attempt")
        _probe_fields(attempt, identity=identity)


def validate_probes(value, absent, request):
    if not isinstance(value, dict) or set(value) != {"format_version", "probes"} or value["format_version"] != 1:
        raise ValueError("invalid probe document")
    probes = {}
    for item in value["probes"]:
        if set(item) != {"code", "identity", "events"} or item["code"] in probes:
            raise ValueError("invalid/duplicate coverage probe")
        ticker = code(item["code"])
        for kind, endpoint, params in (
            ("identity", IDENTITY_ENDPOINT, {"q": ticker, "asset_type": "a-share", "limit": 50}),
            ("events", EVENT_ENDPOINT, {"thscode": ticker, "from": request["start"], "to": request["end"]}),
        ):
            record = item[kind]
            _probe_fields(record, identity=kind == "identity")
            if record.get("endpoint") != endpoint or record.get("params") != params:
                raise ValueError("coverage probe scope mismatch")
        probes[ticker] = item
    if set(probes) != set(absent):
        raise ValueError("coverage probes do not match dump-absent universe")
    return probes


def proves_empty(probe, ticker):
    identity, events = probe["identity"], probe["events"]
    return (all(r.get("http_status") == 200 and r.get("business_code") == 0 and not r.get("error")
                and r.get("response_sha256") and r.get("request_id") for r in (identity, events))
            and ticker in identity.get("identities", [])
            and events.get("data_thscode") == ticker and events.get("item_count") == 0)


def read_artifact(directory, config):
    directory = Path(directory)
    manifest_hash = digest(directory / "manifest.json")
    manifest = read_json(directory / "manifest.json")
    version = manifest.get("format_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported artifact version")
    if version == 1 and (directory / "quarantine.json").exists():
        raise ValueError("v1 must not contain a quarantine sidecar")
    payload = (*FILES[:2], "quarantine.json") if version == 2 else FILES[:2]
    names = (*payload, *FILES[2:])
    before = {name: digest(directory / name) for name in names}
    if before["manifest.json"] != manifest_hash:
        raise ValueError("manifest changed while reading")
    marker = read_json(directory / "COMMITTED.json")
    request = request_identity(config)
    if version == 2:
        request["quarantine_policy"] = QUARANTINE_POLICY
    if type(marker.get("format_version")) is not int or marker != {"format_version": version, "manifest_sha256": before["manifest.json"]}:
        raise ValueError("invalid artifact commit marker")
    if (manifest.get("producer") != "OSkhQuant1.3"
            or manifest.get("source") != SOURCE or manifest.get("endpoint") != DUMP_ENDPOINT
            or manifest.get("request") != request or manifest.get("coverage_passed") is not False
            or manifest.get("lake_write_authorized") is not False):
        raise ValueError("artifact contract/request mismatch")
    stamp = datetime.fromisoformat(manifest["fetched_at"])
    if stamp.utcoffset() is None:
        raise ValueError("fetched_at requires a timezone")
    if manifest.get("files") != {k: before[k] for k in payload}:
        raise ValueError("artifact content hash mismatch")
    rows, stats = parse_dump(directory / FILES[0], quarantine_window=(request["start"], request["end"]) if version == 2 else None)
    if canonical_json(stats) != canonical_json(manifest["dump"]):
        raise ValueError("artifact dump statistics mismatch")
    if version == 2:
        expected = {"format_version": 1, "policy": QUARANTINE_POLICY,
                    "window": {k: request[k] for k in ("start", "end")}, "rows": stats["quarantine_records"]}
        if canonical_json(read_json(directory / "quarantine.json")) != canonical_json(expected):
            raise ValueError("quarantine evidence mismatch")
    absent = set(request["codes"]) - present_codes(rows, stats)
    probes = validate_probes(read_json(directory / "probes.json"), absent, request)
    if before != {name: digest(directory / name) for name in names}:
        raise ValueError("artifact changed while reading")
    return manifest, rows, probes, before
