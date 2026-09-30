"""Offline remap of pinned #1111 evidence plus the 2026-09-30 host fills.

No lake, network, runner or R4. Uses only the standard library. Pinned LF
inputs are vendored for offline CI. The instruments host fill (rule archive,
approval record, available_at, ordinary_listing) is bound to pinned inputs in
inputs.json and HOST_R4_INSTRUMENTS_APPROVAL_20260930.md. The #1114 CAM
materials and HOST_R4_CAM_APPROVAL_20260930.md fill calendar/actions/marks
evidence only. The timing fill uses pinned MyQuant census/map/vendor excerpts;
r4_authorized stays false. The named wall-time encoding approval requires v5.
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
APPROVAL_NAME = "HOST_R4_INSTRUMENTS_APPROVAL_20260930.md"
APPROVAL_ID = "host_r4_instruments_approval_20260930"
RULE_FULLTEXT = "sse_rule_archive/sse_trading_rules_fulltext_retrieved_20260930.md"
RULE_EXCERPTS = "sse_rule_archive/clause_excerpts.md"
AVAILABLE_AT_SUFFIX = "T15:30:00+08:00"  # Human-approved convention (a): T-1 post-close archive.
CAM_DIR = "cam_host_materials"
CAM_APPROVAL_NAME = "HOST_R4_CAM_APPROVAL_20260930.md"
CAM_APPROVAL_ID = "host_r4_cam_approval_20260930"
CAM_GO_NAME = "HUMAN_GO_CAM.md"
CAM_LAKE_SHA256 = "58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083"
NEXT_BUY_DAY = "2025-11-05"
TIMING_DIR = "timing_host_materials"
TIMING_APPROVAL_NAME = "HOST_R4_TIMING_APPROVAL_20260930.md"
TIMING_APPROVAL_ID = "host_r4_timing_approval_20260930"
TIMING_GO_NAME = "HUMAN_GO_TIMING.md"
TIMING_CENSUS = "raw_materials/raw_lake_minute_census_603196SH_20251023_20251104.json"
TIMING_DOCS = "raw_materials/raw_excerpt_xtquant_docs.json"
TIMING_MAP = "HOST_MATERIALS_MAP_R4.md"
TIME_ENCODING = "epoch_ms_wall_shanghai_as_utc"
TIME_ENCODING_DIR = "time_encoding_host_materials"
TIME_ENCODING_APPROVAL_NAME = "HOST_R4_TIME_ENCODING_APPROVAL_20260930.md"
TIME_ENCODING_APPROVAL_ID = "host_r4_time_encoding_approval_20260930"
TIME_ENCODING_GO_NAME = "HUMAN_GO_TIME_ENCODING.md"


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


def read_inputs(source_dir, human_go, host_approval=None, host_cam_approval=None, host_timing_approval=None):
    pins = json.loads((HERE / "inputs.json").read_bytes())
    require(digest(human_go.read_bytes()) == pins["human_go_sha256"], "Human GO hash mismatch")
    if host_approval is None:
        host_approval = HERE / APPROVAL_NAME
    approval_raw = host_approval.read_bytes()
    require(digest(approval_raw) == pins["host_approval_sha256"], "host approval hash mismatch")
    cam_approval_raw = (host_cam_approval or HERE / CAM_APPROVAL_NAME).read_bytes()
    require(digest(cam_approval_raw) == pins["host_cam_approval_sha256"], "CAM host approval hash mismatch")
    require(CAM_APPROVAL_ID in cam_approval_raw.decode("utf-8"), "CAM host approval id marker missing")
    cam_go_raw = (HERE / CAM_GO_NAME).read_bytes()
    require(digest(cam_go_raw) == pins["human_go_cam_sha256"], "CAM Human GO hash mismatch")
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
    for name, hashes in pins["host_materials"]["files"].items():
        raw = (source_dir / name).read_bytes()
        require(digest(raw) == hashes["git_sha256"], f"input hash mismatch: {name}")
        inputs[name] = raw.decode("utf-8")
    inputs[APPROVAL_NAME] = approval_raw.decode("utf-8")
    for name, hashes in pins["cam_host_materials"]["files"].items():
        key = CAM_DIR + "/" + name
        raw = (source_dir / key).read_bytes()
        require(digest(raw) == hashes["git_sha256"], f"CAM input hash mismatch: {name}")
        inputs[key] = raw.decode("utf-8")
    inputs[CAM_APPROVAL_NAME] = cam_approval_raw.decode("utf-8")
    inputs[CAM_GO_NAME] = cam_go_raw.decode("utf-8")
    timing_approval_raw = (host_timing_approval or HERE / TIMING_APPROVAL_NAME).read_bytes()
    require(digest(timing_approval_raw) == pins["host_timing_approval_sha256"], "timing host approval hash mismatch")
    require(TIMING_APPROVAL_ID in timing_approval_raw.decode("utf-8"), "timing host approval id marker missing")
    timing_go_raw = (HERE / TIMING_GO_NAME).read_bytes()
    require(digest(timing_go_raw) == pins["human_go_timing_sha256"], "timing Human GO hash mismatch")
    for name, hashes in pins["timing_host_materials"]["files"].items():
        key = TIMING_DIR + "/" + name
        raw = (source_dir / key).read_bytes()
        require(digest(raw) == hashes["git_sha256"], f"timing input hash mismatch: {name}")
        inputs[key] = json.loads(raw, parse_float=Decimal)
    inputs[TIMING_APPROVAL_NAME] = timing_approval_raw.decode("utf-8")
    inputs[TIMING_GO_NAME] = timing_go_raw.decode("utf-8")
    for name, key in ((TIME_ENCODING_APPROVAL_NAME, "host_time_encoding_approval_sha256"),
                      (TIME_ENCODING_GO_NAME, "human_go_time_encoding_sha256")):
        raw = (HERE / name).read_bytes()
        require(digest(raw) == pins[key], f"time encoding approval/GO hash mismatch: {name}")
        inputs[name] = raw.decode("utf-8")
    require(TIME_ENCODING_APPROVAL_ID in inputs[TIME_ENCODING_APPROVAL_NAME],
            "time encoding approval id marker missing")
    for name, pin in pins[TIME_ENCODING_DIR]["files"].items():
        raw = (source_dir / TIME_ENCODING_DIR / name).read_bytes()
        require(digest(raw) == pin["git_sha256"], f"time encoding input hash mismatch: {name}")
        doc = json.loads(raw)
        require(doc["data"]["origin"]["sha256"] == pin["original_sha256"],
                f"time encoding original pin mismatch: {name}")
        inputs[TIME_ENCODING_DIR + "/" + name] = doc
    return pins, inputs


def extract_timing_materials(materials, originals):
    """Reproduce compact fixtures from pinned saved evidence, never a live lake."""
    for name, raw in originals.items():
        require(digest(raw) == materials["original_files"][name]["sha256"],
                f"timing original hash mismatch: {name}")

    def excerpt(name, rows, extraction, **metadata):
        return {"schema_version": "bl2_raw_excerpt_v1", "data": {
            "origin": {"repository": materials["repository"], "commit": materials["commit"],
                       "path": materials["directory"] + "/" + name,
                       **materials["original_files"][name]},
            "extraction": {"row_index": "zero-based excerpt rows array", **extraction},
            **metadata, "rows": rows}}

    census = json.loads(originals[TIMING_CENSUS], parse_float=Decimal)
    rows = [{"kind": key, "json_pointer": "/" + key, key: census[key]}
            for key in ("time_semantics", "grid_definition")]
    counters = ("window_rows", "grid_cells", "grid_missing", "grid_dup", "zero_volume_grid_cells")
    rows.append({"kind": "coverage", **{key: census[key] for key in counters}})
    for index, cell in enumerate(census["cells"]):
        if (cell["day"] == FIRST and cell["end_label_hm"] in
                ("0930", "0931", "1130", "1301", "1457", "1458", "1459", "1500")) or (
                cell["day"] == LAST and cell["end_label_hm"] == "1500"):
            rows.append({"kind": "boundary_sample", "source_cell_index": index, **cell})
    result = {"timing_lake_census.json": excerpt(TIMING_CENSUS, rows,
        {"method": "Copy semantics, grid, counters and selected cells; source_cell_index indexes original /cells; "
                   "row_idx is the saved zero-based absolute parquet row, not an excerpt index."},
        source_identity_note=census["source"],
        limitation="Saved census statement and boundary samples only; no local lake identity/coverage verification. "
                   "Full original census pinned separately. The time_encoding_approval binds these saved labels "
                   "to the R4f partition hash, time:int64 and approved Shanghai wall encoding/window.")}

    docs = json.loads(originals[TIMING_DOCS])
    rows = []
    for index, selected in ((0, (1219, 1222, 1226, 1227)), (1, (4088, 4103, 4104, 4105, 4106, 4107, 4108))):
        entry = docs["rows"][index]
        for line in entry["lines"]:
            if line["line"] in selected:
                rows.append({"source_row_index": index, "excerpt_id": entry["excerpt_id"],
                             "original": entry["original"], "original_sha256": entry["original_sha256"], **line})
    result["timing_xtquant_docs.json"] = excerpt(TIMING_DOCS, rows,
        {"method": "Selected K-line time/close/volume and fill_data lines; preserve original vendor line numbers."},
        collected_at=docs["collected_at"], xtquant_version=docs["xtquant_version"],
        limitation="Timestamp field corroboration only, not an independent vendor END or latency declaration. "
                   "fill_data zero-fill is not event-time proof; collected_at is file collection, not event time.")
    lines = originals[TIMING_MAP].decode("utf-8").splitlines()
    stop = next(index for index, line in enumerate(lines) if line.startswith("### 1.2 "))
    result["timing_materials_map.json"] = excerpt(TIMING_MAP,
        [{"line": index, "text": line} for index, line in enumerate(lines[:stop])],
        {"method": "UTF-8 lines from header through section 1.1, excluding section 1.2; original zero-based line retained."},
        limitation="Original host-assist DRAFT and time wording preserved. Section 1.1 supplies END semantics. "
                   "Its example labels 1761211800000 as Shanghai 09:30, but the existing epoch_ms decoder "
                   "gives 17:30+08:00. The separate time_encoding_approval binds this wall intent to the named "
                   "encoding and R4f source/window; fresh v5 host freeze still required, no numeric offset correction.")
    return result


def add_timing_package(pins, inputs, add, md_excerpt):
    """Independent timing observations; no consumer role or recipe placeholder."""
    materials = pins["timing_host_materials"]
    excerpts = {}
    for name, pin in materials["files"].items():
        doc = inputs[TIMING_DIR + "/" + name]
        original = pin["original_file"]
        require(doc["schema_version"] == "bl2_raw_excerpt_v1" and doc["data"]["origin"] == {
            "repository": materials["repository"], "commit": materials["commit"],
            "path": materials["directory"] + "/" + original, **materials["original_files"][original]},
            f"timing excerpt origin mismatch: {name}")
        identity = Path(name).stem
        excerpts[identity] = doc["data"]["rows"]
        add(identity, "sources/" + name, doc["schema_version"], doc["data"])
    for identity, name, hash_key in (
        ("host_timing_approval", TIMING_APPROVAL_NAME, "host_timing_approval_sha256"),
        ("human_go_timing", TIMING_GO_NAME, "human_go_timing_sha256"),
    ):
        excerpts[identity] = md_excerpt(identity, name,
            {"repository": "baiyibing/MyQuant-backtrader",
             "path": "docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/" + name,
             "sha256": pins[hash_key]},
            limitation="Human「开修」timing packs only. Merge awaits baiyibing countersign; "
                       "not「开 R4」; r4_authorized=false; production_C=frozen.")
    census = excerpts["timing_lake_census"]
    require("END 标签" in census[0]["time_semantics"] and "[t-1min,t)" in census[0]["time_semantics"],
            "timing END semantics missing")
    require(tuple(census[2][key] for key in ("window_rows", "grid_cells", "grid_missing", "grid_dup"))
            == (2169, 2133, 0, 0), "timing census coverage mismatch")
    observations = [
        {"source": "timing_lake_census", "row": 0,
         "observation": "Pinned END declaration: label t covers [t-1min,t). Under §3.1 the completed "
                        "bar close/volume are available at bucket.end=t (availability=bucket_end), never "
                        "at bucket.start; completed_bucket_available_at_end is historical model availability."},
        {"source": "timing_lake_census", "row": 1,
         "observation": "237 tradable END labels/day: 09:31-11:30 and 13:01-14:57. 09:30/14:58/14:59/15:00 "
                        "remain off-grid; 15:00 is mark-legal, not an execution bucket."},
        {"source": "timing_lake_census", "row": 2,
         "observation": "Saved census: window_rows=2169, grid_cells=2133, grid_missing=0, grid_dup=0. "
                        "These saved counts do not bind configured lake bytes."},
    ]
    for index, sample in enumerate(census[3:], 3):
        label = sample["end_label_hm"]
        end = datetime.fromisoformat(sample["day"] + "T" + label[:2] + ":" + label[2:] + ":00+08:00")
        start = end - timedelta(minutes=1)
        observations.append({"source": "timing_lake_census", "row": index,
            "observation": f"{SYMBOL}: saved absolute parquet row={sample['row_idx']}; END label={end.isoformat()} "
                           f"maps to [{start.isoformat()},{end.isoformat()}); close/volume available at end "
                           f"under §3.1. in_tradable_grid={sample['in_tradable_grid']}; "
                           "off-grid samples remain excluded from execution; 15:00 may support a mark."})
    for identity, token, observation in (
        ("timing_materials_map", "1761211800000", "Pinned §1.1 labels 1761211800000 as Shanghai 09:30 and says "
         "'不是真 UTC'. Arithmetic check with the unchanged epoch_ms decoder instead gives "
         "2025-10-23T17:30:00+08:00. The pinned time_encoding_approval now binds the named Shanghai wall "
         "encoding to this source/column/window; END stays unchanged, with no numeric offset correction."),
        ("timing_xtquant_docs", "'time'", "Vendor K-line time is a timestamp field; corroborates the field mapping, "
         "not by itself END semantics or feed arrival latency."),
        ("timing_xtquant_docs", "amount、volume为0", "fill_data=True may fill missing volume/amount with zero and "
         "prices with prior close; this is a limitation, not evidence of event time or trades."),
        ("host_timing_approval", "completed_bucket_available_at_end", "Scoped approval of END and completed-bucket "
         "availability from census/map §1.1 and contract §3.1; merge countersign pending; no R4 authorization."),
        ("human_go_timing", "Cue:", "Human「开修」authorizes this timing packs-only repair of the R4d missing id."),
    ):
        row = next(i for i, item in enumerate(excerpts[identity]) if token in item["text"])
        observations.append({"source": identity, "row": row, "observation": observation})
    observations.append({"source": "opening_auction", "row": 0,
        "observation": "Existing #1111 2025-10-23 09:30 opening-auction observation corroborates the boundary; "
                       "it remains off-grid, and vendor export does not establish lake equivalence."})
    observations.append({"source": "daqmt_1m", "row": 0,
        "observation": "Pinned #1111 vendor export has time=1761183000000 and datetime=2025-10-23 "
                       "09:30:00+08:00, consistent with the existing epoch_ms decoder. This differs by "
                       "28800000 ms from the map's example; do not substitute vendor time for lake identity."})
    add("proof_timing", "timing.proof.json", "bl2_proof_v1", {
        "issuer": "Human GO 2026-09-30 / MyQuant pinned host-assist census and §1.1 timing host fill",
        "subject": "timing", "source_refs": [*excerpts, "opening_auction", "daqmt_1m"],
        "filter": {"symbols": [SYMBOL], "from_date": FIRST, "through_date": LAST,
                   "predicate": "END labels map to [t-1min,t); completed close/volume available at bucket.end=t; "
                                "saved Shanghai labels for bars and legal marks; named wall encoding bound by host approval"},
        "result": {"complete": True, "summary": "completed_bucket_available_at_end; independently pinned census "
                   "END statement and boundary samples, map §1.1, vendor field corroboration and scoped approval",
                   "rows": observations},
        "limitations": [NOTICE,
            "R4d remains BLOCKED/NOT_RUN as recorded; this remapped draft is not lake PASS. r4_authorized stays false.",
            "Historical completed-bar model only, not measured live feed arrival latency. Known availability later "
            "than bucket.end must reject adaptation; file collection time is not event time.",
            "fill_data zero-fill is not event-time proof or proof of actual trades. Vendor timestamp docs do not "
            "independently declare START/END; END comes from the pinned census and host materials map §1.1.",
            "Vendor export != lake identity; the saved census parquet hash is an identity note only. "
            "minute_603196 remains unbound; host must pin configured lake identity/coverage and freshly freeze.",
            "Proof covers bars/marks 2025-10-23..2025-11-04, not bars on next BUY calendar date 2025-11-05. "
            "A wider execution/mark window requires fresh coverage; calendar retains its separate next-day coverage.",
            "The old epoch_ms mapping still yields 17:30+08:00 and is not approved for this lake partition. "
            "Use epoch_ms_wall_shanghai_as_utc with the pinned source/column/window approval; v5 requires fresh "
            "implementation/recipe/attestation pins. No new lake run, Clock or economic-semantics change."]})


def add_time_encoding_package(pins, inputs, artifacts, add, md_excerpt):
    """Pin Human A, saved host reports and the exact mapping approved for v5."""
    for identity, name, key in (
        ("host_time_encoding_approval", TIME_ENCODING_APPROVAL_NAME, "host_time_encoding_approval_sha256"),
        ("human_go_time_encoding", TIME_ENCODING_GO_NAME, "human_go_time_encoding_sha256"),
    ):
        md_excerpt(identity, name, {"repository": "baiyibing/MyQuant-backtrader",
            "path": "docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/" + name,
            "sha256": pins[key]}, limitation="Named encoding implementation GO only; r4_authorized=false.")
    for name in pins[TIME_ENCODING_DIR]["files"]:
        doc = inputs[TIME_ENCODING_DIR + "/" + name]
        add(Path(name).stem, "sources/" + name, doc["schema_version"], doc["data"])
    material_ids = {"host_time_encoding_approval", "human_go_time_encoding", "time_encoding_advice",
                    "time_encoding_r4f", "timing_materials_map", "timing_lake_census"}
    evidence_refs = {identity: digest(encode(doc)) for identity, doc in artifacts.values() if identity in material_ids}
    require(set(evidence_refs) == material_ids, "missing time encoding materials")
    approval = {
        "approval_id": TIME_ENCODING_APPROVAL_ID,
        "approval_document_sha256": pins["host_time_encoding_approval_sha256"],
        "human_go_document_sha256": pins["human_go_time_encoding_sha256"],
        "r4_authorized": False,
        "decode_rule": "UTC integer milliseconds construction; replace(tzinfo=None).replace(tzinfo=Asia/Shanghai); no offset arithmetic",
        "binding": {"source": MINUTE_SOURCE, "source_sha256": CAM_LAKE_SHA256,
                    "column": "time", "source_type": "int64", "symbol": SYMBOL,
                    "encoding": TIME_ENCODING, "timezone": "Asia/Shanghai", "label": "END",
                    "availability": "bucket_end", "from_date": FIRST, "through_date": LAST},
        "evidence_refs": evidence_refs,
    }
    add("time_encoding_approval", "sources/time_encoding_approval.json", "bl2_time_encoding_approval_v1",
        {"rows": [approval]})
    proof = artifacts["timing.proof.json"][1]["data"]
    proof["source_refs"] += sorted(material_ids - set(proof["source_refs"])) + ["time_encoding_approval"]
    proof["result"]["rows"].append({"source": "time_encoding_approval", "row": 0,
        "observation": "Human A GO: epoch_ms_wall_shanghai_as_utc for pinned minute_603196 time:int64, "
                       "603196.SH 2025-10-23..2025-11-04; UTC wall components stamped Asia/Shanghai, "
                       "no offset arithmetic. Saved Kimi census reports 2169 rows / zero violations; "
                       "HOST approval and all source materials are byte-bound. Fresh v5 freeze required."})
    proof["result"]["summary"] += "; epoch_ms_wall_shanghai_as_utc bound to source/column/window and Human A HOST approval"


def add_cam_packages(pins, inputs, add, md_excerpt):
    """Saved #1114 observations and approved scope; never bind or open a lake."""
    materials = pins["cam_host_materials"]

    def origin(name):
        return {"repository": materials["repository"], "commit": materials["commit"],
                "path": materials["directory"] + "/" + name, **materials["files"][name]}

    excerpts = {}
    for identity, name in (
        ("cam_sse_holidays", "calendar/sse_holiday_notices_2025.md"),
        ("cam_pmc_calendar", "calendar/pmc_sse_calendar_20250901_20251231.txt"),
        ("cam_calendar_cross_check", "calendar/calendar_cross_check.md"),
        ("cam_cninfo_analysis", "actions/cninfo_603196_announcements_analysis.md"),
        ("cam_ex_date_index", "actions/ex_date_index_local_check.md"),
        ("cam_preclose_chain", "actions/preclose_chain_no_ex_adjustment.md"),
        ("cam_marks_substrate", "marks/minute_lake_marks_substrate.md"),
    ):
        excerpts[identity] = md_excerpt(
            identity, CAM_DIR + "/" + name, origin(name),
            limitation="Pinned #1114 saved material; original DRAFT wording preserved. "
                       "Human's four-cell approval is recorded separately in host_cam_approval. "
                       "No local market-source retrieval or lake verification.")
    for identity, name, hash_key in (
        ("host_cam_approval", CAM_APPROVAL_NAME, "host_cam_approval_sha256"),
        ("human_go_cam", CAM_GO_NAME, "human_go_cam_sha256"),
    ):
        excerpts[identity] = md_excerpt(
            identity, name,
            {"repository": "baiyibing/MyQuant-backtrader",
             "path": "docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/" + name,
             "sha256": pins[hash_key]},
            limitation="Human「四格全批，开 packs」; packs only. Approval record awaits baiyibing "
                       "countersign before merge; r4_authorized=false.")

    # Preserve announcement order and page metadata, while keeping each proof
    # small. The complete raw responses are independently byte-pinned fixtures.
    announcement_ids = []
    for page in (1, 2, 3):
        name = f"actions/cninfo_603196_announcements_p{page}.json"
        raw = json.loads(inputs[CAM_DIR + "/" + name], parse_float=Decimal)
        rows = raw["announcements"]
        require(raw["totalAnnouncement"] == 77 and len(rows) == (17 if page == 3 else 30),
                "CAM cninfo page count mismatch")
        require(all(row["secCode"] == "603196" for row in rows), "CAM cninfo symbol mismatch")
        columns = ("secCode", "secName", "orgId", "announcementId", "announcementTitle",
                   "announcementTime", "adjunctUrl")
        identity = f"cam_cninfo_p{page}"
        add(identity, "sources/" + identity + ".json", "bl2_raw_excerpt_v1", {
            "origin": origin(name),
            "extraction": {"json_pointer": "/announcements", "columns": list(columns),
                           "row_index": "zero-based within this page's announcements array; order unchanged"},
            "page_metadata": {key: raw[key] for key in ("totalAnnouncement", "totalRecordNum", "totalpages", "hasMore")},
            "limitation": "Saved title metadata only, not PDF full text. The API reports totalpages=2 "
                          "on all three archived responses; preserve this metadata. Archived row counts "
                          "30+30+17 and 77 unique announcement IDs reconcile totalAnnouncement=77; "
                          "completeness is the Human-approved multi-source statement.",
            "rows": [{key: row[key] for key in columns} for row in rows]})
        announcement_ids.extend(row["announcementId"] for row in rows)
    require(len(set(announcement_ids)) == len(announcement_ids) == 77, "CAM cninfo duplicate/missing announcements")

    def proof(subject, conclusion, refs, rows, limitations, through_date=LAST):
        add("proof_" + subject, subject + ".proof.json", "bl2_proof_v1", {
            "issuer": "Human GO 2026-09-30 / #1114 CAM saved-material host fill",
            "subject": subject, "source_refs": [*refs, "host_cam_approval", "human_go_cam"],
            "filter": {"symbols": [SYMBOL], "from_date": FIRST, "through_date": through_date,
                       "predicate": conclusion + "; approved economic scope; pinned source rows/line indexes"},
            "result": {"complete": True, "summary": conclusion + "; Human「四格全批，开 packs」; "
                       "saved #1114 observations plus the scoped coverage approval", "rows": rows},
            "limitations": [NOTICE, *limitations]})

    date_lines = [(row["line"], row["text"]) for row in excerpts["cam_pmc_calendar"]
                  if len(row["text"]) == 8 and row["text"].isdigit()]
    all_dates = [datetime.strptime(value, "%Y%m%d").date().isoformat() for _, value in date_lines]
    require(len(all_dates) == 82 and all_dates == sorted(set(all_dates)), "CAM PMC calendar order/coverage mismatch")
    selected_dates = [(line, day) for (line, _), day in zip(date_lines, all_dates, strict=True)
                      if FIRST <= day <= NEXT_BUY_DAY]
    dates = [day for _, day in selected_dates]
    require(dates == [datetime.strptime(day, "%Y%m%d").date().isoformat() for day in DATES] + [NEXT_BUY_DAY],
            "CAM approved calendar subset mismatch")
    add("calendar", "calendar.json", "bl2_calendar_v1", {"trading_dates": dates})
    proof("calendar", "complete_trading_calendar",
          ["cam_pmc_calendar", "cam_sse_holidays", "cam_calendar_cross_check"],
          [{"source": "cam_pmc_calendar", "row": line,
            "observation": day + ": PMC/SSE trading date; first_day=2025-10-23; "
                           "2025-11-05 included as the next possible BUY trading date."}
           for line, day in selected_dates],
          ["SSE notices are the independent holiday anchor; PMC supplies the ordered dates. "
           "The census is corroboration only; dates are not inferred from bar presence or weekdays.",
           "Human confirms no initial lot acquired before first_day=2025-10-23; a changed recipe "
           "economic window requires fresh calendar/actions coverage review."], through_date=NEXT_BUY_DAY)

    add("actions", "actions.json", "bl2_actions_v1", {
        "symbols": [SYMBOL], "from_date": FIRST, "through_date": LAST,
        "complete": True, "events": [], "proofs": ["proof_actions"]})
    proof("actions", "complete_no_company_actions",
          ["cam_cninfo_analysis", "cam_cninfo_p1", "cam_cninfo_p2", "cam_cninfo_p3",
           "cam_ex_date_index", "cam_preclose_chain", "daqmt_1d", "ths_daily"], [],
          ["Contract §3.2: `ex_date_index/adj_factor` 的 hash 只证明身份；无行、因子未变或源缺失均不单独证明无事件。 "
           "Empty filter/file presence alone is not no-events evidence.",
           "Human approves complete economic-window coverage [2025-10-23,2025-11-04]: ex_date_index "
           "zero matches + cninfo 77 announcement titles with zero action-keyword matches + preClose "
           "chain 9/9 without adjustment + adj_factor constant 1.0. result.rows=[] is the saved event "
           "filter result; supporting observations remain in source_refs, not in actions proof rows.",
           "cninfo search window is 2025-06-01..2025-12-31; this is not an empty-events claim for that "
           "whole interval. Titles/window review only; no PDF full-text verification. API totalpages=2 "
           "is retained despite three responses (30+30+17 unique IDs); see page excerpts.",
           "The local ex_date_index e8fe70ce snapshot differs from the R3 93c264ed pin. The saved check "
           "corroborates rather than replaces it; adj_factor and unchanged preClose are supporting "
           "observations, not independent proof of event absence or of configured lake coverage."])

    # Read explicit prices/absolute rows from the substrate; do not create an
    # interpolated intraday point from a row range or a previous price.
    substrate = inputs[CAM_DIR + "/marks/minute_lake_marks_substrate.md"]
    require(CAM_LAKE_SHA256 in substrate, "CAM marks parquet identity note mismatch")
    mark_table = []
    for row in excerpts["cam_marks_substrate"]:
        if row["text"].startswith("| 2025-"):
            cells = [cell.strip() for cell in row["text"].strip("|").split("|")]
            day, first_row, last_row, close, volume, _ = cells
            mark_table.append((day, int(first_row), int(last_row), close, int(volume), row["line"]))
    require(tuple(day.replace("-", "") for day, *_ in mark_table) == DATES, "CAM marks date coverage mismatch")
    daily = inputs["raw/daqmt_603196_1d_none.csv"]
    for i, (day, first_row, last_row, close, volume, _) in enumerate(mark_table):
        require(last_row - first_row + 1 == 241 and volume >= 0, "CAM marks row range mismatch")
        require(i == 0 or first_row == mark_table[i - 1][2] + 1, "CAM marks noncontiguous row ranges")
        require(Decimal(close) == Decimal(daily[i]["close"]), "CAM marks/daily close mismatch")
    require(mark_table[0][1:4] == (46513, 46753, "23.89")
            and mark_table[-1][2:4] == (48681, "22.96"), "CAM approved mark row/price mismatch")
    grid, observations = [], []
    for mark_id, (day, _, abs_row, close, _, line) in (
        ("spot_20251023_close", mark_table[0]), ("final", mark_table[-1]),
    ):
        event = day + "T15:00:00+08:00"
        grid.append({"mark_id": mark_id, "event_time": event, "available_at": event, "price_domain": "raw",
                     "prices": [{"symbol": SYMBOL, "price": close, "source": MINUTE_SOURCE,
                                 "abs_row": abs_row, "time_column": "time", "price_column": "close",
                                 "substrate_source": "cam_marks_substrate", "substrate_row": line}]})
        observations.append({"source": "cam_marks_substrate", "row": line,
                             "observation": f"{mark_id}: {SYMBOL}; event_time={event}; available_at=event_time={event}; "
                                            f"zero-based absolute parquet row={abs_row}, time column=time, "
                                            f"price column=close, raw close={close}; saved parquet SHA-256 "
                                            f"{CAM_LAKE_SHA256}. Substrate records row-table/census agreement; "
                                            "configured minute source remains unbound."})
    add("marks", "marks.json", "bl2_marks_grid_v1", {
        "subject": "marks", "conclusion": "raw_contemporaneous_grid",
        "purpose": "Host-facing approved grid document; not a loader role or a frozen recipe.",
        "approval_id": CAM_APPROVAL_ID, "transform_version": "bl2_source_transform_v5",
        "time": {"encoding": TIME_ENCODING, "timezone": "Asia/Shanghai", "label": "END"},
        "source_identity_note": {"source": MINUTE_SOURCE, "sha256": CAM_LAKE_SHA256,
                                 "binding_status": "unbound_minute_source",
                                 "note": "Identity recorded in pinned #1114 substrate; parquet/census not read here. "
                                         "Exports do not establish lake equivalence; host must bind configured "
                                         "parquet identity/coverage and preserve its time/close mapping."},
        "proofs": ["proof_marks"], "rows": grid})
    proof("marks", "raw_contemporaneous_grid", ["cam_marks_substrate", "daqmt_1d", "ths_daily"], observations,
          ["Human approves the candidate grid; this implementation selects the first-day explicit close "
           "as the independent spot-check and the required final close. Both are direct substrate rows.",
           "available_at=event_time is the approved minute-label convention. The saved substrate describes "
           "parquet pin + row table + census agreement for legal 15:00 marks; no local parquet or census "
           "verification is claimed. These marks add no execution buckets.",
           "Host must bind the configured minute source, preserve the loader's time/close mapping, "
           "register this approved grid and re-freeze the scoped attestation. The grid document and "
           "source exports do not establish lake equivalence or lake PASS."])


def build(source_dir, human_go, host_approval=None, host_cam_approval=None, host_timing_approval=None):
    pins, inputs = read_inputs(source_dir, human_go, host_approval, host_cam_approval, host_timing_approval)
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
    def md_excerpt(identity, name, origin, **metadata):
        rows = [{"line": index, "text": line} for index, line in enumerate(inputs[name].splitlines())]
        add(identity, "sources/" + identity + ".json", "bl2_raw_excerpt_v1",
            {"origin": origin, "extraction": {"method": "UTF-8 markdown lines, order unchanged, one row per line",
                                              "row_index": "zero-based line number"},
             **metadata, "rows": rows})
        return rows

    excerpt("daqmt_detail", "raw/daqmt_603196_instrument_detail.json",
            [inputs["raw/daqmt_603196_instrument_detail.json"]],
            limitation="2026-09-30 snapshot; corroboration only, not historical limits or listing status.")
    materials = pins["host_materials"]
    require(APPROVAL_ID in inputs[APPROVAL_NAME], "host approval id marker missing")
    sse_rows = md_excerpt(
        "sse_rule", RULE_FULLTEXT,
        {"repository": materials["repository"], "commit": materials["commit"],
         "path": materials["directory"] + "/" + RULE_FULLTEXT, **materials["files"][RULE_FULLTEXT]},
        limitation="Retrieved SSE trading rules fulltext archive (2013 base + 2023-04-18 revision; "
                   "window-effective per clause_excerpts section D). Supersedes the #1111 URL/paraphrase "
                   "excerpt. Applicability, rounding and exception review recorded in host_approval.")
    clause_line = {}
    for clause in ("3.4.7", "3.4.11", "3.4.13", "3.4.14", "3.7.2", "4.1.3"):
        matches = [r["line"] for r in sse_rows if r["text"].startswith(clause + " ")]
        require(matches, f"clause {clause} missing from pinned rule archive")
        clause_line[clause] = matches[0]
    md_excerpt("clause_excerpts", RULE_EXCERPTS,
               {"repository": materials["repository"], "commit": materials["commit"],
                "path": materials["directory"] + "/" + RULE_EXCERPTS, **materials["files"][RULE_EXCERPTS]},
               limitation="Clause excerpts and effective-interval delimitation quoted from the archived "
                          "fulltext; 9/9 Decimal ROUND_HALF_UP recomputation recorded. Approved via host_approval.")
    md_excerpt("host_approval", APPROVAL_NAME,
               {"repository": "baiyibing/MyQuant-backtrader",
                "path": "docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages/" + APPROVAL_NAME,
                "sha256": pins["host_approval_sha256"],
                "note": "Created by the instruments host-fill PR; pinned by bytes SHA-256 in inputs.json."},
               limitation="Human decision record of the 2026-09-30 session; awaits baiyibing countersign "
                          "before merge. r4_authorized is not flipped by this record.")
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

    def proof(identity, filename, issuer, subject, refs, rows, limitations, complete=True, summary=None):
        if summary is None:
            summary = "#1111 remapped " + subject + " draft; " + (
                "saved observations checked offline" if complete
                else "BLOCKED: historical availability and rule approval not evidenced")
        add(identity, filename, "bl2_proof_v1", {
            "issuer": issuer, "subject": subject, "source_refs": refs,
            "filter": {"symbols": [SYMBOL], "from_date": FIRST, "through_date": LAST,
                       "predicate": "603196.SH only; inclusive probe dates; exact source rows and bindings; " + subject},
            "result": {"complete": complete, "summary": summary, "rows": rows},
            "limitations": [NOTICE, *limitations]})

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
    inst_inputs = ["sse_rule", "clause_excerpts", "host_approval", "upstream_instruments",
                   "daqmt_1d", "wind_limits", "ths_daily"]
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
        # Host-approved convention (a): T-1 trading day post-close archive (host_approval section 1).
        prev = DATES[i - 1] if i else "20251022"
        require(prev in ths, "T-1 archive row missing from pinned daily sources")
        if i:
            require(Decimal(daily[i - 1]["close"]) == Decimal(daily[i]["preClose"]),
                    "T-1 archive close chain mismatch")
        else:
            require(Decimal(ths[prev]["close"]) == Decimal(daily[0]["preClose"]),
                    "first T-1 archive close mismatch")
        available = datetime.strptime(prev, "%Y%m%d").date().isoformat() + AVAILABLE_AT_SUFFIX
        day = datetime.strptime(raw["date"], "%Y%m%d").date().isoformat()
        facts = {"symbol": SYMBOL, "trade_date": day, "board": "main", "price_domain": "raw",
                 **{k: format(Decimal(str(raw[k])), ".2f") for k in ("tick_size", "reference_price", "limit_down", "limit_up")},
                 "lot_size": raw["lot_size"]}
        binding = {"facts": facts, "effective_from": day, "effective_through": day,
                   "available_at": available, "ordinary_listing": True, "origin": "approved_derivation",
                   "derivation": {"inputs": inst_inputs, "approved_rule_version": upstream["approved_rule_version"]}}
        inst_bindings.append(binding)
        inst_rows.append({**binding, "proofs": ["proof_instruments_sse"],
                          "derivation": {**binding["derivation"], "independent_verification": ["proof_instruments_wind"]}})
    add("instruments", "instruments.json", "bl2_instruments_v1", {"rows": inst_rows})
    inst_observation = ("Host fill 2026-09-30 per host_approval: #1111 values checked against the daqmt "
                        "preClose chain, Wind 18/18 limits and archived SSE clauses; available_at is the "
                        "approved T-1 post-close archive convention; ordinary_listing approved. "
                        "No default band computed.")
    inst_limitations = [
        "available_at is the Human-approved T-1 post-close archive convention (host_approval section 1): "
        "SSE rule 4.1.3 close at 15:00 and 3.7.2 in-window rule timepoint 15:30; anchored to pinned daily "
        "archive rows, not a vendor publication timestamp. The 2026-07-06 after-hours rule change postdates "
        "the window and is not an anchor.",
        "ordinary_listing approved by host (host_approval section 2): window non-ST, zero corporate actions, "
        "no 3.4.13 first-day exception; 9/9 values consistent with the 10% formula and tick 0.01.",
        "approved_rule_version sse_main_board_limit_pct10_tick0.01_lot100_v2023 approved by baiyibing "
        "2026-09-30 (host_approval section 3); archive = 2013 base + 2023-04-18 revision; Decimal "
        "ROUND_HALF_UP recomputed 9/9 (clause_excerpts section C).",
        "Issuer identifies the evidence source, not a signature or host certification; the approval record "
        "awaits baiyibing countersign before merge.",
        "Wind verifies 18/18 daily limit values; daqmt instrument_detail is a 20260930 corroborating "
        "snapshot only, not the second historical issuer."]
    for identity, filename, issuer, source in (
        ("proof_instruments_sse", "instruments.proof.json",
         "上海证券交易所交易规则存档 (2023 修订) / host fill 2026-09-30 (remapped draft)", "sse_rule"),
        ("proof_instruments_wind", "instruments.wind.proof.json",
         "Wind 万得 via kimi-datasource / #1111 daily limits (host fill 2026-09-30, remapped draft)", "wind_limits"),
    ):
        proof(identity, filename, issuer, "instruments", [*inst_inputs, "daqmt_detail"],
              [{"source": source, "row": clause_line["3.4.13"] if source == "sse_rule" else i,
                "observation": inst_observation,
                "basis": "approved_derivation", "binding": b} for i, b in enumerate(inst_bindings)],
              inst_limitations,
              summary="#1111 remapped instruments draft; host fill 2026-09-30 (rule archive/approval, "
                      "available_at, ordinary_listing) checked offline")

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

    add_cam_packages(pins, inputs, add, md_excerpt)
    add_timing_package(pins, inputs, add, md_excerpt)
    add_time_encoding_package(pins, inputs, artifacts, add, md_excerpt)
    outputs = {filename: encode(document) for filename, (_, document) in artifacts.items()}
    catalog = {"source_repository": pins["repository"], "source_commit": pins["commit"],
               "notice": NOTICE, "r4_authorized": False, "lake_verdict": "NOT_RUN",
               "unbound_minute_source": {"id": MINUTE_SOURCE, "sha256": None,
                                         "requirement": "Host must pin configured raw minute parquet; exports do not establish lake equivalence."},
               "unresolved": ["account/commands and scoped attestation require host recipe review and registration",
                              "host recipe, lake identity/coverage and fresh freeze; r4_authorized stays false"],
               "transform_version": "bl2_source_transform_v5",
               "artifacts": [{"id": identity, "path": filename, "format": "json", "schema": doc["schema_version"],
                              "sha256": digest(outputs[filename])} for filename, (identity, doc) in artifacts.items()]}
    outputs["manifest.json"] = encode(catalog)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="Read-only staged #1111 tree plus #1112 sse_rule_archive/, #1114 cam_host_materials/ and timing_host_materials/")
    parser.add_argument("--human-go", type=Path, required=True)
    parser.add_argument("--host-approval", type=Path, default=None,
                        help="Host approval record; defaults to the checked-in package file")
    parser.add_argument("--host-cam-approval", type=Path, default=None,
                        help="CAM host approval record; defaults to the checked-in package file")
    parser.add_argument("--host-timing-approval", type=Path, default=None,
                        help="Timing host approval record; defaults to the checked-in package file")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--check", action="store_true", help="Compare generated bytes to checked-in package")
    target.add_argument("--output-dir", type=Path, help="New offline output directory; existing paths rejected")
    args = parser.parse_args()
    outputs = build(args.source_dir, args.human_go, args.host_approval, args.host_cam_approval, args.host_timing_approval)
    if args.check:
        for name, raw in outputs.items():
            require((HERE / name).read_bytes() == raw, f"remap output mismatch: {name}")
    else:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for name, raw in outputs.items():
            path = args.output_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(f"Offline remap checked: {len(outputs)} files; 9 host-filled instrument rows, 2160 status rows, "
          "9 opening rows, 62 zero-volume rows; CAM: 10 calendar dates, empty actions, 2 marks; "
          "timing: independent proof_timing and compact pinned observations. " + NOTICE)


if __name__ == "__main__":
    main()
