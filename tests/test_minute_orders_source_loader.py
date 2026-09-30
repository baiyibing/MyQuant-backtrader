"""Small generated synthetic fixtures only. Fixture PASS != lake PASS."""

import json
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
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
            "proof": {"fixture_notice": FIXTURE_NOTICE, "issuer": "synthetic-test-author",
                      "boundary_samples": [{"source": "bars", "row": 0, "start": at("09:30:00"), "end": at("09:31:00")}],
                      "unit": "incremental shares", "limitation": "fabricated facts for mapping tests only"},
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
                                      "origin": "source_fact", "proofs": ["proof"], "derivation": {}}]},
            "status": {"rows": [{"symbol": SYMBOL, "start": at(start), "end": at(end), "missing": False,
                                  "halted": False, "reason": "fixture source present", "issuer": "synthetic-test-author", "proofs": ["proof"]}
                                 for start, end in (("09:30:00", "09:31:00"), ("09:31:00", "09:32:00"))]},
            "actions": {"symbols": [SYMBOL], "from_date": "2026-09-25", "through_date": "2026-09-29",
                        "complete": True, "events": [], "proofs": ["proof"]},
            "attestation": {"issuer": "synthetic-test-author", "issued_at": "2026-09-29T08:00:00+08:00",
                            "source_kind": "synthetic_fixture", "symbols": [SYMBOL], "from_date": "2026-09-25",
                            "through_date": "2026-09-29", "complete": True, "limitations": [FIXTURE_NOTICE],
                            "claims": {name: {"conclusion": claim, "proofs": ["proof"]} for name, claim in (
                                ("calendar", "complete_trading_calendar"), ("timing", "completed_bucket_available_at_end"),
                                ("units", "incremental_volume_units_verified"), ("instruments", "ordinary_main_raw_facts_verified"),
                                ("actions", "complete_no_company_actions"), ("status", "complete_halt_missing_grid"),
                                ("marks", "raw_contemporaneous_grid"))}},
        }
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
            "roles": {role: role for role in self.sidecars if role != "proof"},
            "bars": [{"source": "bars", "columns": {"symbol": "symbol", "time": "time", "close": "close", "volume": "volume"},
                      "time": {"encoding": "iso_offset", "timezone": "Asia/Shanghai", "label": "START"},
                      "volume": {"kind": "incremental", "unit": "shares", "shares_per_unit": 1},
                      "availability": "bucket_end", "price_domain": "raw"}],
        }
        for role in self.sidecars:
            self.recipe["sources"].append({"id": role, "location": {"kind": "sidecar", "path": str(tmp_path / (role + ".json"))},
                                            "format": "json", "schema": f"bl2_{role}_v1", "sha256": ""})
        self.freeze()

    def freeze(self, *, write_bars=True):
        if write_bars:
            pq.write_table(pa.Table.from_pylist(self.rows), self.bar_path)
            self.recipe["sources"][0]["schema"] = {f.name: str(f.type) for f in pq.read_schema(self.bar_path)}
        for spec in self.recipe["sources"]:
            if spec["id"] == "bars":
                path = self.bar_path
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


@pytest.mark.parametrize("case", ["main", "raw", "listing", "facts_gap", "late_facts", "derivation", "next_date", "default_fee", "session_gap", "auction", "duplicate_symbol"])
def test_fact_calendar_economic_recipe_rejections(source_case, case):
    facts = source_case.sidecars["instruments"]["rows"][0]
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
    elif case == "session_gap":
        source_case.recipe["intervals"] = [{"start": at("09:30:00"), "end": at("09:31:00")},
                                            {"start": at("09:32:00"), "end": at("09:33:00")}]
    elif case == "auction":
        source_case.recipe["intervals"] = [{"start": at("14:57:00"), "end": at("14:58:00")}]
    else:
        source_case.recipe["symbols"].append(SYMBOL)
    source_case.freeze()
    with pytest.raises(ValueError):
        source_case.load()


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
    source_case.freeze()
    loaded = source_case.load()
    assert loaded.run_input.buckets[0].close.as_tuple() == Decimal("10.00").as_tuple()
    assert loaded.run_input.buckets[0].volume_shares == 1001
    source_case.rows[0]["volume"] = Decimal("10.001")
    source_case.freeze()
    with pytest.raises(SourceContractError, match="integer shares"):
        source_case.load()


def test_all_universe_cells_sorted_and_all_marks_required(source_case):
    second_symbol = "000001.SZ"
    second_path = source_case.lake / "stock/period=1m/dividend_type=none/symbol=000001_SZ/data.parquet"
    second_path.parent.mkdir(parents=True)
    rows = [{**row, "symbol": "000001_SZ"} for row in source_case.rows]
    pq.write_table(pa.Table.from_pylist(rows), second_path)
    source_case.recipe["symbols"].append(second_symbol)
    # Freeze the existing sources first, then add a second pinned partition.
    for key in ("actions", "attestation"):
        source_case.sidecars[key]["symbols"].append(second_symbol)
    status = source_case.sidecars["status"]["rows"]
    status.extend([{**deepcopy(row), "symbol": second_symbol} for row in list(status)])
    facts = deepcopy(source_case.sidecars["instruments"]["rows"][0])
    facts["facts"]["symbol"] = second_symbol
    source_case.sidecars["instruments"]["rows"].append(facts)
    for mark in source_case.recipe["mark_grid"]:
        mark["prices"].append({**deepcopy(mark["prices"][0]), "symbol": second_symbol, "source": "bars2"})
    source_case.recipe["bars"].append({**deepcopy(source_case.recipe["bars"][0]), "source": "bars2"})
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
