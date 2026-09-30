"""Small generated synthetic fixtures only. Fixture PASS != lake PASS."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, Inexact, ROUND_UP, Rounded, localcontext
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from backtest.research.minute_orders_backend.clock import RunContractError
from backtest.research.minute_orders_backend.fees import FeeContractError, money_cents
from backtest.research.minute_orders_backend import source_loader
from backtest.research.minute_orders_backend.source_loader import load_minute_orders_source
from backtest.research.minute_orders_backend.source_provenance import (
    FIXTURE_NOTICE,
    TRANSFORM_VERSION,
    SourceContractError,
    attestation_scope,
    execution_identity,
    sha256,
)

SYMBOL = "603196.SH"


def at(time):
    return "2026-09-28T" + time + "+08:00"


class SyntheticCase:
    """Materialize tiny fixtures into tmp_path, never read any configured lake."""

    def __init__(self, tmp_path, monkeypatch):
        self.root = tmp_path
        self.lake = tmp_path / "fixture_lake"
        self.lake.mkdir()
        for key in ("OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT", "OSKH_PERIOD_1M_ROOT", "OSKH_PERIOD_1D_ROOT"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(self.lake))
        self.path = tmp_path / "recipe.json"
        self.bar_path = self.lake / "stock/period=1m/dividend_type=none/symbol=603196_SH/data.parquet"
        self.bar_path.parent.mkdir(parents=True)
        self.rows = [{"symbol": "603196_SH", "time": at(t), "close": 10.0, "volume": v}
                     for t, v in (("09:30:00", 1000), ("09:31:00", 500), ("14:56:00", 100), ("14:57:00", 200), ("14:59:00", 300))]
        pq.write_table(pa.Table.from_pylist(self.rows), self.bar_path)
        fees = {"rate": "0.001", "min_fee": "5.00", "rounding": "ROUND_HALF_UP"}
        self.sidecars = {
            "calendar": {"trading_dates": ["2026-09-25", "2026-09-28", "2026-09-29"]},
            "commands": {"origin": "designed_limit_batch", "commands": [
                {"kind": "submit", "command_id": "submit-A", "order_id": "A", "symbol": "symbol=603196_SH",
                 "side": "BUY", "qty": 400, "limit": "10.00", "available_at": at("09:29:00"),
                 "submitted_at": at("09:29:00"), "effective_at": at("09:30:00"), "expires_at": at("09:35:00"),
                 "sequence": 1, "order_type": "LIMIT"},
                {"kind": "cancel", "command_id": "cancel-A", "order_id": "A", "available_at": at("09:32:00"),
                 "submitted_at": at("09:32:00"), "effective_at": at("09:32:30"), "sequence": 2}]},
            "account": {"origin": "synthetic_account", "initial_cash": "10000.00", "initial_lots": [],
                        "buy_fees": fees, "sell_fees": deepcopy(fees), "participation_rate": "0.20", "requires_marks": True},
            "instruments": {"rows": [{"facts": {"symbol": SYMBOL, "trade_date": "2026-09-28", "board": "main",
                                                "price_domain": "raw", "tick_size": "0.01", "lot_size": 100,
                                                "reference_price": "10.00", "limit_down": "9.00", "limit_up": "11.00"},
                                      "effective_from": "2026-09-28", "effective_through": "2026-09-28",
                                      "available_at": at("09:00:00"), "ordinary_listing": True,
                                      "origin": "source_fact", "proofs": ["proof_instruments"], "derivation": {}}]},
            "status": {"rows": [{"symbol": SYMBOL, "start": at(start), "end": at(end), "missing": False,
                                  "halted": False, "reason": "fixture source present", "issuer": "synthetic-test-author", "proofs": ["proof_status"]}
                                 for start, end in (("09:30:00", "09:31:00"), ("09:31:00", "09:32:00"))]},
            "actions": {"symbols": [SYMBOL], "from_date": "2026-09-25", "through_date": "2026-09-29",
                        "complete": True, "events": [], "proofs": ["proof_actions"]},
            "attestation": {"issuer": "synthetic-test-author", "issued_at": "2026-09-29T08:00:00+08:00",
                            "source_kind": "synthetic_fixture", "symbols": [SYMBOL], "from_date": "2026-09-25",
                            "through_date": "2026-09-29", "complete": True, "limitations": [FIXTURE_NOTICE],
                            "claims": {name: {"conclusion": claim, "proofs": ["proof_" + name]} for name, claim in (
                                ("calendar", "complete_trading_calendar"), ("timing", "completed_bucket_available_at_end"),
                                ("units", "incremental_volume_units_verified"), ("instruments", "ordinary_main_raw_facts_verified"),
                                ("actions", "complete_no_company_actions"), ("status", "complete_halt_missing_grid"),
                                ("marks", "raw_contemporaneous_grid"))}},
        }
        # Independently pinned fabricated observations and company-action inputs.
        # These exercise saved proof structure, never host authenticity.
        self.action_paths = {}
        for name, table in (
            ("ex_date_index", pa.table({"symbol": pa.array([], type=pa.string()),
                                       "ex_date": pa.array([], type=pa.string())})),
            ("adj_factor", pa.table({"symbol": [SYMBOL, SYMBOL],
                                     "date": ["2026-09-25", "2026-09-29"], "factor": ["1", "1"]})),
        ):
            path = self.lake / (name + ".parquet")
            pq.write_table(table, path)
            self.action_paths[name] = path
        attestation = self.sidecars.pop("attestation")
        self.sidecars["observations"] = {
            "rows": [{"subject": name, "conclusion": claim["conclusion"], "fixture_notice": FIXTURE_NOTICE}
                     for name, claim in attestation["claims"].items()]
        }
        for index, (name, claim) in enumerate(attestation["claims"].items()):
            self.sidecars["proof_" + name] = {
                "issuer": "synthetic-test-author", "subject": name,
                "source_refs": ["ex_date_index", "adj_factor"] if name == "actions" else ["observations"],
                "filter": {"symbols": [SYMBOL], "from_date": "2026-09-25", "through_date": "2026-09-29",
                           "predicate": "symbol in declared universe and date within inclusive coverage window"},
                "result": {"complete": True, "summary": claim["conclusion"] + " (fabricated fixture)",
                           "rows": [] if name == "actions" else [
                               {"source": "observations", "row": index, "observation": claim["conclusion"]}]},
                "limitations": [FIXTURE_NOTICE, "Fabricated saved results; completeness needs independent host review."],
            }
        self.sidecars["attestation"] = attestation
        execution = execution_identity()
        self.recipe = {
            "schema_version": "minute_orders_source_recipe_v1", "unit": "B-L2-01", "source_kind": "synthetic_fixture",
            "registered_at": "2026-09-29T09:00:00+08:00", "run_id": "fixture", "parent": str(tmp_path / "out"),
            "invocation": ["fixture-only API", "load_minute_orders_source -> run_minute_orders_research_with_artifacts"],
            "symbols": ["symbol=603196_SH"], "start_at": at("09:28:00"), "end_at": at("15:00:00"),
            "intervals": [{"start": at("09:30:00"), "end": at("09:32:00")}],
            "mark_grid": [{"mark_id": name, "event_time": at(t), "prices": [
                {"symbol": SYMBOL, "source": "bars", "row": index, "symbol_column": "symbol", "time_column": "time", "price_column": "close",
                 "time": {"encoding": "iso_offset", "timezone": "Asia/Shanghai", "label": "START"}}]}
                          for name, t, index in (("spot", "09:31:00", 0), ("final", "15:00:00", 4))],
            "orders_observed_sample": True,
            "implementation": {"code_sha": execution["code_sha"], "python_version": execution["python_version"],
                               "pyarrow_version": execution["pyarrow_version"], "transform_version": TRANSFORM_VERSION},
            "sources": [{"id": "bars", "location": {"kind": "minute", "symbol": SYMBOL}, "format": "parquet",
                         "schema": {"symbol": "string", "time": "string", "close": "double", "volume": "int64"}, "sha256": ""}],
            "roles": {role: role for role in ("calendar", "instruments", "status", "actions", "commands", "account", "attestation")},
            "bars": [{"source": "bars", "columns": {"symbol": "symbol", "time": "time", "close": "close", "volume": "volume"},
                      "time": {"encoding": "iso_offset", "timezone": "Asia/Shanghai", "label": "START"},
                      "volume": {"kind": "incremental", "unit": "shares", "shares_per_unit": 1},
                      "availability": "bucket_end", "price_domain": "raw"}],
        }
        for name, path in self.action_paths.items():
            self.recipe["sources"].append({"id": name, "location": {"kind": "loose", "name": path.name},
                                            "format": "parquet", "schema": {f.name: str(f.type) for f in pq.read_schema(path)},
                                            "sha256": ""})
        for role in self.sidecars:
            self.recipe["sources"].append({"id": role, "location": {"kind": "sidecar", "path": str(tmp_path / (role + ".json"))},
                                            "format": "json", "schema": "bl2_proof_v1" if role.startswith("proof_") else f"bl2_{role}_v1",
                                            "sha256": ""})
        self.attest_fabricated_bindings()
        self.freeze()

    def attest_fabricated_bindings(self):
        """Explicit test-author assertion, NEVER auto-refresh proofs in freeze()."""
        bindings = {
            "units": [{"source": b["source"], "column": b["columns"]["volume"], **b["volume"]}
                      for b in self.recipe["bars"]],
            "status": [{k: v for k, v in row.items() if k != "proofs"}
                       for row in self.sidecars["status"]["rows"]],
            "instruments": [
                {**{k: v for k, v in row.items() if k not in ("proofs", "derivation")},
                 "derivation": {k: v for k, v in row["derivation"].items() if k != "independent_verification"}}
                for row in self.sidecars["instruments"]["rows"]],
        }
        for subject, values in bindings.items():
            proof = self.sidecars["proof_" + subject]
            source_row = next(i for i, r in enumerate(self.sidecars["observations"]["rows"])
                              if r["subject"] == subject)
            if subject == "units":
                self.sidecars["observations"]["rows"][source_row].update(
                    basis="source_declaration", unit_declaration={
                        k: values[0][k] for k in ("column", "kind", "unit", "shares_per_unit")})
            proof["result"]["rows"] = [
                {"source": "observations", "row": source_row, "observation": "Fabricated test assertion only",
                 "basis": {"units": "source_declaration", "status": "explicit_status"}.get(subject, b.get("origin")),
                 "binding": deepcopy(b)} for b in values]

    def approve_fabricated_derivation(self):
        row = self.sidecars["instruments"]["rows"][0]
        row["origin"] = "approved_derivation"
        row["derivation"] = {"inputs": ["observations"], "approved_rule_version": "fabricated-rule-v1",
                             "independent_verification": ["proof_verification"]}
        self.attest_fabricated_bindings()
        proof = deepcopy(self.sidecars["proof_instruments"])
        proof["issuer"] = "independent-synthetic-test-reviewer"
        self.sidecars["proof_verification"] = proof
        self.recipe["sources"].insert(-1, {
            "id": "proof_verification", "location": {"kind": "sidecar", "path": str(self.root / "verification.json")},
            "format": "json", "schema": "bl2_proof_v1", "sha256": "",
        })
        self.sidecars["attestation"]["claims"]["instruments"]["proofs"].append("proof_verification")

    def use_vendor_schema(self):
        # Schema mirror only: timestamps, prices, units and facts are fabricated.
        self.rows = [
            {"time": int(datetime.fromisoformat(row["time"]).timestamp()) * 1000,
             "open": row["close"], "high": row["close"], "low": row["close"], "close": row["close"],
             "volume": row["volume"], "amount": float(row["volume"]) * row["close"],
             "__index_level_0__": datetime.fromisoformat(row["time"]).replace(tzinfo=None)}
            for row in self.rows
        ]
        self.recipe["bars"][0]["columns"]["symbol"] = {"kind": "partition"}
        self.recipe["bars"][0]["time"]["encoding"] = "epoch_ms"
        for mark in self.recipe["mark_grid"]:
            mark["prices"][0]["symbol_column"] = {"kind": "partition"}
            mark["prices"][0]["time"]["encoding"] = "epoch_ms"

    def freeze(self, *, write_bars=True):
        if write_bars:
            table = pa.Table.from_pylist(self.rows)
            if "__index_level_0__" in table.column_names:
                index = table.schema.get_field_index("__index_level_0__")
                table = table.set_column(index, "__index_level_0__", table.column(index).cast(pa.timestamp("ns")))
            pq.write_table(table, self.bar_path)
            self.recipe["sources"][0]["schema"] = {f.name: str(f.type) for f in pq.read_schema(self.bar_path)}
        for spec in self.recipe["sources"]:
            if spec["id"] == "bars":
                path = self.bar_path
            elif spec["id"] in self.action_paths:
                path = self.action_paths[spec["id"]]
            else:
                path = Path(spec["location"]["path"])
                if spec["id"] == "attestation":
                    self.sidecars["attestation"]["scope_hash"] = attestation_scope(self.recipe)
                path.write_text(json.dumps({"schema_version": spec["schema"], "data": self.sidecars[spec["id"]]},
                                           ensure_ascii=False), encoding="utf-8")
            spec["sha256"] = sha256(path.read_bytes())
        self.path.write_text(json.dumps(self.recipe, ensure_ascii=False), encoding="utf-8")
        self.digest = sha256(self.path.read_bytes())

    def load(self):
        return load_minute_orders_source(self.path, expected_sha256=self.digest)


@pytest.fixture
def source_case(tmp_path, monkeypatch):
    return SyntheticCase(tmp_path, monkeypatch)


@pytest.mark.parametrize("encoding,expected", [
    ("epoch_ms_wall_shanghai_as_utc", "2025-10-23T09:30:00+08:00"),
    ("epoch_ms", "2025-10-23T17:30:00+08:00"),
])
def test_explicit_wall_encoding_preserves_old_epoch_instant(encoding, expected):
    spec = {"encoding": encoding, "timezone": "Asia/Shanghai", "label": "END"}
    assert source_loader._time(1761211800000, spec, "fixture").isoformat() == expected


@pytest.mark.parametrize("value, message", [
    (True, "^fixture: wall epoch ms must be an integer$"),
    ("1761211800000", "^fixture: wall epoch ms must be an integer$"),
    (1761211800000.0, "^fixture: wall epoch ms must be an integer$"),
    (None, "^fixture: wall epoch ms must be an integer$"),
    (10**30, "^fixture: invalid timestamp: "),
])
def test_wall_encoding_rejects_non_integer_or_overflow(value, message):
    with pytest.raises(SourceContractError, match=message):
        source_loader._time(value, {"encoding": "epoch_ms_wall_shanghai_as_utc",
                                   "timezone": "Asia/Shanghai", "label": "END"}, "fixture")


@pytest.fixture
def wall_case(source_case, monkeypatch):
    """Fabricated approval trust anchor only; never claim these bytes are lake evidence."""
    case = source_case
    case.use_vendor_schema()  # The existing real-epoch fixture recipe remains unchanged.
    for row in case.rows:
        wall = row["__index_level_0__"] + timedelta(minutes=1)  # START fixture -> END fixture.
        row["__index_level_0__"] = wall
        row["time"] = int(wall.replace(tzinfo=UTC).timestamp()) * 1000
    time = {"encoding": "epoch_ms_wall_shanghai_as_utc", "timezone": "Asia/Shanghai", "label": "END"}
    case.recipe["bars"][0]["time"] = time
    for point in case.recipe["mark_grid"]:
        point["prices"][0]["time"] = deepcopy(time)
    case.freeze()
    sources = {s["id"]: s for s in case.recipe["sources"]}
    case.sidecars["encoding_approval"] = {"rows": [{
        "approval_id": "fabricated-test-author-approval", "r4_authorized": False,
        "fixture_notice": FIXTURE_NOTICE,
        "binding": {"source": "bars", "source_sha256": sources["bars"]["sha256"],
                    "column": "time", "source_type": "int64", "symbol": SYMBOL, **time,
                    "availability": "bucket_end", "from_date": "2026-09-28", "through_date": "2026-09-28"},
        "evidence_refs": {"observations": sources["observations"]["sha256"]},
    }]}
    case.recipe["sources"].insert(-1, {
        "id": "encoding_approval", "location": {"kind": "sidecar", "path": str(case.root / "encoding_approval.json")},
        "format": "json", "schema": "bl2_time_encoding_approval_v1", "sha256": "",
    })
    proof = case.sidecars["proof_timing"]
    proof["source_refs"].append("encoding_approval")
    proof["result"]["rows"].append({"source": "encoding_approval", "row": 0, "observation": FIXTURE_NOTICE})
    case.freeze(write_bars=False)
    # Production has no synthetic bypass. Replace the one pinned approval only
    # inside this test to exercise full mapping/audit with fabricated parquet.
    monkeypatch.setattr(source_loader, "_TIME_ENCODING_APPROVAL_SHA256",
                        next(s["sha256"] for s in case.recipe["sources"] if s["id"] == "encoding_approval"))
    return case


def test_bound_wall_encoding_loads_end_buckets_and_marks_with_audit(wall_case):
    loaded = wall_case.load()
    run = loaded.run_input
    assert [(b.start.isoformat(), b.end.isoformat()) for b in run.buckets] == [
        (at("09:30:00"), at("09:31:00")), (at("09:31:00"), at("09:32:00"))]
    assert run.marks[-1].event_time.isoformat() == at("15:00:00")
    doc = loaded.provenance.document()
    assert doc["transform"]["version"] == "bl2_source_transform_v6"
    for row, raw in zip(doc["transform"]["bars"], wall_case.rows):
        assert row["original_time"] == str(raw["time"])
        assert row["time_source_type"] == "int64"
        assert row["time"] == wall_case.recipe["bars"][0]["time"]
        assert row["time_proofs"][0]["approval_id"] == "fabricated-test-author-approval"
        assert row["available_at"] == row["end"]
    assert doc["transform"]["excluded"][0]["excluded_count"] == 3
    assert doc["transform"]["marks"][-1]["original_time"] == str(wall_case.rows[-1]["time"])
    assert doc["transform"]["marks"][-1]["time_proofs"]
    assert doc["notice"] == FIXTURE_NOTICE


@pytest.mark.parametrize("change,match", [
    ("no_binding", "matching pinned HOST approval binding required"),
    ("not_claimed", "matching pinned HOST approval binding required"),
    ("approval_pin", "HOST approval pin mismatch"),
    ("source_hash", "source/column/mapping binding mismatch"),
    ("column", "approved int64 minute source required"),
    ("label", "source/column/mapping binding mismatch"),
    ("timezone", "source/column/mapping binding mismatch"),
    ("window", "approval window coverage gap"),
    ("missing_material", "pinned approval material missing or changed"),
    ("changed_material", "pinned approval material missing or changed"),
    ("incomplete", "complete saved result required"),
])
def test_wall_encoding_binding_fails_closed(wall_case, change, match):
    case = wall_case
    proof = case.sidecars["proof_timing"]
    write_bars = False
    if change == "no_binding":
        proof["result"]["rows"].pop()
    elif change == "not_claimed":
        case.sidecars["proof_unused_timing"] = deepcopy(proof)
        case.recipe["sources"].insert(-1, {
            "id": "proof_unused_timing", "location": {"kind": "sidecar", "path": str(case.root / "unused.json")},
            "format": "json", "schema": "bl2_proof_v1", "sha256": "",
        })
        proof["result"]["rows"].pop()
    elif change == "approval_pin":
        case.sidecars["encoding_approval"]["rows"][0]["r4_authorized"] = True
    elif change == "source_hash":
        case.rows[-1]["amount"] += 1.0
        write_bars = True
    elif change == "column":
        case.recipe["bars"][0]["columns"]["time"] = "close"
    elif change in ("label", "timezone"):
        case.recipe["bars"][0]["time"][change] = "START" if change == "label" else "UTC"
    elif change == "window":
        case.recipe["start_at"] = "2026-09-27T09:28:00+08:00"
    elif change == "missing_material":
        proof["result"]["rows"] = proof["result"]["rows"][-1:]
        proof["source_refs"].remove("observations")
    elif change == "changed_material":
        case.sidecars["observations"]["rows"][0]["fixture_notice"] += " changed"
    else:
        proof["result"]["complete"] = False
    case.freeze(write_bars=write_bars)
    with pytest.raises(SourceContractError, match=match):
        case.load()
    assert not Path(case.recipe["parent"]).exists()


def test_explicit_mapping_and_excluded_rows_keep_independent_1500_mark(source_case):
    loaded = source_case.load()
    run, doc = loaded.run_input, loaded.provenance.document()
    assert [b.symbol for b in run.buckets] == [SYMBOL, SYMBOL]
    assert [b.volume_shares for b in run.buckets] == [1000, 500]
    assert all(b.close == Decimal("10.0") for b in run.buckets)
    assert run.commands[0].symbol == SYMBOL
    assert run.marks[-1].event_time.hour == 15
    assert all(b.end.hour < 15 for b in run.buckets)
    assert doc["transform"]["excluded"][0]["excluded_count"] == 3
    assert [r["row"] for r in doc["transform"]["excluded"][0]["excluded_rows"]] == [2, 3, 4]
    assert doc["source_kind"] == "synthetic_fixture" and doc["notice"] == FIXTURE_NOTICE
    assert all(row["unchanged"] for row in doc["source_checks_at_load"])
    assert not Path(source_case.recipe["parent"]).exists()


@pytest.mark.parametrize("noisy,expected", [
    (23.310000000000002, "23.31"), (23.830000000000002, "23.83"),
])
def test_double_price_residue_is_attested_for_buckets_and_marks(source_case, noisy, expected):
    for row in source_case.rows:
        row["close"] = noisy
    source_case.sidecars["instruments"]["rows"][0]["facts"].update(
        reference_price="23.00", limit_down="20.00", limit_up="26.00")
    source_case.sidecars["commands"]["commands"][0]["limit"] = "23.00"
    source_case.attest_fabricated_bindings()
    source_case.freeze()
    loaded = source_case.load()
    assert all(b.close.as_tuple() == Decimal(expected).as_tuple() for b in loaded.run_input.buckets)
    assert all(p.price.as_tuple() == Decimal(expected).as_tuple()
               for m in loaded.run_input.marks for p in m.prices)
    transform = loaded.provenance.document()["transform"]
    assert transform["version"] == "bl2_source_transform_v6"
    for record in ([b["price"] for b in transform["bars"]]
                   + [m["conversion"] for m in transform["marks"]]):
        assert record == {"source_type": "double", "original": repr(noisy),
                          "decimal_text": expected, "quantized_text": expected,
                          "rule": "double_repr_cent_quantize_v1", "quantized": True,
                          "residue": "2E-15", "max_abs_residue": "1E-9", "rounding": "ROUND_HALF_EVEN"}
    assert all(b["volume"]["rule"] == "double_repr_or_exact_decimal_v1" for b in transform["bars"])


@pytest.mark.parametrize("value,expected,residue", [
    (23.31, "23.31", "0"), (10.0, "10.0", "0"),
    (23.309999999999995, "23.31", "5E-15"),
    (10.000000001, "10.00", "1E-9"), (9.999999999, "10.00", "1E-9"),
])
def test_double_price_rule_preserves_aligned_values_and_accepts_inclusive_bound(value, expected, residue):
    # Ambient precision, rounding and inexact traps must not alter the rule.
    with localcontext() as ctx:
        ctx.prec, ctx.rounding = 6, ROUND_UP
        ctx.traps[Inexact] = ctx.traps[Rounded] = True
        price, audit = source_loader._price_decimal(value, "double", "test close")
    assert price.as_tuple() == Decimal(expected).as_tuple()
    assert audit["original"] == repr(value) and audit["decimal_text"] == expected
    assert audit["rule"] == "double_repr_cent_quantize_v1"
    assert Decimal(audit["residue"]) == Decimal(residue)
    assert audit["quantized"] is (residue != "0")
    assert money_cents(price, "test close") == int(Decimal(expected) * 100)


@pytest.mark.parametrize("value", [10.001, 10.005, 10.000000001000002, 9.999999998999998])
def test_double_price_rule_rejects_subcents_outside_bound(value):
    with pytest.raises(SourceContractError, match="double_repr_cent_quantize_v1.*cent-aligned.*exceeds"):
        source_loader._price_decimal(value, "double", "test close")


@pytest.mark.parametrize("value,arrow_type", [
    ("10.001", "string"), (Decimal("10.001"), "decimal128(5, 3)"),
    ("23.310000000000002", "string"),
    (Decimal("23.310000000000002"), "decimal128(17, 15)"), (10, "int64"),
])
def test_exact_prices_never_take_double_noise_allowance(value, arrow_type):
    price, audit = source_loader._price_decimal(value, arrow_type, "test close")
    assert price.as_tuple() == Decimal(str(value)).as_tuple()
    assert audit["rule"] == "double_repr_or_exact_decimal_v1"
    assert "quantized_text" not in audit
    if type(value) is not int:
        with pytest.raises(FeeContractError, match="cent-aligned"):
            money_cents(price, "test close")


@pytest.mark.parametrize("index,where", [(0, "close"), (-1, "mark price")])
def test_parquet_double_subcent_prices_fail_at_transform(source_case, index, where):
    source_case.rows[index]["close"] = 10.001
    source_case.freeze()
    with pytest.raises(SourceContractError, match=where + ": double_repr_cent_quantize_v1.*cent-aligned"):
        source_case.load()


def test_parquet_double_volume_residue_is_not_price_quantized(source_case):
    for row in source_case.rows:
        row["volume"] = float(row["volume"])
    source_case.rows[0]["volume"] = 1000.0000000000001
    source_case.freeze()
    with pytest.raises(SourceContractError, match="exact integer shares"):
        source_case.load()


@pytest.mark.parametrize("tag", [SYMBOL, "603196_SH", "symbol=603196_SH"])
def test_canonical_symbol_tags(source_case, tag):
    source_case.recipe["symbols"] = [tag]
    source_case.freeze()
    assert source_case.load().run_input.instruments[0].symbol == SYMBOL


@pytest.mark.parametrize("tag", ["603196", "../603196_SH", "603196_US", "symbol=../603196_SH"])
def test_invalid_symbol_tags(source_case, tag):
    source_case.recipe["symbols"] = [tag]
    source_case.freeze()
    with pytest.raises(SourceContractError, match="symbol"):
        source_case.load()


def test_end_labels_and_exact_fractional_lots(source_case):
    from datetime import timedelta
    for row in source_case.rows:
        row["time"] = (datetime.fromisoformat(row["time"]) + timedelta(minutes=1)).isoformat()
        row["volume"] = str(Decimal(row["volume"]) / 100)
    source_case.recipe["bars"][0]["time"]["label"] = "END"
    source_case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
    for mark in source_case.recipe["mark_grid"]:
        mark["prices"][0]["time"]["label"] = "END"
    source_case.attest_fabricated_bindings()
    source_case.freeze()
    loaded = source_case.load()
    assert [b.volume_shares for b in loaded.run_input.buckets] == [1000, 500]
    assert loaded.provenance.document()["transform"]["bars"][0]["shares_per_unit"] == 100


@pytest.mark.parametrize("encoding", ["naive_shanghai", "epoch_s", "epoch_ms", "epoch_us", "datetime_shanghai"])
def test_explicit_timestamp_decoding(source_case, encoding):
    for row in source_case.rows:
        value = datetime.fromisoformat(row["time"])
        if encoding == "naive_shanghai":
            row["time"] = value.replace(tzinfo=None).isoformat()
        elif encoding == "datetime_shanghai":
            row["time"] = value
        else:
            row["time"] = int(value.timestamp()) * {"epoch_s": 1, "epoch_ms": 1000, "epoch_us": 1_000_000}[encoding]
    source_case.recipe["bars"][0]["time"]["encoding"] = encoding
    for mark in source_case.recipe["mark_grid"]:
        mark["prices"][0]["time"]["encoding"] = encoding
    source_case.freeze()
    assert source_case.load().run_input.buckets[0].start.isoformat() == at("09:30:00")


@pytest.mark.parametrize(("field", "value", "message"), [
    ("time.label", "UNKNOWN", "START/END"), ("time.timezone", "UTC", "timezone"),
    ("time.encoding", "guess", "encoding"), ("availability", "after_end", "availability"),
    ("price_domain", "front", "price domain"), ("volume.kind", "cumulative", "volume"),
    ("volume.unit", "unknown", "volume"), ("volume.shares_per_unit", 100, "factor"),
    ("volume.shares_per_unit", True, "factor"),
])
def test_reject_mapping_semantics(source_case, field, value, message):
    target = source_case.recipe["bars"][0]
    *parts, key = field.split(".")
    for part in parts:
        target = target[part]
    target[key] = value
    source_case.freeze()
    with pytest.raises(SourceContractError, match=message):
        source_case.load()


@pytest.mark.parametrize(("column", "value", "message"), [
    ("volume", "-1", "negative"), ("volume", "1.5", "integer shares"),
    ("volume", "NaN", "nonfinite"), ("close", "Infinity", "nonfinite"),
    ("close", "10.001", "cent-aligned"), ("close", "12.00", "daily price limits"),
    ("symbol", "603197.SH", "partition/symbol"),
])
def test_bad_source_values_fail_closed(source_case, column, value, message):
    for row in source_case.rows:
        row[column] = str(row[column])
    source_case.rows[0][column] = value
    source_case.freeze()
    with pytest.raises(ValueError, match=message):
        source_case.load()


def test_missing_halt_and_zero_are_distinct_with_full_evidence(source_case):
    source_case.rows[0]["volume"] = 0
    source_case.sidecars["status"]["rows"][0]["halted"] = True
    source_case.rows.pop(1)
    source_case.sidecars["status"]["rows"][1]["missing"] = True
    source_case.recipe["mark_grid"][-1]["prices"][0]["row"] -= 1
    source_case.attest_fabricated_bindings()
    source_case.freeze()
    first, missing = source_case.load().run_input.buckets
    assert first.volume_shares == 0 and first.halted and not first.missing
    assert missing.missing and not missing.halted and missing.close is None and missing.volume_shares is None


@pytest.mark.parametrize("case", ["status_gap", "missing_conflict", "source_gap", "duplicate", "actions_gap", "event", "no_proof", "attestation_gap", "false_without_proof"])
def test_coverage_rejections(source_case, case):
    if case == "status_gap":
        source_case.sidecars["status"]["rows"].pop()
    elif case == "missing_conflict":
        source_case.sidecars["status"]["rows"][0]["missing"] = True
        source_case.attest_fabricated_bindings()
    elif case == "source_gap":
        source_case.rows.pop(1)
    elif case == "duplicate":
        source_case.rows.append(deepcopy(source_case.rows[0]))
    elif case == "actions_gap":
        source_case.sidecars["actions"]["from_date"] = "2026-09-29"
    elif case == "event":
        source_case.sidecars["actions"]["events"] = [{"cash": "1.00"}]
    elif case == "no_proof":
        source_case.sidecars["attestation"]["claims"]["actions"]["proofs"] = []
    elif case == "attestation_gap":
        source_case.sidecars["attestation"]["complete"] = False
    else:
        source_case.sidecars["status"]["rows"][0]["proofs"] = []
    source_case.freeze()
    with pytest.raises(SourceContractError, match="coverage|conflict|gap|duplicate|company actions|proof"):
        source_case.load()


@pytest.mark.parametrize("subject", ["calendar", "timing", "units", "instruments", "actions", "status", "marks"])
@pytest.mark.parametrize("payload", [{}, {"placeholder": True}, {"issuer": "synthetic-test-author"}])
def test_content_free_proof_objects_fail_closed(source_case, subject, payload):
    source_case.sidecars["proof_" + subject] = payload
    source_case.freeze()
    with pytest.raises(SourceContractError, match="proof.*schema fields"):
        source_case.load()


@pytest.mark.parametrize(("field", "value", "message"), [
    ("issuer", " ", "issuer"),
    ("source_refs", [], "pinned source refs"),
    ("source_refs", ["unknown"], "pinned source refs"),
    ("source_refs", ["proof_status"], "own evidence"),
    ("source_refs", ["attestation"], "own evidence"),
    ("filter.symbols", [], "symbol universe"),
    ("filter.from_date", "2026-09-30", "reversed filter dates"),
    ("filter.predicate", " ", "filter predicate"),
    ("result.complete", False, "complete saved result"),
    ("result.summary", " ", "result summary"),
    ("result.rows", [], "saved observations"),
    ("result.rows", [{}], "observation.*schema fields"),
    ("result.rows", [{"source": "bars", "row": 0, "observation": "present"}], "source ref and row index"),
    ("result.rows", [{"source": "observations", "row": True, "observation": "present"}], "source ref and row index"),
    ("result.rows", [{"source": "observations", "row": 0, "observation": " "}], "observation"),
    ("limitations", [], "limitations"),
])
def test_proof_requires_pinned_scoped_saved_evidence(source_case, field, value, message):
    target = source_case.sidecars["proof_timing"]
    *parts, key = field.split(".")
    for part in parts:
        target = target[part]
    target[key] = value
    source_case.freeze()
    with pytest.raises(SourceContractError, match=message):
        source_case.load()


@pytest.mark.parametrize("target", ["status", "actions", "attestation"])
def test_proof_refs_cannot_substitute_an_unrelated_claim(source_case, target):
    if target == "status":
        row = source_case.sidecars["status"]["rows"][0]
    elif target == "actions":
        row = source_case.sidecars["actions"]
    else:
        row = source_case.sidecars["attestation"]["claims"]["actions"]
    row["proofs"] = ["proof_timing"]
    source_case.freeze()
    with pytest.raises(SourceContractError, match="proof subject mismatch"):
        source_case.load()


def test_company_action_proof_requires_saved_empty_filter_result(source_case):
    source_case.sidecars["proof_actions"]["result"]["rows"] = [{"symbol": SYMBOL, "cash": "1.00"}]
    source_case.freeze()
    with pytest.raises(SourceContractError, match="company actions.*empty saved filter result"):
        source_case.load()


@pytest.mark.parametrize("case", ["no_final", "no_spot", "universe_gap", "wrong_time", "missing_row", "off_tick", "disabled"])
def test_mark_rejections(source_case, case):
    if case == "no_final":
        source_case.recipe["mark_grid"][-1]["event_time"] = at("14:59:00")
    elif case == "no_spot":
        source_case.recipe["mark_grid"].pop(0)
    elif case == "universe_gap":
        source_case.recipe["mark_grid"][0]["prices"] = []
    elif case == "wrong_time":
        source_case.recipe["mark_grid"][0]["prices"][0]["row"] = 1
    elif case == "missing_row":
        source_case.recipe["mark_grid"][0]["prices"][0]["row"] = 100
    elif case == "off_tick":
        source_case.rows[-1]["close"] = 10.001
    else:
        source_case.sidecars["account"]["requires_marks"] = False
    source_case.freeze()
    with pytest.raises(ValueError, match="mark|exact cents"):
        source_case.load()


@pytest.mark.parametrize("case", ["unconfigured", "nonexistent", "partition", "schema", "hash", "recipe_hash"])
def test_root_schema_and_hash_fail_closed(source_case, monkeypatch, case):
    if case == "unconfigured":
        monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT")
    elif case == "nonexistent":
        monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(source_case.root / "absent"))
    elif case == "partition":
        source_case.bar_path.unlink()
    elif case == "schema":
        source_case.recipe["sources"][0]["schema"]["close"] = "string"
        source_case.path.write_text(json.dumps(source_case.recipe), encoding="utf-8")
        source_case.digest = sha256(source_case.path.read_bytes())
    elif case == "hash":
        with source_case.bar_path.open("ab") as stream:
            stream.write(b"changed")
    else:
        source_case.digest = "0" * 64
    with pytest.raises((ValueError, RuntimeError), match="configured|missing|unreadable|schema|hash"):
        source_case.load()


def test_authority_marker_and_period_override_are_recorded(source_case, monkeypatch):
    monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT")
    monkeypatch.setenv("OSKH_AUTHORITY_HINT_ROOT", str(source_case.lake))
    (source_case.lake / ".authority").write_text("synthetic authority fixture", encoding="utf-8")
    monkeypatch.setenv("OSKH_PERIOD_1M_ROOT", str(source_case.lake / "stock/period=1m"))
    loaded = source_case.load()
    doc = loaded.provenance.document()
    assert doc["resolver"]["basis"] == "AUTHORITY_HINT"
    assert any(s["id"] == "authority_marker" for s in doc["snapshots"])


@pytest.mark.parametrize("case", ["main", "raw", "listing", "facts_gap", "late_facts", "derivation", "next_date", "default_fee", "session_gap", "auction", "session_gap_covered", "lunch_covered", "auction_covered", "duplicate_symbol"])
def test_fact_calendar_economic_recipe_rejections(source_case, case):
    facts = source_case.sidecars["instruments"]["rows"][0]
    error, message = ValueError, None
    if case == "main":
        facts["facts"]["board"] = "star"
    elif case == "raw":
        facts["facts"]["price_domain"] = "front"
    elif case == "listing":
        facts["ordinary_listing"] = False
    elif case == "facts_gap":
        facts["facts"]["trade_date"] = "2026-09-29"
    elif case == "late_facts":
        facts["available_at"] = at("10:00:00")
    elif case == "derivation":
        facts["origin"] = "approved_derivation"
    elif case == "next_date":
        source_case.sidecars["calendar"]["trading_dates"].pop()
    elif case == "default_fee":
        del source_case.sidecars["account"]["buy_fees"]
    elif case in ("session_gap", "session_gap_covered"):
        source_case.recipe["intervals"] = [{"start": at("09:30:00"), "end": at("09:31:00")},
                                            {"start": at("09:32:00"), "end": at("09:33:00")}]
    elif case in ("auction", "auction_covered"):
        source_case.recipe["intervals"] = [{"start": at("14:57:00"), "end": at("14:58:00")}]
    elif case == "lunch_covered":
        source_case.recipe["intervals"] = [{"start": at("12:00:00"), "end": at("12:01:00")}]
    else:
        source_case.recipe["symbols"].append(SYMBOL)
    if case.endswith("_covered"):
        # Match the entire status grid so refusal reaches BrokerCore -> Clock.
        template = source_case.sidecars["status"]["rows"][0]
        source_case.sidecars["status"]["rows"] = [
            {**deepcopy(template), **interval,
             "missing": not any(row["time"] == interval["start"] for row in source_case.rows)}
            for interval in source_case.recipe["intervals"]
        ]
        source_case.attest_fabricated_bindings()
        error = RunContractError
        message = ("session gap must be covered by explicit missing buckets" if case == "session_gap_covered"
                   else "bucket crosses lunch or continuous session endpoints")
    elif case in ("session_gap", "auction"):
        error, message = SourceContractError, "halt/missing coverage grid mismatch"
    source_case.freeze()
    with pytest.raises(error, match=message):
        source_case.load()


def test_last_continuous_bucket_ends_at_1457(source_case):
    interval = {"start": at("14:56:00"), "end": at("14:57:00")}
    source_case.recipe["intervals"] = [interval]
    source_case.sidecars["status"]["rows"] = [{**source_case.sidecars["status"]["rows"][0], **interval}]
    source_case.attest_fabricated_bindings()
    source_case.freeze()
    bucket, = source_case.load().run_input.buckets
    assert bucket.start.isoformat() == interval["start"]
    assert bucket.end.isoformat() == interval["end"]


def test_attestation_cannot_be_reused_after_changing_mapping(source_case):
    # Deliberately preserve the old attestation bytes/hash.
    source_case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
    source_case.path.write_text(json.dumps(source_case.recipe), encoding="utf-8")
    source_case.digest = sha256(source_case.path.read_bytes())
    with pytest.raises(SourceContractError, match="attestation scope hash mismatch"):
        source_case.load()


def test_mark_cannot_reinterpret_same_minute_source_timestamp(source_case):
    source_case.recipe["mark_grid"][0]["prices"][0]["time"]["label"] = "END"
    source_case.recipe["mark_grid"][0]["event_time"] = at("09:30:00")
    source_case.freeze()
    with pytest.raises(SourceContractError, match="preserve the minute source"):
        source_case.load()


def test_artifact_parent_cannot_write_inside_source_root(source_case):
    source_case.recipe["parent"] = str(source_case.lake / "outputs")
    source_case.freeze()
    with pytest.raises(SourceContractError, match="read-only source roots"):
        source_case.load()


@pytest.mark.parametrize("field", ["code_sha", "python_version", "pyarrow_version", "transform_version"])
def test_implementation_and_numeric_conversion_runtime_are_pinned(source_case, field):
    source_case.recipe["implementation"][field] = "unknown"
    source_case.freeze()
    with pytest.raises(SourceContractError, match="implementation/runtime version mismatch"):
        source_case.load()


def test_decimal_source_keeps_precision_and_fractional_shares_are_never_rounded(source_case):
    for row in source_case.rows:
        row["close"] = Decimal("10.00")
        row["volume"] = Decimal("10.01")
    source_case.recipe["bars"][0]["volume"].update(unit="lots", shares_per_unit=100)
    source_case.attest_fabricated_bindings()
    source_case.freeze()
    loaded = source_case.load()
    assert loaded.run_input.buckets[0].close.as_tuple() == Decimal("10.00").as_tuple()
    assert loaded.run_input.buckets[0].volume_shares == 1001
    source_case.rows[0]["volume"] = Decimal("10.001")
    source_case.freeze()
    with pytest.raises(SourceContractError, match="integer shares"):
        source_case.load()


@pytest.mark.parametrize("partition_only", [False, True])
def test_all_universe_cells_sorted_and_all_marks_required(source_case, partition_only):
    if partition_only:
        source_case.use_vendor_schema()
        source_case.freeze()
    second_symbol = "000001.SZ"
    second_path = source_case.lake / "stock/period=1m/dividend_type=none/symbol=000001_SZ/data.parquet"
    second_path.parent.mkdir(parents=True)
    if partition_only:
        # Same fabricated quotes in two separately pinned symbol partitions.
        second_path.write_bytes(source_case.bar_path.read_bytes())
    else:
        rows = [{**row, "symbol": "000001_SZ"} for row in source_case.rows]
        pq.write_table(pa.Table.from_pylist(rows), second_path)
    source_case.recipe["symbols"].append(second_symbol)
    # Freeze the existing sources first, then add a second pinned partition.
    for key in ("actions", "attestation"):
        source_case.sidecars[key]["symbols"].append(second_symbol)
    for key in ("proof_status", "proof_instruments", "proof_units"):
        source_case.sidecars[key]["filter"]["symbols"].append(second_symbol)
    status = source_case.sidecars["status"]["rows"]
    status.extend([{**deepcopy(row), "symbol": second_symbol} for row in list(status)])
    facts = deepcopy(source_case.sidecars["instruments"]["rows"][0])
    facts["facts"]["symbol"] = second_symbol
    source_case.sidecars["instruments"]["rows"].append(facts)
    for mark in source_case.recipe["mark_grid"]:
        mark["prices"].append({**deepcopy(mark["prices"][0]), "symbol": second_symbol, "source": "bars2"})
    source_case.recipe["bars"].append({**deepcopy(source_case.recipe["bars"][0]), "source": "bars2"})
    source_case.attest_fabricated_bindings()
    source_case.freeze()
    spec = {**deepcopy(source_case.recipe["sources"][0]), "id": "bars2",
            "location": {"kind": "minute", "symbol": second_symbol}, "sha256": sha256(second_path.read_bytes())}
    source_case.recipe["sources"].append(spec)
    att = source_case.sidecars["attestation"]
    att["scope_hash"] = attestation_scope(source_case.recipe)
    att_spec = next(s for s in source_case.recipe["sources"] if s["id"] == "attestation")
    att_path = Path(att_spec["location"]["path"])
    att_path.write_text(json.dumps({"schema_version": "bl2_attestation_v1", "data": att}), encoding="utf-8")
    att_spec["sha256"] = sha256(att_path.read_bytes())
    source_case.path.write_text(json.dumps(source_case.recipe), encoding="utf-8")
    source_case.digest = sha256(source_case.path.read_bytes())
    run = source_case.load().run_input
    assert [b.symbol for b in run.buckets] == [second_symbol, SYMBOL, second_symbol, SYMBOL]
    assert all([p.symbol for p in m.prices] == [second_symbol, SYMBOL] for m in run.marks)
