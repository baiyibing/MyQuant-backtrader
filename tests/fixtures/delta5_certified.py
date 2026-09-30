"""Fabricated tmp_path packages only. No host exports or market facts.

This builder is test code, never a host attestation generator. Every file says
fabricated_test. A passing load verifies structure and pins, not its truth.
"""

import hashlib
import json

from backtest.research.delta5_certified_source import DOCUMENT_TYPES, PACKS, SCHEMA, scope_hash
from backtest.research.delta5_volume_ingress import CLOSE_MINUTES
from tests.fixtures.delta5_ingress import fixture


def pin_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    data = path.read_bytes()
    return {"path": str(path.resolve()), "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "schema": payload["schema"]}


def fabricated_recipe(root, monkeypatch, *, suspended=(), parquet=False, volume=2500, overrides=None):
    f = fixture(suspended=suspended, volume=volume, overrides=overrides)
    old = f["source"]
    lake = root / "invented-lake"
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(lake))
    for key in ("OSKH_PERIOD_1M_ROOT", "OSKH_PERIOD_1D_ROOT", "OSKH_AUTHORITY_HINT_ROOT"):
        monkeypatch.delenv(key, raising=False)
    source = {k: v for k, v in old.items() if k not in {"kind", "schema", "minute", "daily"}}
    source.update(kind="certified-real", schema=SCHEMA,
                  publisher="fabricated test publisher; no real source",
                  snapshot_id="fabricated-only-snapshot", evidence_origin="fabricated_test",
                  pool_origin="fabricated arithmetic signals; not a real strategy",
                  raw_sources=[], materials=[], packs={})
    minutes = old["minute"]  # Explicitly suspended sessions need no invented bar.
    for period, rows, keys in (
        ("1m", minutes, ("symbol", "timestamp", "volume", "open", "high", "low", "close")),
        ("1d", old["daily"], ("symbol", "day", "open", "high", "low", "close")),
    ):
        path = lake / "stock" / f"period={period}" / "dividend_type=none" / "invented.json"
        payload = {"schema": "d5_raw_records_v1", "origin": "fabricated_test",
                   "publisher": source["publisher"], "snapshot_id": source["snapshot_id"],
                   "rows": [{k: row[k] for k in keys} for row in rows]}
        spec = pin_json(path, payload)
        fmt = "json"
        if parquet:
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = (pa.Table.from_pylist(payload["rows"]) if payload["rows"] else
                     pa.Table.from_pylist([], schema=pa.schema([
                         (k, pa.string() if k in {"symbol", "timestamp", "day"} else pa.float64())
                         for k in keys])))
            path = path.with_suffix(".parquet")
            pq.write_table(table, path)
            spec = {"path": str(path.resolve()), "size": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "schema": {field.name: str(field.type) for field in table.schema}}
            fmt = "parquet"
        source["raw_sources"].append({**spec, "id": f"raw_{period}", "period": period,
                                      "format": fmt, "representation": "raw_source_records",
                                      "transformations": [], "columns": {k: k for k in keys}})
    refs = {p: [{"id": s["id"], "sha256": s["sha256"], "columns": s["columns"]}
                for s in source["raw_sources"] if s["period"] == p] for p in ("1m", "1d")}
    claims = {
        "units": {"sources": refs["1m"], "unit": source["unit"], "incremental": True,
                  "price_domain": "raw", "float_exact": True, "transformations": [],
                  "representation": "exact_integer_float_up_to_2^53_minus_1"},
        "availability": {"rule": source["availability_rule"], "records": [
            {"source": "raw_1m", "row": i, **{k: row[k] for k in (
                "symbol", "timestamp", "begin", "end", "available_at", "volume_state")}}
            for i, row in enumerate(old["minute"])]},
        "no_events": {"symbols": sorted(source["instruments"]), **source["no_events"]},
        "halt": {"status": source["status"], "expected_close_minutes": list(CLOSE_MINUTES),
                 "missing_rule": "only_explicitly_suspended_may_be_absent", "grid": [
                     {"symbol": symbol, "day": day, "hm": hm,
                      "missing": status == "suspended", "halted": status == "suspended",
                      "reason": "fabricated explicit status assertion, no market facts"}
                     for symbol, days in source["status"].items() for day, status in days.items()
                     for hm in CLOSE_MINUTES]},
        "context": {"calendar": source["calendar"], "sessions": source["sessions"],
                    "reference_day": source["reference_day"], "instruments": source["instruments"],
                    "pool": source["pool"], "pool_origin": source["pool_origin"],
                    "daily_sources": refs["1d"], "daily_price_domain": "raw",
                    "label": source["label"], "time_encoding": source["time_encoding"],
                    "interval_policy": source["interval_policy"],
                    "limits": {"function": "book_limit_prices", "qlib_limit_pct": None,
                               "names": "registered_instruments"}},
    }
    for subject, basis in PACKS.items():
        binding = claims[subject]
        original = {"schema": "d5_source_document_v1", "origin": "fabricated_test",
                    "document_type": DOCUMENT_TYPES[subject],
                    "issuer": "invented evidence issuer", "original_reference": f"invented:{subject}",
                    "extraction_method": "fabricated arithmetic; no real source document",
                    "rows": [{"subject": subject, "basis": basis, "scope_hash": scope_hash(source),
                              "observation": "fabricated observation only", "binding": binding}]}
        material = pin_json(root / "materials" / f"{subject}.json", original)
        source["materials"].append({**material, "id": f"original_{subject}"})
        pack = {"schema": "d5_evidence_pack_v1", "package_id": f"invented_{subject}_v1",
                "subject": subject, "origin": "fabricated_test", "complete": True,
                "issuer": "invented reviewer", "issued_at": "2026-09-30T12:00:00+08:00",
                "summary": "test structure only", "limitations": ["fabricated, no host attestation"],
                "scope_hash": scope_hash(source), "basis": basis, "binding": binding,
                "refs": [{"source": f"original_{subject}", "row": 0}]}
        source["packs"][subject] = pin_json(root / "packs" / f"{subject}.json", pack)
    return {"schema": "d5_certified_recipe_v1", "source": source, "parameters": f["parameters"]}
