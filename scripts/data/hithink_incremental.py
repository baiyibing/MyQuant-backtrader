"""Offline Hithink branch of the existing candidate-only incremental driver."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import uuid

import pyarrow as pa
import pyarrow.parquet as pq

from oskh_data import hithink_artifact as artifact

CLASSES = ("delisted_explained", "delisted_no_history", "trading_eventless", "unexplained")


def imported(run):
    marker = artifact.read_json(run.path("work/hithink_committed.json"))
    state = artifact.read_json(run.path("work/hithink_state.json"))
    manifest, rows, probes, hashes = artifact.read_artifact(run.path("raw_events"), run.config)
    if marker != {"format_version": 1, "state_sha256": artifact.digest(run.path("work/hithink_state.json")),
                  "artifact_sha256": hashes} or state["artifact_sha256"] != hashes:
        raise ValueError("import commit/state mismatch")
    if state["fetched_at"] != manifest["fetched_at"]:
        raise ValueError("import changed original fetched_at")
    universe = set(run.config["codes"])
    present = artifact.present_codes(rows, manifest["dump"]) & universe
    hits = {r["thscode"] for r in rows if artifact.day(run.config["start"]) <= r["ex_date"] <= artifact.day(run.config["end"])} & universe
    expected = {**manifest["dump"], "dump_sha256": hashes["hithink_dump.parquet"],
                "universe_hits": sorted(hits), "codes_no_events": sorted(present - hits),
                "codes_vendor_unknown": sorted(universe - present), "vendor_unknown_probes": probes}
    if any(artifact.canonical_json(state.get(k)) != artifact.canonical_json(v) for k, v in expected.items()):
        raise ValueError("import state differs from verified artifact facts")
    for key, default in (("quarantine_records", []), ("quarantined_rows", 0)):
        if artifact.canonical_json(state.get(key, default)) != artifact.canonical_json(manifest["dump"].get(key, default)):
            raise ValueError("import state quarantine differs from verified artifact facts")
    if (type(state.get("artifact_version", 1)) is not int
            or state.get("artifact_version", 1) != manifest["format_version"]
            or state.get("quarantine_policy") != manifest["request"].get("quarantine_policy")):
        raise ValueError("import state artifact version/policy mismatch")
    return state, rows, probes


def import_artifact(run, directory, *, refresh=False):
    from scripts.data.pull_corp_actions_incremental import json_bytes
    run.verify_base()
    if not directory:
        raise ValueError("hithink requires --artifact-dir; this repository never downloads it")
    manifest, rows, probes, hashes = artifact.read_artifact(directory, run.config)
    marker = run.path("work/hithink_committed.json")
    remnants = any(run.path(p).exists() for p in ("raw_events", "work/hithink_state.json", "work/hithink_committed.json"))
    if refresh and run.path("assembled").exists():
        raise ValueError("refresh forbidden after assemble consumed the snapshot")
    if remnants and not refresh:
        try:
            state, _, _ = imported(run)
            if state["artifact_sha256"] != hashes:
                raise ValueError("different artifact")
            return 0
        except (ValueError, KeyError, OSError, pa.ArrowException):
            raise ValueError("incomplete/different import; use --refresh before assemble or create a new run") from None
    staging = run.path("work/import-" + uuid.uuid4().hex)
    staging.mkdir()
    for name in hashes:
        shutil.copyfile(Path(directory) / name, staging / name)
    _, _, _, copied = artifact.read_artifact(staging, run.config)
    if hashes != copied or hashes != {k: artifact.digest(Path(directory) / k) for k in hashes}:
        raise ValueError("artifact changed during copy")
    universe = set(run.config["codes"])
    present = artifact.present_codes(rows, manifest["dump"]) & universe
    hits = {r["thscode"] for r in rows if artifact.day(run.config["start"]) <= r["ex_date"] <= artifact.day(run.config["end"])} & universe
    state = {"format_version": 1, "artifact_sha256": hashes, "dump_sha256": hashes["hithink_dump.parquet"],
             "fetched_at": manifest["fetched_at"], "imported_at": datetime.now(timezone.utc).isoformat(),
             **manifest["dump"], "universe_hits": sorted(hits), "codes_no_events": sorted(present - hits),
             "artifact_version": manifest["format_version"], "quarantine_policy": manifest["request"].get("quarantine_policy"),
             "codes_vendor_unknown": sorted(universe - present), "vendor_unknown_probes": probes}
    run.verify_base()
    if marker.exists():
        marker.unlink()  # Old success cannot survive a partially completed refresh.
    if run.path("raw_events").exists():
        run.path("raw_events").rename(run.path("work/superseded-" + uuid.uuid4().hex))
    staging.rename(run.path("raw_events"))
    run.write("work/hithink_state.json", json_bytes(state))
    run.write("work/hithink_committed.json", json_bytes({"format_version": 1,
              "state_sha256": artifact.digest(run.path("work/hithink_state.json")), "artifact_sha256": hashes}))
    imported(run)
    return 0


def read_exclusions(run):
    raw = run.path("hithink_exclusions.json").read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def coverage(run, rows, probes, *, today=None, exclusions=None, quarantine=()):
    today = today or datetime.now(artifact.SHANGHAI).date()
    universe, start, end = set(run.config["codes"]), artifact.day(run.config["start"]), artifact.day(run.config["end"])
    base = Path(run.config["lake_dir"])
    listing = {}
    for row in pq.ParquetFile(base / "listing.parquet").read().to_pylist():
        ticker = artifact.code(row["code"])
        if ticker in listing:
            raise ValueError("duplicate listing identity")
        listing[ticker] = row
    history = set(pq.ParquetFile(base / "events.parquet").read(columns=["code"])["code"].to_pylist())
    present = {r["thscode"] for r in rows} | {r["code"] for r in quarantine}
    unknown = universe - present
    classified = {}
    for ticker in sorted(unknown):
        record = listing.get(ticker)
        delist = record.get("delist_date") if record else None
        if delist is not None and not hasattr(delist, "year"):
            raise ValueError("listing delist_date must be a calendar date")
        classification = "unexplained"
        if record and delist is not None and delist < start:
            classification = "delisted_explained" if ticker in history else "delisted_no_history"
        elif record and delist is None and ticker not in history and artifact.proves_empty(probes[ticker], ticker):
            classification = "trading_eventless"
        classified[ticker] = {"classification": classification, "delist_date": str(delist) if delist else None,
                              "has_base_history": ticker in history}
    config, exclusions_sha256 = exclusions if exclusions is not None else read_exclusions(run)
    applied, warnings, seen = [], [], set()
    for override in config["manual_overrides"]:
        ticker = artifact.code(override["code"])
        if ticker in seen:
            raise ValueError("duplicate manual override")
        seen.add(ticker)
        if ticker not in universe:
            warnings.append(f"override outside universe: {ticker}")
            continue
        if override.get("classification") not in CLASSES:
            raise ValueError("unknown override classification")
        if ticker not in classified or classified[ticker]["classification"] != "unexplained":
            raise ValueError("manual override only applies to actual D; classification drift")
        for key in ("reason", "evidence", "approved_by"):
            if not isinstance(override.get(key), str) or not override[key].strip():
                raise ValueError("manual override requires review evidence")
        approved, review = artifact.day(override["approved_at"]), artifact.day(override["review_after"])
        scope_start, scope_end = artifact.day(override["scope_start"]), artifact.day(override["scope_end"])
        if not approved <= today <= review or not scope_start <= start <= end <= scope_end:
            raise ValueError("expired/future approval or override scope does not cover incremental window")
        applied.append({**override, "evaluated_at": str(today)})
    effective = {o["code"] for o in applied if o["classification"] != "unexplained"}
    unresolved = [c for c, info in classified.items() if info["classification"] == "unexplained" and c not in effective]
    if artifact.digest(run.path("hithink_exclusions.json")) != exclusions_sha256:
        raise ValueError("exclusions changed during coverage evaluation")
    return {"vendor_unknown_classification": classified, "manual_overrides_applied": applied,
            "exclusions_sha256": exclusions_sha256,
            "coverage_warnings": warnings, "unresolved_codes": sorted(unresolved), "unresolved_tasks": len(unresolved)}


def assemble(run):
    from scripts.data import pull_corp_actions_incremental as driver
    run.verify_base()
    state, raw, probes = imported(run)
    facts = coverage(run, raw, probes, quarantine=state.get("quarantine_records", []))
    universe = set(run.config["codes"])
    start, end = artifact.day(run.config["start"]), artifact.day(run.config["end"])
    rows, rights, mixed = [], [], []
    for record in raw:
        if record["thscode"] not in universe or not start <= record["ex_date"] <= end:
            continue
        if record["allotment_ratio"] > 0:
            sidecar = {k: str(v) if isinstance(v, Decimal) or k == "ex_date" else v for k, v in record.items()}
            has_economics = record["dividend_per_share"] > 0 or record["per_share_bonus"] > 0
            sidecar["reason"] = "mixed_economics_requires_review" if has_economics else "pure_allotment_out_of_scope"
            rights.append(sidecar)
            if has_economics:
                mixed.append(sidecar)
            continue
        row = {"code": record["thscode"], "ex_date": record["ex_date"],
               "cash_div_per_share": record["dividend_per_share"], "bonus_ratio": record["per_share_bonus"],
               "transfer_ratio": None, "record_date": None, "pay_date": None, "bonus_list_date": None,
               "source": artifact.SOURCE}
        identity = "|".join("NULL" if x is None else str(x.normalize()) if isinstance(x, Decimal) else str(x)
                            for x in driver.natural_key(row))
        row["event_id"] = f"{row['code']}_{row['ex_date']:%Y%m%d}_incr_" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        rows.append(row)
    if len({r["event_id"] for r in rows}) != len(rows):
        # Distinct raw rows can project to the same 10-column natural key: never silently collapse.
        raise ValueError("distinct raw records collide after mapping; manual identity review required")
    rows.sort(key=lambda r: (r["code"], r["ex_date"], r["event_id"]))
    table = pa.Table.from_pylist(rows, schema=driver.EVENT_SCHEMA)
    buffer = pa.BufferOutputStream()
    pq.write_table(table, buffer, compression="snappy", row_group_size=8192)
    run.write("assembled/events.parquet", buffer.getvalue().to_pybytes())
    run.write("assembled/corp_actions.csv", driver.table_bytes_csv(table))
    run.write("assembled/rejected.json", driver.json_bytes(mixed))
    run.write("assembled/hithink_allotments.json", driver.json_bytes(rights))
    from collections import Counter
    dates = Counter((r["code"], r["ex_date"]) for r in rows)
    report = {"channel": "hithink", **facts, "event_rows": len(rows), "rejected_rows": len(mixed),
              "quarantined_rows": state.get("quarantined_rows", 0),
              "quarantined_codes": sorted({r["code"] for r in state.get("quarantine_records", [])}),
              "quarantine_policy": state.get("quarantine_policy"),
              "mixed_economics_requires_review": len(mixed), "hithink_allotment_rows": len(rights),
              "universe_hits": state["universe_hits"], "codes_no_events": state["codes_no_events"],
              "codes_vendor_unknown": state["codes_vendor_unknown"],
              "null_counts": {k: table[k].null_count for k in driver.EVENT_COLS},
              "multiple_event_code_dates": sum(n > 1 for n in dates.values()),
              "window": {k: run.config[k] for k in ("start", "end")}, "dump_sha256": state["dump_sha256"],
              "fetched_at": state["fetched_at"], "imported_at": state["imported_at"],
              "events_sha256": artifact.digest(run.path("assembled/events.parquet")),
              "import_sha256": artifact.digest(run.path("work/hithink_committed.json")),
              "evidence": state["artifact_sha256"], "coverage_is_vendor_query_only": True,
              "acquisition": "committed", "economics_ready": False, "lake_write_authorized": False}
    run.write("assembled/summary.json", driver.json_bytes(report))
    imported(run)
    run.verify_base()
    if artifact.digest(run.path("hithink_exclusions.json")) != report["exclusions_sha256"]:
        raise ValueError("exclusions changed during assembly")
    return table, report
