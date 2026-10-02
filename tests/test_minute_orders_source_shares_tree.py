"""S1-shaped synthetic shares bytes only; S2 PASS is not lake/R4l/delta5 PASS."""

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from backtest.research.minute_orders_backend import source_loader
from backtest.research.minute_orders_backend.source_provenance import (
    NATIVE_SHARES_TRANSFORM_VERSION,
    TRANSFORM_VERSION,
    SourceContractError,
    sha256,
    validate_source_provenance,
)
from tests.test_minute_orders_source_loader import (
    SYMBOL,
    SyntheticCase,
    mapped_volume_case,
    source_case,
)


def units_evidence(case):
    proof_row = case.sidecars["proof_units"]["result"]["rows"][0]
    return case.sidecars[proof_row["source"]]["rows"][proof_row["row"]]


def shares_tree(case, *, audit_column=True):
    """Mirror SCHEMA.md columns, without accessing S1's real export or lake."""
    rows = []
    for original in case.rows:
        wall = datetime.fromisoformat(original["time"]).replace(tzinfo=None)
        volume = original["volume"]
        rows.append({
            "symbol": SYMBOL, "timestamp": wall.isoformat(sep=" "), "day": wall.strftime("%Y%m%d"),
            "time_ms": int(wall.replace(tzinfo=UTC).timestamp()) * 1000,
            **{column: original["close"] for column in ("open", "high", "low", "close")},
            "volume": volume, **({"volume_lots_source": volume // 100} if audit_column else {}),
            "amount": volume * original["close"], "period": "1m", "dividend_type": "none",
            "unit": "raw_shares_incremental",
        })
    case.rows = rows
    case.recipe["implementation"]["transform_version"] = NATIVE_SHARES_TRANSFORM_VERSION
    bar = case.recipe["bars"][0]
    bar["columns"]["time"] = "timestamp"
    bar["time"]["encoding"] = "naive_shanghai"
    for mark in case.recipe["mark_grid"]:
        mark["prices"][0]["time_column"] = "timestamp"
        mark["prices"][0]["time"]["encoding"] = "naive_shanghai"
    units_evidence(case).update(contract="raw_shares_incremental", transformations=[])
    case.freeze()
    return case


@pytest.fixture
def native_case(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
    case.rows[0]["volume"], case.rows[1]["volume"] = 38000, 0
    return shares_tree(case)


@pytest.mark.parametrize("audit_column", [False, True])
def test_s1_shares_are_read_verbatim_with_replay_and_unchanged_sources(tmp_path, monkeypatch, audit_column):
    case = SyntheticCase(tmp_path, monkeypatch)
    case.rows[0]["volume"], case.rows[1]["volume"] = 38000, 0
    shares_tree(case, audit_column=audit_column)
    before = {p: sha256(p.read_bytes()) for p in case.root.rglob("*") if p.is_file()}
    loaded = case.load()
    physical = pq.ParquetFile(case.bar_path).read().column("volume").to_pylist()
    assert [b.volume_shares for b in loaded.run_input.buckets] == physical[:2] == [38000, 0]
    doc = loaded.provenance.document()
    assert doc["transform"]["version"] == NATIVE_SHARES_TRANSFORM_VERSION
    for row, expected in zip(doc["transform"]["bars"], physical[:2], strict=True):
        assert row["volume"]["original"] == str(expected)
        assert row["volume_shares"] == expected and row["shares_per_unit"] == 1
        assert row["volume_at_rest"] == {
            "basis": "source_declaration", "unit": "raw_shares_incremental", "transformations": []}
        assert "volume_mapping" not in row
    assert validate_source_provenance(
        loaded.run_input, loaded.provenance, parent=case.recipe["parent"], run_id=case.recipe["run_id"]
    ) == doc
    assert {p: sha256(p.read_bytes()) for p in case.root.rglob("*") if p.is_file()} == before
    assert not Path(case.recipe["parent"]).exists()


@pytest.mark.parametrize("volume", [123, 2**63 - 1])
def test_native_shares_do_not_read_or_round_the_optional_lots_audit_column(native_case, volume):
    native_case.rows[0].update(volume=volume, volume_lots_source=999999)
    native_case.freeze()
    assert native_case.load().run_input.buckets[0].volume_shares == volume


@pytest.mark.parametrize("change,match", [
    ("lots_factor", "native shares require volume/shares/1"),
    ("missing_contract", "native shares require volume/shares/1"),
    ("missing_transformations", "native shares require volume/shares/1"),
    ("nonempty_transformations", "native shares require volume/shares/1"),
    ("null_transformations", "native shares require volume/shares/1"),
    ("multiply", "cannot contain mapping instructions"),
    ("input_binding", "cannot contain mapping instructions"),
    ("mixed_basis", "explicit matching unit declaration"),
    ("old_tag", "old-tree scaling forbidden"),
    ("audit_column_selected", "native shares require volume/shares/1"),
    ("missing_evidence_contract", "native shares require volume/shares/1"),
])
def test_native_contract_cannot_hide_scaling_or_mixed_bases(native_case, change, match):
    case = native_case
    evidence = units_evidence(case)
    if change == "lots_factor":
        case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
        case.attest_fabricated_bindings()
    elif change == "audit_column_selected":
        case.recipe["bars"][0]["columns"]["volume"] = "volume_lots_source"
        case.attest_fabricated_bindings()
    elif change.startswith("missing_"):
        if change == "missing_evidence_contract":
            del evidence["contract"], evidence["transformations"]
        else:
            del evidence[change.removeprefix("missing_")]
    elif change == "nonempty_transformations":
        evidence["transformations"] = [{"operation": "multiply", "multiplier": 100}]
    elif change == "null_transformations":
        evidence["transformations"] = None
    elif change == "multiply":
        evidence.update(operation="multiply", multiplier=100)
    elif change == "input_binding":
        evidence["input_binding"] = {"unit": "lots", "shares_per_unit": 100}
    elif change == "mixed_basis":
        evidence["basis"] = "authorized_mapping"
    else:
        case.recipe["implementation"]["transform_version"] = TRANSFORM_VERSION
    case.freeze()
    with pytest.raises(SourceContractError, match=match):
        case.load()
    assert not Path(case.recipe["parent"]).exists()


@pytest.mark.parametrize("row_index", [0, 2, 4])
@pytest.mark.parametrize("unit", ["lots", "shares", None])
def test_native_units_checked_even_on_excluded_and_mark_only_rows(native_case, row_index, unit):
    native_case.rows[row_index]["unit"] = unit
    native_case.freeze()
    with pytest.raises(SourceContractError, match="consistent raw_shares_incremental source units"):
        native_case.load()


@pytest.mark.parametrize("change", ["no_unit_column", "float_volume", "negative_volume", "null_volume"])
def test_native_schema_and_quantity_fail_closed(native_case, change):
    if change == "no_unit_column":
        for row in native_case.rows:
            del row["unit"]
    else:
        native_case.rows[0]["volume"] = {"float_volume": 38000.0, "negative_volume": -1, "null_volume": None}[change]
    native_case.freeze()
    with pytest.raises(SourceContractError, match="native shares require int64|volume is negative|invalid numeric"):
        native_case.load()


def test_every_native_units_proof_must_declare_the_at_rest_contract(native_case):
    case = native_case
    proof = deepcopy(case.sidecars["proof_units"])
    evidence = deepcopy(units_evidence(case))
    del evidence["contract"], evidence["transformations"]
    evidence_rows = case.sidecars["observations"]["rows"]
    proof["result"]["rows"][0]["row"] = len(evidence_rows)
    evidence_rows.append(evidence)
    case.sidecars["proof_other_units"] = proof
    case.recipe["sources"].insert(-1, {
        "id": "proof_other_units", "location": {"kind": "sidecar", "path": str(case.root / "other_units.json")},
        "format": "json", "schema": "bl2_proof_v1", "sha256": ""})
    case.sidecars["attestation"]["claims"]["units"]["proofs"].append("proof_other_units")
    case.freeze()
    with pytest.raises(SourceContractError, match="native shares require volume/shares/1"):
        case.load()


@pytest.mark.parametrize("change,match", [
    ("native_tag", "native shares require source_declaration"),
    ("empty_transformations", "old-tree authorized_mapping cannot claim native"),
    ("raw_source_units", "old-tree scaling forbidden"),
    ("shares_source_units", "physical source units conflict"),
])
def test_v8_mapping_is_exclusive_to_old_tree_bytes(mapped_volume_case, monkeypatch, change, match):
    case = mapped_volume_case
    evidence = units_evidence(case)
    if change == "native_tag":
        case.recipe["implementation"]["transform_version"] = NATIVE_SHARES_TRANSFORM_VERSION
    elif change == "empty_transformations":
        evidence["transformations"] = []
    else:
        for row in case.rows:
            row["unit"] = "raw_shares_incremental" if change == "raw_source_units" else "shares"
    case.freeze()
    # Repin fabricated evidence to reach the branch gate, not just fail its hash.
    evidence["input_binding"]["source_sha256"] = case.recipe["sources"][0]["sha256"]
    case.freeze(write_bars=False)
    monkeypatch.setattr(source_loader, "_VOLUME_MAPPING_APPROVAL_SHA256",
                        next(s["sha256"] for s in case.recipe["sources"] if s["id"] == "mapping_approval"))
    with pytest.raises(SourceContractError, match=match):
        case.load()


def test_raw_column_cannot_be_scaled_by_a_legacy_lots_declaration(source_case):
    case = source_case
    for row in case.rows:
        row["unit"] = "raw_shares_incremental"
    case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
    case.attest_fabricated_bindings()
    case.freeze()
    with pytest.raises(SourceContractError, match="old-tree scaling forbidden"):
        case.load()
