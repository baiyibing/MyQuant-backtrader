"""Offline evidence checks and fabricated acceptance tests; no lake or host run."""

import importlib.util
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from backtest.research.minute_orders_backend import source_loader
from backtest.research.minute_orders_backend.source_provenance import SourceContractError, sha256
from tests.test_minute_orders_source_loader import SyntheticCase


PACK = Path(__file__).parents[1] / "docs/backtest/b-l2-01-evidence-2026-09-30/attestation_packages"
UPSTREAM = Path(__file__).parent / "fixtures/bl2_attestation_remap_upstream"


def document(name):
    return json.loads((PACK / name).read_bytes())


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


def test_checked_packages_hashes_bind_all_rows_and_preserve_instrument_blockers():
    manifest = document("manifest.json")
    store = SimpleNamespace(data={}, specs={}, proof_bindings={})
    for spec in manifest["artifacts"]:
        raw = (PACK / spec["path"]).read_bytes()
        assert sha256(raw) == spec["sha256"]
        doc = json.loads(raw)
        assert doc["schema_version"] == spec["schema"]
        store.data[spec["id"]] = doc["data"]
        store.specs[spec["id"]] = {**spec, "location": {"kind": "sidecar"}}
    # Descriptor only for proof structure; never invokes the lake resolver.
    store.specs["minute_603196"] = {"schema": {"volume": "int64"}, "sha256": "0" * 64,
                                    "location": {"kind": "minute", "symbol": "603196.SH"}}
    for identity in ("proof_units", "proof_status"):
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
    sse, wind = (store.data[p] for p in ("proof_instruments_sse", "proof_instruments_wind"))
    assert sse["issuer"] != wind["issuer"]
    for proof in (sse, wind):
        with pytest.raises(SourceContractError, match="complete saved result required"):
            source_loader._proof(proof, store, "blocked_instruments")
    for index, row in enumerate(store.data["instruments"]["rows"]):
        assert row["available_at"] is row["ordinary_listing"] is None
        binding = source_loader._instrument_binding(row)
        assert binding == sse["result"]["rows"][index]["binding"] == wind["result"]["rows"][index]["binding"]
        assert set(row["derivation"]["inputs"]) <= set(sse["source_refs"]) & set(wind["source_refs"])
    assert store.data["wind_limits"]["origin"]["host_sha256"] == "31f8461a4ae7aca352db35648c0d7c60e476597b259bfecc03c9807c9f3a048b"


@pytest.fixture
def remapper():
    spec = importlib.util.spec_from_file_location("remap", PACK / "remap.py")
    remap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(remap)
    return remap


def test_remapper_check_matches_checked_in_packages():
    result = subprocess.run(
        [sys.executable, str(PACK / "remap.py"), "--source-dir", str(UPSTREAM),
         "--human-go", str(PACK / "HUMAN_GO.md"), "--check"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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
