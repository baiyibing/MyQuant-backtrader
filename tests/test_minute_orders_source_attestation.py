"""B-L2-01 package contracts using fabricated files only; no host certification."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from backtest.research.minute_orders_backend import source_loader
from backtest.research.minute_orders_backend.source_provenance import SourceContractError, sha256
from tests.test_minute_orders_source_loader import SyntheticCase

TEMPLATES = Path(__file__).parent / "fixtures/minute_orders_source_attestation"


@pytest.fixture
def case(tmp_path, monkeypatch):
    return SyntheticCase(tmp_path, monkeypatch)


def add_proof(case, identity, proof):
    case.sidecars[identity] = proof
    case.recipe["sources"].insert(-1, {
        "id": identity, "location": {"kind": "sidecar", "path": str(case.root / (identity + ".json"))},
        "format": "json", "schema": "bl2_proof_v1", "sha256": "",
    })


@pytest.mark.parametrize("factor", [50, 100])
def test_volume_units_bind_exact_factor_column_and_source_without_guessing(case, factor):
    case.use_vendor_schema()
    case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=factor)
    case.attest_fabricated_bindings()
    case.freeze()
    before = {p: sha256(p.read_bytes()) for p in case.root.rglob("*") if p.is_file()}
    loaded = case.load()
    assert [b.volume_shares for b in loaded.run_input.buckets] == [1000 * factor, 500 * factor]
    assert loaded.provenance.document()["transform"]["bars"][0]["volume_proofs"] == [
        {"proof": "proof_units", "row": 0, "source": "observations", "source_row": 2}]
    assert before == {p: sha256(p.read_bytes()) for p in case.root.rglob("*") if p.is_file()}
    assert not Path(case.recipe["parent"]).exists()


@pytest.mark.parametrize("source_kind", ["synthetic_fixture", "lake"])
@pytest.mark.parametrize("change", ["stale_shares", "stale_factor", "column", "scope", "no_proof"])
def test_fresh_recipe_attestation_cannot_launder_unattested_lots(case, monkeypatch, source_kind, change):
    # 'lake' exercises only the guard over tmp_path synthetic files; no run/evidence writer.
    original = source_loader.execution_identity
    monkeypatch.setattr(source_loader, "execution_identity", lambda: dict(original(), code_dirty=False))
    case.recipe["source_kind"] = source_kind
    case.sidecars["attestation"]["source_kind"] = source_kind
    case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
    if change != "stale_shares":
        case.attest_fabricated_bindings()
    proof = case.sidecars["proof_units"]
    if change == "stale_factor":
        proof["result"]["rows"][0]["binding"]["shares_per_unit"] = 50
    elif change == "column":
        proof["result"]["rows"][0]["binding"]["column"] = "close"
    elif change == "scope":
        proof["filter"]["symbols"] = ["000001.SZ"]
    elif change == "no_proof":
        case.sidecars["attestation"]["claims"]["units"]["proofs"] = []
    case.freeze()  # New scope_hash still cannot repair a stale/missing units proof.
    with pytest.raises(SourceContractError, match="proof"):
        case.load()
    assert not Path(case.recipe["parent"]).exists()


@pytest.mark.parametrize("alias", [False, True])
def test_amount_close_volume_ratio_is_not_independent_unit_evidence(case, alias):
    case.use_vendor_schema()
    for row in case.rows:
        row["amount"] = row["close"] * row["volume"] * 100
    case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
    case.attest_fabricated_bindings()
    proof = case.sidecars["proof_units"]
    proof["source_refs"] = ["bars"]
    proof["result"]["rows"][0].update(source="bars", row=0, observation="amount/(close*volume)=100")
    case.freeze()
    if alias:
        # A second descriptor/path label must not launder the same bar bytes.
        spec = deepcopy(case.recipe["sources"][0])
        spec.update(id="bar_alias", location={"kind": "sidecar", "path": str(case.bar_path)})
        case.recipe["sources"].insert(-1, spec)
        proof["source_refs"] = ["bar_alias"]
        proof["result"]["rows"][0]["source"] = "bar_alias"
        # Preserve the parquet alias while freeze writes ordinary sidecars.
        case.action_paths["bar_alias"] = case.bar_path
        case.freeze(write_bars=False)
    with pytest.raises(SourceContractError, match="independent source declaration, not bar heuristics"):
        case.load()


@pytest.mark.parametrize("subject", ["units", "instruments", "status"])
@pytest.mark.parametrize("field", ["issuer", "subject", "source_refs", "filter", "result", "limitations"])
def test_each_registered_proof_requires_all_six_fields(case, subject, field):
    del case.sidecars["proof_" + subject][field]
    case.freeze()
    with pytest.raises(SourceContractError, match="proof.*schema fields"):
        case.load()


@pytest.mark.parametrize(("subject", "basis"), [
    ("units", "amount_close_volume_heuristic"),
    ("instruments", "ten_percent_default"),
    ("status", "halt_from_silence"),
])
def test_inferences_are_not_approved_evidence_bases(case, subject, basis):
    case.sidecars["proof_" + subject]["result"]["rows"][0]["basis"] = basis
    case.freeze()
    with pytest.raises(SourceContractError, match="heuristics are not attestation"):
        case.load()


@pytest.mark.parametrize("subject", ["units", "instruments", "status"])
@pytest.mark.parametrize("change", ["no_binding", "no_basis", "duplicate", "self_evidence", "conflicting_claim"])
def test_proof_bindings_are_structured_independent_and_unambiguous(case, subject, change):
    proof = case.sidecars["proof_" + subject]
    observation = proof["result"]["rows"][0]
    if change == "no_binding":
        del observation["binding"]
    elif change == "no_basis":
        del observation["basis"]
    elif change == "duplicate":
        proof["result"]["rows"].append(deepcopy(observation))
    elif change == "self_evidence":
        proof["source_refs"] = ["status" if subject == "status" else "instruments"]
    else:
        contradictory = deepcopy(proof)
        binding = contradictory["result"]["rows"][0]["binding"]
        if subject == "units":
            binding.update(unit="lots", shares_per_unit=100)
            # Each declaration is internally valid; the claim still conflicts.
            observations = case.sidecars["observations"]["rows"]
            observations.append({"basis": "source_declaration", "unit_declaration": {
                k: binding[k] for k in ("column", "kind", "unit", "shares_per_unit")}})
            contradictory["result"]["rows"][0]["row"] = len(observations) - 1
        elif subject == "status":
            binding["halted"] = True
        else:
            binding["facts"]["limit_up"] = "12.00"
        add_proof(case, "contradictory", contradictory)
        case.sidecars["attestation"]["claims"][subject]["proofs"].append("contradictory")
    case.freeze()
    with pytest.raises(SourceContractError, match="schema fields|duplicate/conflicting|own evidence|binding mismatch"):
        case.load()


@pytest.mark.parametrize(("field", "value"), [
    ("tick_size", "0.02"), ("lot_size", 200), ("reference_price", "10.02"),
    ("limit_down", "8.40"), ("limit_up", "11.60"),
])
def test_each_instrument_value_requires_matching_saved_assertion(case, field, value):
    case.sidecars["instruments"]["rows"][0]["facts"][field] = value
    case.freeze()
    with pytest.raises(SourceContractError, match="instruments: proof binding mismatch"):
        case.load()


@pytest.mark.parametrize(("field", "value", "message"), [
    ("tick_size", "0.00", "invalid tick"),
    ("tick_size", "0.001", "cent-aligned"),
    ("lot_size", 0, "lot_size"),
    ("lot_size", True, "integer"),
    ("reference_price", "NaN", "finite Decimal"),
    ("reference_price", "12.00", "daily price limits"),
    ("limit_down", "12.00", "daily limit facts"),
    ("limit_up", "8.00", "daily limit facts"),
])
def test_even_matching_proofs_cannot_override_existing_instrument_validation(case, field, value, message):
    case.sidecars["instruments"]["rows"][0]["facts"][field] = value
    case.attest_fabricated_bindings()
    case.freeze()
    with pytest.raises(ValueError, match=message):
        case.load()


@pytest.mark.parametrize("subject", ["units", "instruments", "status"])
def test_independent_proof_bytes_must_match_the_pinned_hash(case, subject):
    path = case.root / f"proof_{subject}.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(SourceContractError, match="source hash mismatch"):
        case.load()


@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("halted", [False, True])
def test_every_status_boolean_combination_is_explicitly_bound(case, missing, halted):
    case.sidecars["status"]["rows"][1].update(missing=missing, halted=halted,
                                              reason="fabricated independent status observation")
    if missing:
        case.rows.pop(1)
        case.recipe["mark_grid"][-1]["prices"][0]["row"] -= 1
    else:
        case.rows[1]["volume"] = 0
    case.attest_fabricated_bindings()
    case.freeze()
    bucket = case.load().run_input.buckets[1]
    assert (bucket.missing, bucket.halted) == (missing, halted)
    assert bucket.volume_shares == (None if missing else 0)


@pytest.mark.parametrize("change", ["halted", "missing", "reason", "issuer", "unbound_minute", "nonboolean_proof"])
def test_status_proof_for_date_cannot_substitute_for_actual_bucket_values(case, change):
    row = case.sidecars["status"]["rows"][0]
    if change in ("missing", "halted"):
        row[change] = True
    elif change in ("reason", "issuer"):
        row[change] = "changed after independent assertion"
    elif change == "unbound_minute":
        case.sidecars["proof_status"]["result"]["rows"].pop(0)
    else:
        case.sidecars["proof_status"]["result"]["rows"][0]["binding"]["missing"] = 0
    case.freeze()
    with pytest.raises(SourceContractError, match="proof binding"):
        case.load()


@pytest.mark.parametrize("change", ["same_proof", "same_issuer", "unbound_input", "changed_rule",
                                  "changed_output", "not_in_claim", "package_input"])
def test_approved_derivation_cannot_self_verify_or_change_frozen_rule_inputs_outputs(case, change):
    case.approve_fabricated_derivation()
    row = case.sidecars["instruments"]["rows"][0]
    if change == "same_proof":
        row["derivation"]["independent_verification"] = row["proofs"][:]
    elif change == "same_issuer":
        case.sidecars["proof_verification"]["issuer"] = case.sidecars["proof_instruments"]["issuer"]
    elif change == "unbound_input":
        row["derivation"]["inputs"].append("adj_factor")
    elif change == "changed_rule":
        row["derivation"]["approved_rule_version"] = "unapproved-rule-v2"
    elif change == "changed_output":
        case.sidecars["proof_verification"]["result"]["rows"][0]["binding"]["facts"]["limit_up"] = "12.00"
    elif change == "not_in_claim":
        case.sidecars["attestation"]["claims"]["instruments"]["proofs"].remove("proof_verification")
    else:
        row["derivation"]["inputs"] = ["instruments"]
    case.freeze()
    with pytest.raises(SourceContractError, match="independent|pinned inputs|binding mismatch|registered in claim"):
        case.load()


@pytest.mark.parametrize("filename", sorted(p.name for p in TEMPLATES.glob("*.json")))
def test_unfilled_templates_fail_closed_and_contain_no_market_values(case, filename):
    template = json.loads((TEMPLATES / filename).read_text(encoding="utf-8"))
    subject = filename.split(".")[0]
    if ".proof." in filename:
        assert template["data"]["result"]["complete"] is False
        assert template["data"]["source_refs"] == []
        case.sidecars["proof_" + subject] = template["data"]
    else:
        row = template["data"]["rows"][0]
        assert row["proofs"] == []
        if subject == "instruments":
            assert all(v is None for v in row["facts"].values())
        else:
            assert row["missing"] is None and row["halted"] is None
        case.sidecars[subject] = template["data"]
    case.freeze()
    with pytest.raises(SourceContractError):
        case.load()


@pytest.mark.parametrize("derived", [False, True])
def test_host_template_shapes_can_be_filled_with_explicit_fabricated_assertions(case, derived):
    if derived:
        case.approve_fabricated_derivation()

    def fill(template, values):
        # Structural contract check: unknown or missing keys cannot hide in a template.
        if isinstance(template, dict):
            assert template.keys() == values.keys()
            return {k: fill(v, values[k]) for k, v in template.items()}
        if isinstance(template, list) and template and isinstance(template[0], dict):
            return [fill(template[0], row) for row in values]
        return deepcopy(values)

    for subject in ("units", "instruments", "status"):
        template = json.loads((TEMPLATES / f"{subject}.proof.template.json").read_text(encoding="utf-8"))["data"]
        if derived and subject == "instruments":
            # Switch from source_fact to the documented approved_derivation binding.
            template["result"]["rows"][0]["binding"]["derivation"] = {
                "inputs": [], "approved_rule_version": None}
        case.sidecars["proof_" + subject] = fill(template, case.sidecars["proof_" + subject])
    for subject in ("instruments", "status"):
        name = "instruments.derived" if subject == "instruments" and derived else subject
        template = json.loads((TEMPLATES / f"{name}.template.json").read_text(encoding="utf-8"))["data"]
        case.sidecars[subject] = fill(template, case.sidecars[subject])
    case.freeze()
    assert case.load().run_input.instruments[0].reference_price == Decimal("10.00")
