"""Offline evidence checks and fabricated acceptance tests; no lake or host run."""

import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from backtest.research.minute_orders_backend import source_loader
from backtest.research.minute_orders_backend.source_provenance import SourceContractError, sha256, strict_json
from tests.test_minute_orders_source_loader import SyntheticCase


PACK = Path(__file__).parents[1] / "docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages"
UPSTREAM = Path(__file__).parent / "fixtures/bl2_attestation_remap_upstream"


def document(name):
    return strict_json((PACK / name).read_bytes(), name)


@pytest.fixture
def ratio_case(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
    # Shift the fabricated inputs to one day inside the narrowly authorized window.
    def shift(value):
        if isinstance(value, str):
            for before, after in (("2026-09-25", "2025-10-22"), ("2026-09-28", "2025-10-23"),
                                  ("2026-09-29", "2025-10-24")):
                value = value.replace(before, after)
            return value
        if isinstance(value, list):
            return [shift(v) for v in value]
        if isinstance(value, dict):
            return {k: shift(v) for k, v in value.items()}
        return value
    case.rows, case.sidecars, case.recipe = map(shift, (case.rows, case.sidecars, case.recipe))
    case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
    case.attest_fabricated_bindings()
    proof = case.sidecars["proof_units"]
    proof["filter"].update(from_date="2025-10-23", through_date="2025-11-04")
    evidence = document("sources/units_comparison.json")["data"]
    sources = {"human_go": ("bl2_human_go_v1", document("sources/human_go.json")["data"]),
               "comparison": ("bl2_cross_source_ratio_v1", evidence)}
    for name in evidence["rows"][0]["evidence_refs"].values():
        sources[name] = ("bl2_raw_excerpt_v1", {"rows": [{"fixture_notice": "Fabricated " + name}]})
    for name, (schema, data) in sources.items():
        case.sidecars[name] = data
        case.recipe["sources"].insert(-1, {"id": name,
            "location": {"kind": "sidecar", "path": str(tmp_path / (name + ".json"))},
            "format": "json", "schema": schema, "sha256": ""})
    proof["source_refs"] = list(sources)
    proof["result"]["rows"][0].update(source="comparison", row=0, basis="cross_source_ratio")
    case.freeze()
    return case


def test_explicit_human_go_accepts_ratio_only_inside_probe_window(ratio_case):
    loaded = ratio_case.load()
    assert [b.volume_shares for b in loaded.run_input.buckets] == [100000, 50000]
    assert loaded.provenance.document()["transform"]["bars"][0]["volume_proofs"][0]["source"] == "comparison"
    assert not Path(ratio_case.recipe["parent"]).exists()


@pytest.mark.parametrize("change", ["basis", "no_go", "go_hash", "go_scope", "go_bool", "window", "symbol",
                                  "factor", "column", "no_ratio", "same_source", "mislabel", "bar_heuristic"])
def test_ratio_exception_cannot_relax_other_gates(ratio_case, change):
    case = ratio_case
    proof = case.sidecars["proof_units"]
    obs = proof["result"]["rows"][0]
    evidence = case.sidecars["comparison"]["rows"][0]
    marker = case.sidecars["human_go"]["rows"][0]
    if change == "basis":
        del obs["basis"]
    elif change == "no_go":
        proof["source_refs"].remove("human_go")
    elif change == "go_hash":
        marker["source_document_sha256"] = "0" * 64
    elif change == "go_scope":
        marker["through_date"] = "2025-11-05"
    elif change == "go_bool":
        marker["r4_authorized"] = 0
    elif change == "window":
        proof["filter"]["through_date"] = "2025-11-05"
    elif change == "symbol":
        proof["filter"]["symbols"] = ["000001.SZ"]
    elif change == "factor":
        obs["binding"]["shares_per_unit"] = 50
    elif change == "column":
        obs["binding"]["column"] = "close"
    elif change == "no_ratio":
        proof["source_refs"].remove("ratio_table")
    elif change == "same_source":
        evidence["evidence_refs"]["ths_daily"] = "daqmt_1d"
    elif change == "mislabel":
        obs["basis"] = "source_declaration"
    else:
        proof["source_refs"].append("bars")
    case.freeze()
    with pytest.raises(SourceContractError):
        case.load()
    assert not Path(case.recipe["parent"]).exists()


def test_declaration_label_without_declaration_fails(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
    del case.sidecars["observations"]["rows"][2]["unit_declaration"]
    case.freeze()
    with pytest.raises(SourceContractError, match="explicit matching unit declaration"):
        case.load()


EXPECTED_AVAILABLE_AT = {
    "2025-10-23": "2025-10-22T15:30:00+08:00", "2025-10-24": "2025-10-23T15:30:00+08:00",
    "2025-10-27": "2025-10-24T15:30:00+08:00", "2025-10-28": "2025-10-27T15:30:00+08:00",
    "2025-10-29": "2025-10-28T15:30:00+08:00", "2025-10-30": "2025-10-29T15:30:00+08:00",
    "2025-10-31": "2025-10-30T15:30:00+08:00", "2025-11-03": "2025-10-31T15:30:00+08:00",
    "2025-11-04": "2025-11-03T15:30:00+08:00",
}
DERIVATION_INPUTS = {"sse_rule", "clause_excerpts", "host_approval", "upstream_instruments",
                     "daqmt_1d", "wind_limits", "ths_daily"}


def test_checked_packages_hashes_bind_all_rows_and_record_instrument_host_fill():
    manifest = document("manifest.json")
    store = SimpleNamespace(data={}, specs={}, proof_bindings={})
    for spec in manifest["artifacts"]:
        raw = (PACK / spec["path"]).read_bytes()
        assert sha256(raw) == spec["sha256"]
        doc = strict_json(raw, spec["path"])
        assert doc["schema_version"] == spec["schema"]
        store.data[spec["id"]] = doc["data"]
        store.specs[spec["id"]] = {**spec, "location": {"kind": "sidecar"}}
    # Descriptor only for proof structure; never invokes the lake resolver.
    store.specs["minute_603196"] = {"schema": {"volume": "int64"}, "sha256": "0" * 64,
                                    "location": {"kind": "minute", "symbol": "603196.SH"}}
    for identity in ("proof_units", "proof_status", "proof_instruments_sse", "proof_instruments_wind",
                     "proof_calendar", "proof_actions", "proof_marks", "proof_timing"):
        store.proof_bindings[identity] = source_loader._proof(store.data[identity], store, identity)
    statuses = store.data["status"]["rows"]
    assert len(statuses) == len(store.proof_bindings["proof_status"]) == 2160
    assert set(Counter(r["start"][:10] for r in statuses).values()) == {240}
    assert len(Counter(r["start"][:10] for r in statuses)) == 9
    assert sum("zero volume" in r["reason"] for r in statuses) == 62
    for row in statuses:
        assert row["missing"] is row["halted"] is False
        assert datetime.fromisoformat(row["end"]) - datetime.fromisoformat(row["start"]) == timedelta(minutes=1)
        assert row["end"][11:16] != "09:30"
        source_loader._bound_refs(row["proofs"], store, "status",
                                  {k: v for k, v in row.items() if k != "proofs"}, "explicit_status")
        key = source_loader._binding_key("status", {k: v for k, v in row.items() if k != "proofs"})
        _, observation = store.proof_bindings["proof_status"][key]
        raw = store.data[observation["source"]]["rows"][observation["row"]]
        assert datetime.fromisoformat(raw["datetime"]).isoformat() == row["end"]
        assert raw["suspendFlag"] == "0"
        assert (int(raw["volume"]) == 0) == ("zero volume" in row["reason"])
    assert len(store.data["opening_auction"]["rows"]) == 9
    # Host fill 2026-09-30: both instruments proofs are complete, bound to every
    # derivation input and to the exact consumer rows; r4_authorized stays false.
    sse, wind = (store.data[p] for p in ("proof_instruments_sse", "proof_instruments_wind"))
    assert sse["issuer"] != wind["issuer"]
    assert DERIVATION_INPUTS <= set(sse["source_refs"]) and DERIVATION_INPUTS <= set(wind["source_refs"])
    assert manifest["r4_authorized"] is False
    assert not any(term in item for item in manifest["unresolved"]
                   for term in ("available_at", "ordinary listing", "SSE rule archive"))
    for index, row in enumerate(store.data["instruments"]["rows"]):
        assert row["available_at"] == EXPECTED_AVAILABLE_AT[row["facts"]["trade_date"]]
        assert row["ordinary_listing"] is True
        assert set(row["derivation"]["inputs"]) == DERIVATION_INPUTS
        binding = source_loader._instrument_binding(row)
        assert binding == sse["result"]["rows"][index]["binding"] == wind["result"]["rows"][index]["binding"]
        source_loader._bound_refs(["proof_instruments_sse"], store, "instruments", binding, "approved_derivation")
        source_loader._bound_refs(["proof_instruments_wind"], store, "instruments", binding, "approved_derivation")
    assert store.data["wind_limits"]["origin"]["host_sha256"] == "31f8461a4ae7aca352db35648c0d7c60e476597b259bfecc03c9807c9f3a048b"


@pytest.fixture
def remapper():
    spec = importlib.util.spec_from_file_location("remap", PACK / "remap.py")
    remap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(remap)
    return remap


@pytest.mark.parametrize("path", sorted(PACK.rglob("*.json")), ids=lambda p: str(p.relative_to(PACK)))
def test_every_package_json_passes_loader_strict_json(path):
    strict_json(path.read_bytes(), str(path))


@pytest.mark.parametrize("envelope", [False, True])
def test_remapper_encodes_nested_decimal_values_without_rounding(remapper, envelope):
    data = {"metadata": {"rate": 0.1}, "rows": [{
        "price": 17.84, "tick": 0.01, "small": 1e-7,
        "exact": Decimal("23.360000000000000001"), "scale": Decimal("1.2300"),
        "count": 100, "missing": None, "flag": False, "text": "unchanged",
    }]}
    original = {"schema_version": "bl2_raw_excerpt_v1", "data": data} if envelope else data
    result = strict_json(remapper.encode(original), "fabricated remap")
    result = result["data"] if envelope else result
    assert result == {"metadata": {"rate": "0.1"}, "rows": [{
        "price": "17.84", "tick": "0.01", "small": "0.0000001",
        "exact": "23.360000000000000001", "scale": "1.2300",
        "count": 100, "missing": None, "flag": False, "text": "unchanged",
    }]}
    assert type(result["rows"][0]["count"]) is int
    assert result["rows"][0]["flag"] is False
    assert type(data["rows"][0]["price"]) is float  # Encoding never edits the input.


@pytest.mark.parametrize("value", [float("nan"), float("inf"), Decimal("-Infinity")])
def test_remapper_rejects_nonfinite_source_numbers(remapper, value):
    with pytest.raises(ValueError, match="non-finite source number"):
        remapper.encode({"nested": [{"number": value}]})


def test_pinned_json_excerpts_preserve_source_decimals_and_unknowns(remapper):
    pins, inputs = remapper.read_inputs(UPSTREAM, PACK / "HUMAN_GO.md")
    raw_detail = inputs["raw/daqmt_603196_instrument_detail.json"]
    assert type(raw_detail["PreClose"]) is Decimal
    detail = document("sources/daqmt_detail.json")["data"]["rows"][0]
    assert detail["PreClose"] == "17.84"
    assert detail["PriceTick"] == "0.01"
    assert detail["IsTrading"] is None
    upstream = document("sources/upstream_instruments.json")["data"]
    assert upstream["upstream_metadata"]["inputs"]["limit_rate"] == "0.1"
    assert upstream["rows"][0]["reference_price"] == "23.36"
    assert upstream["rows"][0]["lot_size"] == 100
    assert document("manifest.json")["r4_authorized"] is False
    assert document("sources/human_go.json")["data"]["rows"][0]["r4_authorized"] is False
    # Host fill 2026-09-30 pins: OSkhQuant1.3 #1112 rule archive plus the approval record.
    assert pins["host_materials"]["commit"] == "d0edd384e9bd7fc0029b380e8850920539c46a95"
    approval = (PACK / "HOST_R4_INSTRUMENTS_APPROVAL_20260930.md").read_bytes()
    assert pins["host_approval_sha256"] == sha256(approval)
    assert "host_r4_instruments_approval_20260930" in inputs["HOST_R4_INSTRUMENTS_APPROVAL_20260930.md"]
    sse = document("sources/sse_rule.json")["data"]
    assert sse["origin"]["path"].endswith("sse_trading_rules_fulltext_retrieved_20260930.md")
    assert any(r["text"].startswith("3.4.13 ") for r in sse["rows"])
    clauses = document("sources/clause_excerpts.json")["data"]
    assert clauses["origin"]["git_sha256"] == "f70180cfb8a10c8294655084bd8e025018e4521420ee1676e48cca5068f88f7d"


def _register_real_sources(case, tmp_path):
    """Pin the real saved excerpts as sidecars; no host/lake run."""
    for spec in document("manifest.json")["artifacts"]:
        if spec["path"].startswith("sources/"):
            identity = spec["id"]
            case.sidecars[identity] = document(spec["path"])["data"]
            case.recipe["sources"].insert(-1, {
                "id": identity, "location": {"kind": "sidecar", "path": str(tmp_path / (identity + ".json"))},
                "format": "json", "schema": spec["schema"], "sha256": "",
            })


@pytest.mark.parametrize("proof_path", ["instruments.proof.json", "instruments.wind.proof.json"])
def test_remapped_complete_proofs_reject_fabricated_rows_outside_scope(tmp_path, monkeypatch, proof_path):
    case = SyntheticCase(tmp_path, monkeypatch)
    _register_real_sources(case, tmp_path)
    case.sidecars["proof_instruments"] = document(proof_path)["data"]
    case.freeze()
    # The host-filled proof now passes the completeness gate; the fabricated
    # 2026-09 row outside its approved scope still fails closed at coverage.
    with pytest.raises(SourceContractError, match="proof scope coverage gap"):
        case.load()
    assert not Path(case.recipe["parent"]).exists()


def test_real_instrument_row_and_proofs_pass_the_instruments_gate(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
    # Shift the fabricated recipe into the approved probe window (same mapping as
    # the ratio fixture), then bind the REAL host-filled row and both REAL proofs.
    def shift(value):
        if isinstance(value, str):
            for before, after in (("2026-09-25", "2025-10-22"), ("2026-09-28", "2025-10-23"),
                                  ("2026-09-29", "2025-10-24")):
                value = value.replace(before, after)
            return value
        if isinstance(value, list):
            return [shift(v) for v in value]
        if isinstance(value, dict):
            return {k: shift(v) for k, v in value.items()}
        return value
    case.rows, case.sidecars, case.recipe = map(shift, (case.rows, case.sidecars, case.recipe))
    _register_real_sources(case, tmp_path)
    case.sidecars["instruments"] = {"rows": [document("instruments.json")["data"]["rows"][0]]}
    # Keep fabricated quotes inside the real approved limit band; facts stay real.
    for row in case.rows:
        row["close"] = 23.50
    case.sidecars["commands"]["commands"][0]["limit"] = "23.50"
    del case.sidecars["proof_instruments"]
    case.recipe["sources"] = [s for s in case.recipe["sources"] if s["id"] != "proof_instruments"]
    for identity in ("proof_instruments_sse", "proof_instruments_wind"):
        case.sidecars[identity] = document(
            "instruments.proof.json" if identity.endswith("sse") else "instruments.wind.proof.json")["data"]
        case.recipe["sources"].insert(-1, {
            "id": identity, "location": {"kind": "sidecar", "path": str(tmp_path / (identity + ".json"))},
            "format": "json", "schema": "bl2_proof_v1", "sha256": "",
        })
    case.sidecars["attestation"]["claims"]["instruments"]["proofs"] = [
        "proof_instruments_sse", "proof_instruments_wind"]
    case.freeze()
    loaded = case.load()
    instrument = loaded.run_input.instruments[0]
    assert (instrument.reference_price, instrument.limit_down, instrument.limit_up) == (
        Decimal("23.36"), Decimal("21.02"), Decimal("25.70"))
    assert instrument.tick_size == Decimal("0.01") and instrument.lot_size == 100
    audit = loaded.provenance.document()["transform"]["instruments"][0]
    assert audit["available_at"] == "2025-10-22T15:30:00+08:00"
    assert audit["origin"] == "approved_derivation"
    # This crossing is evidence-structure only: the real host recipe and lake
    # remain unbound, and r4_authorized stays false.
    assert not Path(case.recipe["parent"]).exists()


def test_remapper_rejects_tampered_host_approval(tmp_path, remapper):
    approval = tmp_path / "approval.md"
    approval.write_text("unapproved", encoding="utf-8")
    with pytest.raises(ValueError, match="host approval hash mismatch"):
        remapper.build(UPSTREAM, PACK / "HUMAN_GO.md", approval)
    assert list(tmp_path.iterdir()) == [approval]


def test_remapper_check_matches_checked_in_packages():
    result = subprocess.run(
        [sys.executable, str(PACK / "remap.py"), "--source-dir", str(UPSTREAM),
         "--human-go", str(PACK / "HUMAN_GO.md"),
         "--host-cam-approval", str(PACK / "HOST_R4_CAM_APPROVAL_20260930.md"),
         "--host-timing-approval", str(PACK / "HOST_R4_TIMING_APPROVAL_20260930.md"), "--check"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_cam_pins_match_upstream_manifest_and_human_go(remapper):
    pins, inputs = remapper.read_inputs(UPSTREAM, PACK / "HUMAN_GO.md")
    cam = pins["cam_host_materials"]
    assert cam["repository"] == "baiyibing/OSkhQuant1.3"
    assert cam["commit"] == "42d066b81a083be49881f0dd8c5ab53ed4f422f6"
    assert cam["directory"] == "docs/evidence/b_l2_r4_cam_host_materials_draft_20260930"
    upstream_manifest = json.loads(inputs["cam_host_materials/manifest.json"])
    assert set(cam["files"]) == {a["path"] for a in upstream_manifest["artifacts"]} | {"manifest.json"}
    for item in upstream_manifest["artifacts"]:
        raw = (UPSTREAM / "cam_host_materials" / item["path"]).read_bytes()
        assert len(raw) == item["bytes"]
        assert sha256(raw) == item["sha256"] == cam["files"][item["path"]]["git_sha256"]
        assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and b"\x00" not in raw
    assert pins["human_go_cam_sha256"] == sha256((PACK / "HUMAN_GO_CAM.md").read_bytes()) == (
        "e15c79acde154bd7163208f2bf0a156737a9f908ed3fb9f41b87b64d42c13feb")
    approval = (PACK / remapper.CAM_APPROVAL_NAME).read_bytes()
    assert pins["host_cam_approval_sha256"] == sha256(approval)
    assert remapper.CAM_APPROVAL_ID in approval.decode("utf-8")
    assert "四格全批，开 packs" in inputs[remapper.CAM_GO_NAME]
    assert pins["commit"] == "ec19fd6f69a52f93aa9870ad582f0173df8963f4"
    assert pins["host_materials"]["commit"] == "d0edd384e9bd7fc0029b380e8850920539c46a95"


def test_cam_calendar_actions_and_marks_are_scoped_saved_observations():
    calendar = document("calendar.json")["data"]
    expected = list(EXPECTED_AVAILABLE_AT) + ["2025-11-05"]
    assert calendar == {"trading_dates": expected}
    proof = document("calendar.proof.json")["data"]
    assert proof["filter"]["through_date"] == "2025-11-05"
    pmc = document("sources/cam_pmc_calendar.json")["data"]["rows"]
    assert [pmc[row["row"]]["text"] for row in proof["result"]["rows"]] == [day.replace("-", "") for day in expected]
    assert {"cam_sse_holidays", "cam_calendar_cross_check", "host_cam_approval"} <= set(proof["source_refs"])
    actions = document("actions.json")["data"]
    assert actions == {"symbols": ["603196.SH"], "from_date": "2025-10-23", "through_date": "2025-11-04",
                       "complete": True, "events": [], "proofs": ["proof_actions"]}
    action_proof = document("actions.proof.json")["data"]
    assert action_proof["result"]["rows"] == []
    assert {"cam_ex_date_index", "cam_cninfo_analysis", "cam_preclose_chain",
            "cam_cninfo_p1", "cam_cninfo_p2", "cam_cninfo_p3", "host_cam_approval"} <= set(action_proof["source_refs"])
    pages = [document(f"sources/cam_cninfo_p{page}.json")["data"] for page in (1, 2, 3)]
    assert [len(page["rows"]) for page in pages] == [30, 30, 17]
    assert len({r["announcementId"] for page in pages for r in page["rows"]}) == 77
    assert all(page["page_metadata"]["totalpages"] == 2 for page in pages)  # Preserve upstream inconsistency.
    marks = document("marks.json")["data"]
    assert marks["subject"] == "marks" and marks["conclusion"] == "raw_contemporaneous_grid"
    assert marks["transform_version"] == "bl2_source_transform_v4"
    assert marks["source_identity_note"]["sha256"] == "58879893f221bfe050b7a16029667c49fb65d8ec6f47592254e549374a577083"
    assert marks["source_identity_note"]["binding_status"] == "unbound_minute_source"
    expected_points = [("spot_20251023_close", "2025-10-23T15:00:00+08:00", 46753, "23.89"),
                       ("final", "2025-11-04T15:00:00+08:00", 48681, "22.96")]
    substrate = document("sources/cam_marks_substrate.json")["data"]["rows"]
    observations = document("marks.proof.json")["data"]["result"]["rows"]
    assert len(marks["rows"]) == len(observations) == 2
    for point, obs, (identity, event, abs_row, close) in zip(marks["rows"], observations, expected_points, strict=True):
        assert point["mark_id"] == identity
        assert point["event_time"] == point["available_at"] == event
        assert point["price_domain"] == "raw" and len(point["prices"]) == 1
        price = point["prices"][0]
        assert (price["symbol"], price["abs_row"], price["price"]) == ("603196.SH", abs_row, close)
        assert price["source"] == "minute_603196" and price["price_column"] == "close"
        assert obs["source"] == price["substrate_source"] == "cam_marks_substrate"
        assert obs["row"] == price["substrate_row"]
        line = substrate[obs["row"]]
        assert line["line"] == obs["row"]
        assert f"| {abs_row} | {close} |" in line["text"]
        assert "available_at=event_time=" + event in obs["observation"]
        assert f"absolute parquet row={abs_row}" in obs["observation"]
    for subject in ("calendar", "actions", "marks"):
        proof = document(subject + ".proof.json")["data"]
        assert set(proof) == {"issuer", "subject", "source_refs", "filter", "result", "limitations"}
        assert proof["subject"] == subject and proof["result"]["complete"] is True
        assert proof["filter"]["from_date"] <= "2025-10-23"
        assert proof["filter"]["through_date"] >= "2025-11-04"
    manifest = document("manifest.json")
    assert manifest["r4_authorized"] is False and manifest["lake_verdict"] == "NOT_RUN"
    assert manifest["unbound_minute_source"]["sha256"] is None
    assert not any("calendar/actions/marks" in gap for gap in manifest["unresolved"])
    assert any("host recipe, lake identity/coverage and fresh freeze" in gap for gap in manifest["unresolved"])
    assert document("sources/human_go.json")["data"]["rows"][0]["r4_authorized"] is False


@pytest.mark.parametrize("subject", ["calendar", "actions", "marks"])
def test_cam_proofs_keep_loader_negative_row_contract(subject):
    store = SimpleNamespace(data={}, specs={})
    for spec in document("manifest.json")["artifacts"]:
        store.data[spec["id"]] = document(spec["path"])["data"]
        store.specs[spec["id"]] = spec
    proof = deepcopy(store.data["proof_" + subject])
    proof["result"]["rows"] = [{"source": "cam_ex_date_index", "row": 0, "observation": "not an event"}] if subject == "actions" else []
    with pytest.raises(SourceContractError, match="empty saved filter result|saved observations required"):
        source_loader._proof(proof, store, "proof_" + subject)


def test_remapper_rejects_tampered_cam_approval(tmp_path, remapper):
    approval = tmp_path / "cam_approval.md"
    approval.write_bytes((PACK / remapper.CAM_APPROVAL_NAME).read_bytes() + b"tampered\n")
    with pytest.raises(ValueError, match="CAM host approval hash mismatch"):
        remapper.build(UPSTREAM, PACK / "HUMAN_GO.md", host_cam_approval=approval)
    assert list(tmp_path.iterdir()) == [approval]


def test_remapper_requires_cam_approval_id_even_after_repin(tmp_path, remapper, monkeypatch):
    pins = document("inputs.json")
    approval = tmp_path / remapper.CAM_APPROVAL_NAME
    approval.write_text((PACK / remapper.CAM_APPROVAL_NAME).read_text(encoding="utf-8").replace(
        remapper.CAM_APPROVAL_ID, "unapproved"), encoding="utf-8")
    pins["host_cam_approval_sha256"] = sha256(approval.read_bytes())
    (tmp_path / "inputs.json").write_text(json.dumps(pins), encoding="utf-8")
    monkeypatch.setattr(remapper, "HERE", tmp_path)
    with pytest.raises(ValueError, match="CAM host approval id marker missing"):
        remapper.build(UPSTREAM, PACK / "HUMAN_GO.md", PACK / remapper.APPROVAL_NAME, approval)


@pytest.mark.parametrize("name", ["calendar/pmc_sse_calendar_20250901_20251231.txt",
                                  "actions/cninfo_603196_announcements_p3.json",
                                  "marks/minute_lake_marks_substrate.md", "manifest.json"])
def test_remapper_rejects_tampered_cam_pin(tmp_path, remapper, name):
    source = tmp_path / "source"
    shutil.copytree(UPSTREAM, source)
    path = source / "cam_host_materials" / name
    path.write_bytes(path.read_bytes() + b"tampered\n")
    with pytest.raises(ValueError, match="CAM input hash mismatch"):
        remapper.build(source, PACK / "HUMAN_GO.md")
    assert list(tmp_path.iterdir()) == [source]


def test_timing_excerpts_reproduce_pinned_original_materials(remapper):
    pins, _ = remapper.read_inputs(UPSTREAM, PACK / "HUMAN_GO.md")
    materials = pins["timing_host_materials"]
    assert materials["repository"] == "baiyibing/MyQuant-backtrader"
    assert materials["commit"] == "55f27f7967bc98a30146dc2474b91f1ac69f46f0"
    assert materials["directory"] == "docs/backtest/b-l2-01-evidence-2026-09-30"
    expected_pins = {
        remapper.TIMING_CENSUS: "b4ee473bcf7d224d635ce0f788d0d64dde8a2e421034420c2c292e9c632b7188",
        remapper.TIMING_DOCS: "3884f478256f96c7938cb5f0f40075ceb03f8064665be1193e2d445612bc8a12",
        remapper.TIMING_MAP: "b2487a9ba20f66b8e211b22536fb92d5dc60b0c2edb8eb2427c8d4c93e0e2fba",
    }
    originals = {name: (PACK.parent / name).read_bytes() for name in expected_pins}
    assert {name: sha256(raw) for name, raw in originals.items()} == expected_pins
    assert materials["original_files"] == {name: {"sha256": pin} for name, pin in expected_pins.items()}
    for name, excerpt in remapper.extract_timing_materials(materials, originals).items():
        raw = (UPSTREAM / remapper.TIMING_DIR / name).read_bytes()
        assert sha256(raw) == materials["files"][name]["git_sha256"]
        assert raw == remapper.encode(excerpt) == (PACK / "sources" / name).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and b"\x00" not in raw
    assert pins["human_go_timing_sha256"] == sha256((PACK / remapper.TIMING_GO_NAME).read_bytes()) == (
        "b89d99fc0fabbad5dd1e6da4ff6f3368ab84d1c7afce71832ea9e405d7e270f7")
    assert pins["host_timing_approval_sha256"] == sha256((PACK / remapper.TIMING_APPROVAL_NAME).read_bytes())
    # Neither earlier Human GO pin is repurposed by the new timing approval.
    assert pins["human_go_sha256"] == "bb287dfe9e2559e9fe05abb7401a636aa6596524cfb79ffa34a4f3ff884c2afe"
    assert pins["human_go_cam_sha256"] == "e15c79acde154bd7163208f2bf0a156737a9f908ed3fb9f41b87b64d42c13feb"


def test_timing_proof_resolves_r4d_claim_with_manifest_sources_only():
    manifest = document("manifest.json")
    store = SimpleNamespace(data={}, specs={})
    for spec in manifest["artifacts"]:
        assert spec["id"] not in store.data
        store.data[spec["id"]] = document(spec["path"])["data"]
        store.specs[spec["id"]] = spec
    proof = store.data["proof_timing"]
    assert store.specs["proof_timing"]["path"] == "timing.proof.json"
    assert store.specs["proof_timing"]["schema"] == "bl2_proof_v1"
    assert set(proof) == {"issuer", "subject", "source_refs", "filter", "result", "limitations"}
    assert proof["subject"] == "timing" and proof["result"]["complete"] is True
    assert proof["filter"]["symbols"] == ["603196.SH"]
    assert proof["filter"]["from_date"] == "2025-10-23"
    assert proof["filter"]["through_date"] == "2025-11-04"
    assert "END" in proof["filter"]["predicate"] and "bucket.end" in proof["filter"]["predicate"]
    assert "completed_bucket_available_at_end" in proof["result"]["summary"]
    assert {"timing_lake_census", "timing_xtquant_docs", "timing_materials_map",
            "host_timing_approval", "human_go_timing"} <= set(proof["source_refs"])
    for ref in proof["source_refs"]:
        assert store.specs[ref]["schema"] not in ("bl2_proof_v1", "bl2_attestation_v1")
        assert sha256((PACK / store.specs[ref]["path"]).read_bytes()) == store.specs[ref]["sha256"]
    assert proof["result"]["rows"]
    for obs in proof["result"]["rows"]:
        assert set(obs) == {"source", "row", "observation"}  # No instruments-only binding requirement.
        assert obs["source"] in proof["source_refs"]
        assert 0 <= obs["row"] < len(store.data[obs["source"]]["rows"])
    assert source_loader._proof(proof, store, "proof_timing") == {}
    source_loader._refs(["proof_timing"], store, "timing", symbols=["603196.SH"],
                        from_date=datetime(2025, 10, 23).date(), through_date=datetime(2025, 11, 4).date())
    # Reproduce the original missing-id failure without a recipe, resolver or lake.
    del store.data["proof_timing"]
    with pytest.raises(SourceContractError, match="timing: unknown proof source ref"):
        source_loader._refs(["proof_timing"], store, "timing")
    assert manifest["r4_authorized"] is False and manifest["lake_verdict"] == "NOT_RUN"
    assert manifest["unbound_minute_source"]["sha256"] is None
    assert not any("timing" in gap for gap in manifest["unresolved"])
    assert any("account/commands" in gap for gap in manifest["unresolved"])
    assert any("time-encoding reconciliation" in gap for gap in manifest["unresolved"])
    assert any("host recipe, lake identity/coverage and fresh freeze" in gap for gap in manifest["unresolved"])
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    assert '"conclusion": "completed_bucket_available_at_end"' in readme
    assert '"proofs": ["proof_timing"]' in readme


def test_timing_boundary_samples_keep_original_indexes_and_end_mapping():
    census = document("sources/timing_lake_census.json")["data"]["rows"]
    original = json.loads((PACK.parent / "raw_materials/raw_lake_minute_census_603196SH_20251023_20251104.json").read_bytes())
    assert census[0]["time_semantics"] == original["time_semantics"]
    assert census[1]["grid_definition"] == original["grid_definition"]
    assert [census[2][k] for k in ("window_rows", "grid_cells", "grid_missing", "grid_dup")] == [2169, 2133, 0, 0]
    expected = [("2025-10-23", "0930", 46513, False), ("2025-10-23", "0931", 46514, True),
                ("2025-10-23", "1130", 46633, True), ("2025-10-23", "1301", 46634, True),
                ("2025-10-23", "1457", 46750, True), ("2025-10-23", "1458", 46751, False),
                ("2025-10-23", "1459", 46752, False), ("2025-10-23", "1500", 46753, False),
                ("2025-11-04", "1500", 48681, False)]
    assert [(r["day"], r["end_label_hm"], r["row_idx"], r["in_tradable_grid"]) for r in census[3:]] == expected
    observations = document("timing.proof.json")["data"]["result"]["rows"]
    cited = {obs["row"]: obs["observation"] for obs in observations if obs["source"] == "timing_lake_census"}
    for index, row in enumerate(census[3:], 3):
        assert {k: v for k, v in row.items() if k not in ("kind", "source_cell_index")} == original["cells"][row["source_cell_index"]]
        assert f"parquet row={row['row_idx']}" in cited[index]
        assert "close/volume available at end" in cited[index]
    decoded = source_loader._time(1761211800000, {"encoding": "epoch_ms", "timezone": "Asia/Shanghai", "label": "END"}, "timing")
    assert decoded.isoformat() == "2025-10-23T17:30:00+08:00"
    # Preserve the discovered contradiction as a host freeze blocker, not a silent decoder fix.
    map_rows = document("sources/timing_materials_map.json")["data"]["rows"]
    assert any("1761211800000" in row["text"] and "09:30" in row["text"] for row in map_rows)
    vendor = document("sources/daqmt_1m.json")["data"]["rows"][0]
    assert int(vendor["time"]) == 1761183000000
    assert decoded - datetime.fromisoformat(vendor["datetime"]) == timedelta(hours=8)
    limitations = document("timing.proof.json")["data"]["limitations"]
    assert any("does not certify the R4d epoch_ms mapping" in item for item in limitations)


@pytest.mark.parametrize("change,match", [("empty_rows", "saved observations required"),
                                        ("self_ref", "proof/attestation cannot be its own evidence"),
                                        ("bad_index", "observation row outside pinned source rows")])
def test_timing_proof_keeps_loader_negative_contract(change, match):
    store = SimpleNamespace(data={}, specs={})
    for spec in document("manifest.json")["artifacts"]:
        store.data[spec["id"]] = document(spec["path"])["data"]
        store.specs[spec["id"]] = spec
    proof = deepcopy(store.data["proof_timing"])
    if change == "empty_rows":
        proof["result"]["rows"] = []
    elif change == "self_ref":
        proof["source_refs"].append("proof_timing")
    else:
        proof["result"]["rows"][0]["row"] = 2169  # Full census indexes cannot substitute for excerpt indexes.
    with pytest.raises(SourceContractError, match=match):
        source_loader._proof(proof, store, "proof_timing")


def test_remapper_rejects_tampered_timing_approval(tmp_path, remapper):
    approval = tmp_path / "timing_approval.md"
    approval.write_bytes((PACK / remapper.TIMING_APPROVAL_NAME).read_bytes() + b"tampered\n")
    with pytest.raises(ValueError, match="timing host approval hash mismatch"):
        remapper.build(UPSTREAM, PACK / "HUMAN_GO.md", host_timing_approval=approval)
    assert list(tmp_path.iterdir()) == [approval]


def test_remapper_requires_timing_approval_id_even_after_repin(tmp_path, remapper, monkeypatch):
    pins = document("inputs.json")
    approval = tmp_path / remapper.TIMING_APPROVAL_NAME
    approval.write_text((PACK / remapper.TIMING_APPROVAL_NAME).read_text(encoding="utf-8").replace(
        remapper.TIMING_APPROVAL_ID, "unapproved"), encoding="utf-8")
    pins["host_timing_approval_sha256"] = sha256(approval.read_bytes())
    (tmp_path / "inputs.json").write_text(json.dumps(pins), encoding="utf-8")
    shutil.copyfile(PACK / remapper.CAM_GO_NAME, tmp_path / remapper.CAM_GO_NAME)
    monkeypatch.setattr(remapper, "HERE", tmp_path)
    with pytest.raises(ValueError, match="timing host approval id marker missing"):
        remapper.build(UPSTREAM, PACK / "HUMAN_GO.md", PACK / remapper.APPROVAL_NAME,
                       PACK / remapper.CAM_APPROVAL_NAME, approval)


@pytest.mark.parametrize("name", ["timing_lake_census.json", "timing_xtquant_docs.json", "timing_materials_map.json"])
def test_remapper_rejects_tampered_timing_pin(tmp_path, remapper, name):
    source = tmp_path / "source"
    shutil.copytree(UPSTREAM, source)
    path = source / remapper.TIMING_DIR / name
    path.write_bytes(path.read_bytes() + b"tampered\n")
    with pytest.raises(ValueError, match="timing input hash mismatch"):
        remapper.build(source, PACK / "HUMAN_GO.md")
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("scope,field,value", [
    ("document", "board", "sse_star_a"),
    ("document", "board", None),
    ("document", "price_domain", "front"),
    ("row", "price_domain", "front"),
    ("document", "price_domain", "raw"),
    ("row", "price_domain", "raw"),
])
def test_remapper_rejects_changed_upstream_labels_after_repin(remapper, monkeypatch, scope, field, value):
    pins, inputs = remapper.read_inputs(UPSTREAM, PACK / "HUMAN_GO.md")
    upstream = inputs["instruments.json"]
    target = upstream if scope == "document" else upstream["rows"][0]
    target[field] = value
    # Simulate a future accepted re-pin; the semantic guard must still reject it.
    monkeypatch.setattr(remapper, "read_inputs", lambda *_: (pins, inputs))
    with pytest.raises(ValueError, match=field):
        remapper.build(UPSTREAM, PACK / "HUMAN_GO.md")


def test_remapper_rejects_unpinned_raw_before_parsing_or_writing(tmp_path, remapper):
    go = tmp_path / "HUMAN_GO.md"
    go.write_text("unapproved", encoding="utf-8")
    with pytest.raises(ValueError, match="Human GO hash mismatch"):
        remapper.build(tmp_path, go)
    assert list(tmp_path.iterdir()) == [go]
    go.write_bytes((PACK / "HUMAN_GO.md").read_bytes())
    (tmp_path / "units.proof.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="input hash mismatch: units.proof.json"):
        remapper.build(tmp_path, go)
