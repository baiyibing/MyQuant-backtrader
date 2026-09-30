"""Vendor-shaped synthetic fixtures; no market truth, lake access or live PASS."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from backtest.research.minute_orders_backend.source_provenance import (
    FIXTURE_NOTICE,
    SourceContractError,
    sha256,
)
from backtest.research.minute_orders_backend.types import RunContractError

from tests.test_minute_orders_source_loader import SYMBOL, SyntheticCase, at


@pytest.fixture
def vendor_case(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
    case.use_vendor_schema()
    case.freeze()
    return case


def test_vendor_partition_mapping_freezes_without_a_symbol_column_or_source_writes(vendor_case):
    schema = vendor_case.recipe["sources"][0]["schema"]
    assert schema == {"time": "int64", "open": "double", "high": "double", "low": "double",
                      "close": "double", "volume": "int64", "amount": "double",
                      "__index_level_0__": "timestamp[ns]"}
    before = {p: sha256(p.read_bytes()) for p in vendor_case.root.rglob("*") if p.is_file()}
    loaded = vendor_case.load()
    assert {p: sha256(p.read_bytes()) for p in vendor_case.root.rglob("*") if p.is_file()} == before
    assert [b.symbol for b in loaded.run_input.buckets] == [SYMBOL, SYMBOL]
    assert [b.volume_shares for b in loaded.run_input.buckets] == [1000, 500]
    assert loaded.run_input.marks[-1].event_time.isoformat() == at("15:00:00")
    doc = loaded.provenance.document()
    assert doc["notice"] == FIXTURE_NOTICE
    for row in doc["transform"]["bars"] + doc["transform"]["marks"]:
        assert row["symbol_binding"] == {
            "kind": "partition", "location": {"kind": "minute", "symbol": SYMBOL},
            "partition_key": "603196_SH", "checked_columns": [],
        }
    assert not Path(vendor_case.recipe["parent"]).exists()


@pytest.mark.parametrize("selector", ["symbol", "", None, {}, {"kind": "auto"},
                                     {"kind": "partition", "symbol": SYMBOL}])
def test_no_symbol_column_needs_exact_explicit_partition_opt_in(vendor_case, selector):
    vendor_case.recipe["bars"][0]["columns"]["symbol"] = selector
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="column|selector|schema fields"):
        vendor_case.load()


def test_omitted_symbol_selector_is_not_a_default(vendor_case):
    del vendor_case.recipe["bars"][0]["columns"]["symbol"]
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="bar columns.*schema fields"):
        vendor_case.load()


@pytest.mark.parametrize("tag", [SYMBOL, "603196_SH", "symbol=603196_SH"])
def test_partition_mode_checks_existing_matching_symbol_column(vendor_case, tag):
    for row in vendor_case.rows:
        row["symbol"] = tag
    vendor_case.freeze()
    doc = vendor_case.load().provenance.document()
    assert doc["transform"]["bars"][0]["symbol_binding"]["checked_columns"] == ["symbol"]


@pytest.mark.parametrize("row_index", [0, 2, 4])
@pytest.mark.parametrize("bad_symbol", ["000001.SZ", None, "603196"])
def test_partition_mode_rejects_mixed_symbols_even_outside_grid(vendor_case, row_index, bad_symbol):
    for row in vendor_case.rows:
        row["symbol"] = SYMBOL
    vendor_case.rows[row_index]["symbol"] = bad_symbol
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="symbol"):
        vendor_case.load()


def test_column_mapping_cannot_hide_a_conflicting_physical_symbol(vendor_case):
    for row in vendor_case.rows:
        row.update(symbol="000001.SZ", security=SYMBOL)
    vendor_case.recipe["bars"][0]["columns"]["symbol"] = "security"
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="partition/symbol mismatch in symbol"):
        vendor_case.load()


def test_partition_mode_still_rejects_duplicate_timestamps(vendor_case):
    vendor_case.rows.append(deepcopy(vendor_case.rows[0]))
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="duplicate/conflicting source timestamp"):
        vendor_case.load()


def test_partition_identity_cannot_be_taken_from_an_arbitrary_sidecar_path(vendor_case):
    vendor_case.recipe["sources"][0]["location"] = {"kind": "sidecar", "path": str(vendor_case.bar_path)}
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="raw minute resolver"):
        vendor_case.load()


@pytest.mark.parametrize("change", ["symbol", "mapping", "price", "time"])
def test_partition_marks_preserve_source_identity_and_mapping(vendor_case, change):
    mark = vendor_case.recipe["mark_grid"][0]["prices"][0]
    if change == "symbol":
        mark["symbol"] = "000001.SZ"
    elif change == "mapping":
        mark["symbol_column"] = "symbol"
    elif change == "price":
        mark["price_column"] = "open"
    else:
        mark["time"]["label"] = "END"
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="mark source symbol|preserve the minute source"):
        vendor_case.load()


def test_zero_volume_source_bar_remains_present(vendor_case):
    vendor_case.rows[0].update(volume=0, amount=0.0)
    vendor_case.freeze()
    loaded = vendor_case.load()
    first, second = loaded.run_input.buckets
    assert first.start.isoformat() == at("09:30:00")
    assert first.volume_shares == 0
    assert first.missing is False and first.halted is False
    assert first.close == Decimal("10.0")
    assert second.volume_shares == 500
    transform = loaded.provenance.document()["transform"]
    bar = transform["bars"][0]
    assert bar["source"] == "bars" and bar["row"] == 0
    assert bar["volume_shares"] == 0
    status = transform["status"][bar["status_row"]]
    assert status["missing"] is False and status["halted"] is False


def test_status_grid_retains_explicit_missing_halted_and_issuer_proofs(vendor_case):
    vendor_case.rows.pop(1)
    missing = vendor_case.sidecars["status"]["rows"][1]
    missing.update(missing=True, halted=True, reason="fabricated halt and missing observation")
    vendor_case.recipe["mark_grid"][-1]["prices"][0]["row"] -= 1
    vendor_case.freeze()
    loaded = vendor_case.load()
    first, second = loaded.run_input.buckets
    assert not first.missing and not first.halted
    assert second.missing and second.halted and second.close is None and second.volume_shares is None
    audit = loaded.provenance.document()["transform"]["status"]
    assert len(audit) == 2
    assert audit[1]["source"] == "status" and audit[1]["row"] == 1
    for field in ("missing", "halted", "reason", "issuer", "proofs"):
        assert audit[1][field] == missing[field]


@pytest.mark.parametrize("change", ["missing_row", "duplicate", "extra", "blank_reason", "blank_issuer",
                                  "missing_boolean", "nonboolean", "no_proof", "unregistered_proof"])
def test_status_grid_is_complete_explicit_and_proven(vendor_case, change):
    rows = vendor_case.sidecars["status"]["rows"]
    if change == "missing_row":
        rows.pop()
    elif change == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif change == "extra":
        rows.append({**rows[0], "start": at("09:32:00"), "end": at("09:33:00")})
    elif change == "blank_reason":
        rows[0]["reason"] = " "
    elif change == "blank_issuer":
        rows[0]["issuer"] = " "
    elif change == "missing_boolean":
        del rows[0]["halted"]
    elif change == "nonboolean":
        rows[0]["missing"] = 0
    elif change == "no_proof":
        rows[0]["proofs"] = []
    else:
        rows[0]["proofs"] = ["host-unregistered"]
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="coverage|reason|issuer|schema fields|booleans|proof"):
        vendor_case.load()


@pytest.mark.parametrize("subject", ["status", "instruments"])
@pytest.mark.parametrize("change", ["symbol", "from_date", "through_date", "source_row", "issuer"])
def test_fact_proofs_cover_actual_symbols_dates_and_saved_source_rows(vendor_case, subject, change):
    proof = vendor_case.sidecars["proof_" + subject]
    if change == "symbol":
        proof["filter"]["symbols"] = ["000001.SZ"]
    elif change == "from_date":
        proof["filter"]["from_date"] = "2026-09-29"
    elif change == "through_date":
        proof["filter"]["through_date"] = "2026-09-25"
    elif change == "source_row":
        proof["result"]["rows"][0]["row"] = 999
    else:
        proof["issuer"] = " "
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="scope coverage|outside pinned source rows|issuer"):
        vendor_case.load()


@pytest.mark.parametrize("role", ["status", "instruments"])
def test_status_and_instrument_sidecars_require_matching_hashes(vendor_case, role):
    path = vendor_case.root / (role + ".json")
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(SourceContractError, match="source hash mismatch"):
        vendor_case.load()


@pytest.mark.parametrize("role", ["status", "instruments", "derivation"])
def test_valid_attestation_does_not_cover_an_unrelated_row_proof(vendor_case, role):
    subject = "instruments" if role == "derivation" else role
    proof = deepcopy(vendor_case.sidecars["proof_" + subject])
    proof["filter"]["symbols"] = ["000001.SZ"]
    vendor_case.sidecars["row_proof"] = proof
    vendor_case.recipe["sources"].insert(-1, {
        "id": "row_proof", "location": {"kind": "sidecar", "path": str(vendor_case.root / "row_proof.json")},
        "format": "json", "schema": "bl2_proof_v1", "sha256": "",
    })
    row = vendor_case.sidecars[subject]["rows"][0]
    if role == "derivation":
        row["origin"] = "approved_derivation"
        row["derivation"] = {"inputs": ["observations"], "approved_rule_version": "fixture-rule-v1",
                             "independent_verification": ["row_proof"]}
    else:
        row["proofs"] = ["row_proof"]
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="proof scope coverage gap"):
        vendor_case.load()


@pytest.mark.parametrize(("missing_role", "error", "message"), [
    (None, None, None),
    ("status", SourceContractError, "coverage grid mismatch"),
    ("instruments", RunContractError, "missing instrument facts"),
])
def test_multiple_sessions_require_status_cells_and_daily_facts(vendor_case, missing_role, error, message):
    def next_day(value):
        return value.replace("2026-09-28", "2026-09-29")

    for original in (vendor_case.rows[0], vendor_case.rows[-1]):
        vendor_case.rows.append({**original, "time": original["time"] + 86_400_000,
                                "__index_level_0__": original["__index_level_0__"] + timedelta(days=1)})
    vendor_case.recipe["intervals"].append({"start": next_day(at("09:30:00")), "end": next_day(at("09:31:00"))})
    vendor_case.recipe["end_at"] = next_day(at("15:00:00"))
    final = vendor_case.recipe["mark_grid"][-1]
    final["event_time"] = vendor_case.recipe["end_at"]
    final["prices"][0]["row"] = len(vendor_case.rows) - 1
    vendor_case.sidecars["calendar"]["trading_dates"].append("2026-09-30")
    status = deepcopy(vendor_case.sidecars["status"]["rows"][0])
    for field in ("start", "end"):
        status[field] = next_day(status[field])
    facts = deepcopy(vendor_case.sidecars["instruments"]["rows"][0])
    facts["facts"]["trade_date"] = "2026-09-29"
    for field in ("effective_from", "effective_through", "available_at"):
        facts[field] = next_day(facts[field])
    if missing_role != "status":
        vendor_case.sidecars["status"]["rows"].append(status)
    if missing_role != "instruments":
        vendor_case.sidecars["instruments"]["rows"].append(facts)
    vendor_case.freeze()
    if missing_role is None:
        run = vendor_case.load().run_input
        assert len(run.buckets) == 3 and len(run.instruments) == 2
    else:
        with pytest.raises(error, match=message):
            vendor_case.load()


def test_pinned_instrument_facts_are_used_verbatim_without_ten_percent_guess(vendor_case):
    # Deliberately asymmetric fabricated limits prove no 10% calculation.
    row = vendor_case.sidecars["instruments"]["rows"][0]
    row["facts"].update(tick_size="0.02", lot_size=200, reference_price="10.00",
                        limit_down="8.40", limit_up="11.60")
    vendor_case.freeze()
    loaded = vendor_case.load()
    facts, = loaded.run_input.instruments
    assert (facts.tick_size, facts.lot_size, facts.reference_price, facts.limit_down, facts.limit_up) == (
        Decimal("0.02"), 200, Decimal("10.00"), Decimal("8.40"), Decimal("11.60"))
    audit, = loaded.provenance.document()["transform"]["instruments"]
    assert audit["proofs"] == ["proof_instruments"] and audit["origin"] == "source_fact"
    assert audit["available_at"] == at("09:00:00")


@pytest.mark.parametrize("field", ["tick_size", "lot_size", "reference_price", "limit_down", "limit_up",
                                 "board", "price_domain"])
def test_no_instrument_defaults_when_pinned_fact_field_is_absent(vendor_case, field):
    del vendor_case.sidecars["instruments"]["rows"][0]["facts"][field]
    vendor_case.freeze()
    with pytest.raises(SourceContractError, match="instrument facts.*schema fields"):
        vendor_case.load()


@pytest.mark.parametrize(("change", "error"), [
    ("no_rows", RunContractError),
    ("duplicate", RunContractError),
    ("unknown_symbol", SourceContractError),
    ("no_proof", SourceContractError),
    ("wrong_proof", SourceContractError),
    ("no_listing", SourceContractError),
    ("effective_gap", SourceContractError),
    ("late", SourceContractError),
    ("hidden_derivation", SourceContractError),
])
def test_instrument_grid_rejects_missing_or_unproven_facts(vendor_case, change, error):
    rows = vendor_case.sidecars["instruments"]["rows"]
    if change == "no_rows":
        rows.clear()
    elif change == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif change == "unknown_symbol":
        rows[0]["facts"]["symbol"] = "000001.SZ"
    elif change == "no_proof":
        rows[0]["proofs"] = []
    elif change == "wrong_proof":
        rows[0]["proofs"] = ["proof_status"]
    elif change == "no_listing":
        del rows[0]["ordinary_listing"]
    elif change == "effective_gap":
        rows[0]["effective_through"] = "2026-09-25"
    elif change == "late":
        rows[0]["available_at"] = at("09:31:00")
    else:
        rows[0]["derivation"] = {"guess": "10 percent"}
    vendor_case.freeze()
    with pytest.raises(error, match="instrument|proof|listing|derivation"):
        vendor_case.load()


@pytest.mark.parametrize("change", [None, "no_inputs", "proof_as_input", "no_rule", "no_verification", "wrong_verification"])
def test_derived_facts_need_pinned_inputs_rule_and_independent_proof(vendor_case, change):
    row = vendor_case.sidecars["instruments"]["rows"][0]
    row["origin"] = "approved_derivation"
    row["derivation"] = {"inputs": ["observations"], "approved_rule_version": "fabricated-rule-v1",
                         "independent_verification": ["proof_instruments"]}
    if change == "no_inputs":
        row["derivation"]["inputs"] = []
    elif change == "proof_as_input":
        row["derivation"]["inputs"] = ["proof_instruments"]
    elif change == "no_rule":
        row["derivation"]["approved_rule_version"] = " "
    elif change == "no_verification":
        row["derivation"]["independent_verification"] = []
    elif change == "wrong_verification":
        row["derivation"]["independent_verification"] = ["proof_status"]
    vendor_case.freeze()
    if change is None:
        assert vendor_case.load().run_input.instruments[0].limit_up == Decimal("11.00")
    else:
        with pytest.raises(SourceContractError, match="pinned inputs|approved rule|proof"):
            vendor_case.load()
