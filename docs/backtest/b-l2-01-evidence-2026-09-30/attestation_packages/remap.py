"""Offline remap of pinned #1111 evidence; no lake, network, runner or R4.

Uses only the standard library. Pinned LF inputs are vendored for offline CI.
Unknown historical availability and rule approval remain explicitly blocked.
"""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


HERE = Path(__file__).resolve().parent
SYMBOL = "603196.SH"
FIRST, LAST = "2025-10-23", "2025-11-04"
MINUTE_SOURCE = "minute_603196"
GO_CUE = "人裁：①量单位接受直接对账（basis=cross_source_ratio），然后 remap"
DATES = ("20251023", "20251024", "20251027", "20251028", "20251029",
         "20251030", "20251031", "20251103", "20251104")
NOTICE = "Remapped draft only; structural checks != lake PASS; R3 BLOCKED/NOT_RUN; R4 needs separate Human「开 R4」; production_C=frozen."


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decimal_strings(value):
    """Keep decimal values exact in loader JSON, including nested metadata."""
    if isinstance(value, (Decimal, float)):
        number = Decimal(str(value))
        require(number.is_finite(), "non-finite source number")
        return format(number, "f")
    if isinstance(value, dict):
        return {key: decimal_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decimal_strings(item) for item in value]
    return value


def encode(document):
    """Compact JSON, one data row per line for stable diffs on the 2160 grid."""
    document = decimal_strings(document)
    if "schema_version" in document:
        data = document["data"]
        rows_key = "result" if "result" in data else None
        owner = data[rows_key] if rows_key else data
        if "rows" in owner:
            empty = json.loads(json.dumps(document))
            target = empty["data"][rows_key] if rows_key else empty["data"]
            target["rows"] = "__ROWS__"
            text = json.dumps(empty, ensure_ascii=False, indent=2)
            rows = ",\n".join("    " + json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                              for row in owner["rows"])
            return (text.replace('"__ROWS__"', "[\n" + rows + "\n  ]") + "\n").encode("utf-8")
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_inputs(source_dir, human_go):
    pins = json.loads((HERE / "inputs.json").read_bytes())
    require(digest(human_go.read_bytes()) == pins["human_go_sha256"], "Human GO hash mismatch")
    inputs = {}
    for name, hashes in pins["files"].items():
        raw = (source_dir / name).read_bytes()
        require(digest(raw) in hashes.values(), f"input hash mismatch: {name}")
        # Explicitly allow only the pinned Git LF or original host CRLF bytes.
        normalized = raw.replace(b"\r\n", b"\n")
        require(digest(normalized) == hashes["git_sha256"], f"non-newline source difference: {name}")
        if hashes.get("host_sha256", hashes["git_sha256"]) != hashes["git_sha256"]:
            require(digest(normalized.replace(b"\n", b"\r\n")) == hashes["host_sha256"],
                    f"host CRLF pin mismatch: {name}")
        text = normalized.decode("utf-8")
        # Parse decimal tokens directly: do not round pinned source text via binary floats.
        inputs[name] = (list(csv.DictReader(io.StringIO(text))) if name.endswith(".csv")
                        else json.loads(text, parse_float=Decimal))
    return pins, inputs


def build(source_dir, human_go):
    pins, inputs = read_inputs(source_dir, human_go)
    artifacts = {}

    def add(identity, filename, schema, data):
        artifacts[filename] = (identity, {"schema_version": schema, "data": data})

    def excerpt(identity, name, rows, **metadata):
        origin = {"repository": pins["repository"], "commit": pins["commit"],
                  "path": pins["directory"] + "/" + name, **pins["files"][name]}
        add(identity, "sources/" + identity + ".json", "bl2_raw_excerpt_v1",
            {"origin": origin, **metadata, "rows": rows})

    raw_names = {
        "daqmt_1m": "raw/daqmt_603196_1m_none.csv",
        "daqmt_1d": "raw/daqmt_603196_1d_none.csv",
        "ths_daily": "raw/kimi_stock_finance_data_603196_daily.csv",
        "ratio_table": "raw/daqmt_ths_unit_ratio_table.csv",
        "zero_volume": "raw/daqmt_603196_zero_volume_bars.csv",
        "wind_limits": "raw/wind_603196_daily_limits.csv",
    }
    for identity, name in raw_names.items():
        rows = inputs[name]
        columns = list(rows[0])
        if identity == "daqmt_1m":
            columns = ["datetime", "time", "volume", "suspendFlag"]
            rows = [{k: r[k] for k in columns} for r in rows]
        excerpt(identity, name, rows, extraction={"method": "CSV DictReader, strings unchanged, row order unchanged",
                                                "columns": columns, "row_index": "zero-based excluding header"})
    excerpt("daqmt_detail", "raw/daqmt_603196_instrument_detail.json",
            [inputs["raw/daqmt_603196_instrument_detail.json"]],
            limitation="2026-09-30 snapshot; corroboration only, not historical limits or listing status.")
    excerpt("sse_rule", "instruments.proof.json", [inputs["instruments.proof.json"]["proofs"][0]],
            extraction={"json_pointer": "/proofs/0"},
            limitation="Host-recorded SSE rule paraphrase and URL only; original rule archive and approval receipt absent.")
    excerpt("upstream_instruments", "instruments.json", inputs["instruments.json"]["rows"],
            extraction={"json_pointer": "/rows"},
            upstream_metadata={k: inputs["instruments.json"][k] for k in ("origin", "approved_rule_version", "board", "inputs")})
    excerpt("vendor_status_semantics", "status.proof.json",
            [inputs["status.proof.json"]["vendor_field_semantics"]],
            extraction={"json_pointer": "/vendor_field_semantics"},
            limitation="#1111 records thinktrader semantics: 0 normal, 1 suspended, -1 resumption day; fill_data=True.")
    excerpt("vendor_units_absence", "units.proof.json", [inputs["units.proof.json"]["vendor_doc_verbatim"]],
            extraction={"json_pointer": "/vendor_doc_verbatim"},
            limitation="Vendor K-line volume unit declaration is absent; upstream basis label source_declaration is not adopted.")

    marker = {"approval_id": "b_l2_remap_r4_20260930", "source_document_sha256": pins["human_go_sha256"],
              "cue": GO_CUE, "basis": "cross_source_ratio", "symbols": [SYMBOL],
              "from_date": FIRST, "through_date": LAST, "unit": "手", "shares_per_unit": 100,
              "kind": "incremental", "scope": "docs/fixtures remap only", "r4_authorized": False}
    add("human_go", "sources/human_go.json", "bl2_human_go_v1", {"rows": [marker]})

    minute = inputs[raw_names["daqmt_1m"]]
    daily = inputs[raw_names["daqmt_1d"]]
    ths = {r["time"]: r for r in inputs[raw_names["ths_daily"]]}
    ratios = inputs[raw_names["ratio_table"]]
    wind = inputs[raw_names["wind_limits"]]
    require(tuple(r["date"] for r in ratios) == DATES, "ratio date coverage mismatch")
    require(tuple(r["stime"] for r in daily) == DATES, "daily date coverage mismatch")
    require(tuple(r["日期"].replace("-", "") for r in wind) == DATES, "Wind date coverage mismatch")
    sums = Counter()
    minute_by_key = {}
    for index, r in enumerate(minute):
        stamp = datetime.fromisoformat(r["datetime"])
        require(stamp.utcoffset() == timedelta(hours=8) and stamp.second == stamp.microsecond == 0,
                "invalid raw timestamp")
        require(int(stamp.timestamp() * 1000) == int(r["time"]), "raw time/datetime disagreement")
        key = stamp.strftime("%Y%m%d"), stamp.strftime("%H:%M")
        require(key[0] in DATES and key not in minute_by_key, "unexpected or duplicate raw minute")
        require(r["suspendFlag"] == "0", "changed/unknown suspendFlag requires fresh review, no inference")
        require(int(r["volume"]) >= 0, "negative raw volume")
        minute_by_key[key] = (index, r)
        sums[key[0]] += int(r["volume"])
    for d, ratio in zip(daily, ratios, strict=True):
        day = d["stime"]
        lots, shares = int(d["volume"]), Decimal(ths[day]["volume"])
        require(ths[day]["thscode"] == SYMBOL, "THS symbol mismatch")
        require(lots == int(ratio["daqmt_volume_lots"]) == sums[day] == int(ratio["sum_1m_volume_lots"])
                and ratio["sum_1m_equals_1d"] == "True", "incremental reconciliation mismatch")
        require(shares == Decimal(ratio["ths_volume_shares"]), "THS ratio shares mismatch")
        require(abs(Decimal(ratio["ratio_ths_per_daqmt"]) - shares / lots) < Decimal("1e-12"),
                "saved ratio mismatch")
        require(shares - lots * 100 == (-100 if day == "20251023" else 0), "changed cross-source discrepancy")
    evidence = {"basis": "cross_source_ratio", "unit_declaration": None, "declared_unit": "手",
                "shares_per_unit": 100, "kind": "incremental", "human_go": "human_go",
                "evidence_refs": {k: k for k in ("daqmt_1m", "daqmt_1d", "ths_daily", "ratio_table")},
                "finding": "8/9 daily ratios exactly 100; 20251023 THS is 100 shares less than daqmt*100; 9/9 full-day sum(1m)==1d, including 09:30 opening bars."}
    add("units_comparison", "sources/units_comparison.json", "bl2_cross_source_ratio_v1", {"rows": [evidence]})

    def proof(identity, filename, issuer, subject, refs, rows, limitations, complete=True):
        add(identity, filename, "bl2_proof_v1", {
            "issuer": issuer, "subject": subject, "source_refs": refs,
            "filter": {"symbols": [SYMBOL], "from_date": FIRST, "through_date": LAST,
                       "predicate": "603196.SH only; inclusive probe dates; exact source rows and bindings; " + subject},
            "result": {"complete": complete, "summary": "#1111 remapped " + subject + " draft; " +
                       ("saved observations checked offline" if complete else "BLOCKED: historical availability and rule approval not evidenced"),
                       "rows": rows}, "limitations": [NOTICE, *limitations]})

    proof("proof_units", "units.proof.json", "Human GO 2026-09-30 / #1111 cross-source evidence remap", "units",
          ["units_comparison", "human_go", "daqmt_1m", "daqmt_1d", "ths_daily", "ratio_table", "vendor_units_absence"],
          [{"source": "units_comparison", "row": 0, "observation": evidence["finding"], "basis": "cross_source_ratio",
            "binding": {"source": MINUTE_SOURCE, "column": "volume", "kind": "incremental", "unit": "lots", "shares_per_unit": 100}}],
          ["Human GO quote: " + GO_CUE,
           "Vendor-doc absence (#1111 verbatim finding): " + inputs["units.proof.json"]["vendor_doc_verbatim"]["finding"],
           "unit=手 is encoded as the existing loader enum lots; shares_per_unit=100 is explicit, not a default.",
           "20251023 differs by 100 shares; this exception is not a general vendor declaration or amount/(close*volume) heuristic.",
           "minute_603196 is an intended host source ID. Actual lake bytes, coverage and identity still require separate host binding; daqmt exports are not the configured lake."])

    inst_rows = []
    inst_bindings = []
    inst_inputs = ["sse_rule", "upstream_instruments", "daqmt_1d", "wind_limits"]
    upstream = inputs["instruments.json"]
    # These consumer labels apply only to the pinned upstream convention.
    require(upstream["board"] == "sse_main_a", "unsupported upstream instrument board")
    require(upstream.get("price_domain") is None, "upstream instrument price_domain requires fresh review")
    require(tuple(r["date"] for r in upstream["rows"]) == DATES, "instrument date coverage mismatch")
    for i, raw in enumerate(upstream["rows"]):
        require(raw.get("price_domain") is None, "upstream instrument row price_domain requires fresh review")
        require(raw["symbol"] == wind[i]["Wind代码"] == SYMBOL, "instrument symbol mismatch")
        require(Decimal(str(raw["reference_price"])) == Decimal(daily[i]["preClose"]), "reference/preClose mismatch")
        for field, column in (("limit_up", "涨停价"), ("limit_down", "跌停价")):
            require(Decimal(str(raw[field])) == Decimal(wind[i][column]), "Wind/upstream limit mismatch")
        day = datetime.strptime(raw["date"], "%Y%m%d").date().isoformat()
        facts = {"symbol": SYMBOL, "trade_date": day, "board": "main", "price_domain": "raw",
                 **{k: format(Decimal(str(raw[k])), ".2f") for k in ("tick_size", "reference_price", "limit_down", "limit_up")},
                 "lot_size": raw["lot_size"]}
        binding = {"facts": facts, "effective_from": day, "effective_through": day,
                   "available_at": None, "ordinary_listing": None, "origin": "approved_derivation",
                   "derivation": {"inputs": inst_inputs, "approved_rule_version": upstream["approved_rule_version"]}}
        inst_bindings.append(binding)
        inst_rows.append({**binding, "proofs": ["proof_instruments_sse"],
                          "derivation": {**binding["derivation"], "independent_verification": ["proof_instruments_wind"]}})
    add("instruments", "instruments.json", "bl2_instruments_v1", {"rows": inst_rows})
    for identity, filename, issuer, source in (
        ("proof_instruments_sse", "instruments.proof.json", "上海证券交易所 / #1111 rule excerpt (unsigned remapped draft)", "sse_rule"),
        ("proof_instruments_wind", "instruments.wind.proof.json", "Wind 万得 via kimi-datasource / #1111 daily limits (remapped draft)", "wind_limits"),
    ):
        proof(identity, filename, issuer, "instruments", [*inst_inputs, "daqmt_detail"],
              [{"source": source, "row": 0 if source == "sse_rule" else i,
                "observation": "#1111 supplied values copied; daqmt daily preClose checked; Wind limit_up/down match. No default band computed.",
                "basis": "approved_derivation", "binding": b} for i, b in enumerate(inst_bindings)],
              ["available_at and ordinary_listing remain null: #1111 lacks historical availability and authoritative ordinary-listing coverage. No 09:00 availability invented.",
               "approved_rule_version is copied from #1111, not a new approval. SSE archive, rounding/exception applicability and independent approval review remain required.",
               "Issuer identifies the evidence source, not a signature or host certification; complete=false preserves this review gate.",
               "Wind verifies 18/18 daily limit values; daqmt instrument_detail is a 20260930 corroborating snapshot only, not the second historical issuer."], complete=False)

    zero_keys = {(r["date"], r["hm"]) for r in inputs[raw_names["zero_volume"]]}
    actual_zero = {key for key, (_, row) in minute_by_key.items() if int(row["volume"]) == 0}
    require(len(zero_keys) == len(inputs[raw_names["zero_volume"]]) == 62 and zero_keys == actual_zero,
            "zero-volume raw census mismatch")
    require(all(r["volume"] == "0" and r["suspendFlag"] == "0" for r in inputs[raw_names["zero_volume"]]),
            "zero-volume status mismatch")
    statuses, observations, opening = [], [], []
    expected_keys = set()
    upstream_grid = {(r["date"], r["minute"]): r for r in inputs["status.json"]["minute_grid"]}
    for day in DATES:
        for hour in (9, 13):
            base = datetime.fromisoformat(datetime.strptime(day, "%Y%m%d").date().isoformat() +
                                         ("T09:30:00+08:00" if hour == 9 else "T13:00:00+08:00"))
            for offset in range(120):
                start, end = base + timedelta(minutes=offset), base + timedelta(minutes=offset + 1)
                key = day, end.strftime("%H:%M")
                expected_keys.add(key)
                require(key in minute_by_key, f"missing raw minute needs independent review: {key}")
                index, raw = minute_by_key[key]
                require(upstream_grid[key]["status"] == "trading" and upstream_grid[key]["grid_role"] == "continuous",
                        "upstream status grid mismatch")
                reason = "daqmt bar present; suspendFlag=0 (正常); fill_data=True"
                if key in zero_keys:
                    reason += "; zero volume means no trades, not halt or missing"
                binding = {"symbol": SYMBOL, "start": start.isoformat(), "end": end.isoformat(),
                           "missing": False, "halted": False, "reason": reason,
                           "issuer": "国金 QMT (迅投数据通道) / daqmt suspendFlag"}
                statuses.append({**binding, "proofs": ["proof_status"]})
                observations.append({"source": "daqmt_1m", "row": index, "observation": reason,
                                     "basis": "explicit_status", "binding": binding})
        key = day, "09:30"
        require(key in minute_by_key and upstream_grid[key]["grid_role"] == "opening_auction", "opening evidence missing")
        index, raw = minute_by_key[key]
        opening.append({"source": "daqmt_1m", "row": index, "datetime": raw["datetime"],
                        "grid_role": "opening_auction", "volume": raw["volume"], "suspendFlag": raw["suspendFlag"]})
    require(set(minute_by_key) == expected_keys | {(d, "09:30") for d in DATES}, "unexpected raw grid rows")
    require(len(statuses) == 2160 and len(minute) == 2169, "canonical grid size mismatch")
    add("status", "status.json", "bl2_status_v1", {"rows": statuses})
    add("opening_auction", "sources/opening_auction.json", "bl2_opening_auction_evidence_v1", {"rows": opening})
    proof("proof_status", "status.proof.json", "国金 QMT (迅投数据通道) / #1111 suspendFlag remap", "status",
          ["daqmt_1m", "zero_volume", "vendor_status_semantics"], observations,
          ["Canonical 240 END labels per day: 09:31-11:30 and 13:01-15:00; closing auction labels remain in this source grid, without asserting continuous-auction execution semantics.",
           "Nine 09:30 opening_auction rows are separate evidence, excluded from status/session grid; included only in full-day volume reconciliation.",
           "62 zero-volume bars have explicit suspendFlag=0 and are trading, not missing/halted. No announcement silence used as evidence.",
           "fill_data=True: presence attests the exported vendor row, not an actual trade or unfilled raw feed. Missing lake rows cannot inherit this vendor-present assertion.",
           "suspendFlag semantics: 0 normal, 1 suspended, -1 resumption day. This pinned window is all 0; changed/missing flags fail remapping, never default to false."])

    outputs = {filename: encode(document) for filename, (_, document) in artifacts.items()}
    catalog = {"source_repository": pins["repository"], "source_commit": pins["commit"],
               "notice": NOTICE, "r4_authorized": False, "lake_verdict": "NOT_RUN",
               "unbound_minute_source": {"id": MINUTE_SOURCE, "sha256": None,
                                         "requirement": "Host must pin configured raw minute parquet; exports do not establish lake equivalence."},
               "unresolved": ["instrument historical available_at", "ordinary listing scope",
                              "SSE rule archive, approved applicability/rounding and independent approval review",
                              "host recipe, lake identity/coverage, remaining claims and fresh freeze"],
               "artifacts": [{"id": identity, "path": filename, "format": "json", "schema": doc["schema_version"],
                              "sha256": digest(outputs[filename])} for filename, (identity, doc) in artifacts.items()]}
    outputs["manifest.json"] = encode(catalog)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="Read-only copy of #1111 evidence tree")
    parser.add_argument("--human-go", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--check", action="store_true", help="Compare generated bytes to checked-in package")
    target.add_argument("--output-dir", type=Path, help="New offline output directory; existing paths rejected")
    args = parser.parse_args()
    outputs = build(args.source_dir, args.human_go)
    if args.check:
        for name, raw in outputs.items():
            require((HERE / name).read_bytes() == raw, f"remap output mismatch: {name}")
    else:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for name, raw in outputs.items():
            path = args.output_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(f"Offline remap checked: {len(outputs)} files; 9 instrument rows, 2160 status rows, 9 opening rows, 62 zero-volume rows. " + NOTICE)


if __name__ == "__main__":
    main()
