"""Certified-real code-path tests, exclusively fabricated local tmp_path data."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

from backtest.research import delta5_certified_source as cert
from backtest.research.delta5_volume_ingress import IngressError, normalize
from common.infra.data_root import UnconfiguredDataRootError
from scripts.research import verify_delta5_real_volume_ingress as cli
from tests.fixtures.delta5_certified import fabricated_recipe, pin_json
from tests.fixtures.delta5_ingress import CODE, DAYS, fixture


def edit_pack(source, subject, mutate, *, original=True):
    spec = source["packs"][subject]
    path = Path(spec["path"])
    pack = json.loads(path.read_text())
    mutate(pack)
    source["packs"][subject] = pin_json(path, pack)
    if original:
        material = next(s for s in source["materials"] if s["id"] == f"original_{subject}")
        path = Path(material["path"])
        document = json.loads(path.read_text())
        document["rows"][0].update(binding=pack["binding"], basis=pack["basis"])
        material.update(pin_json(path, document))


@pytest.mark.parametrize("parquet", [False, True])
def test_complete_packs_map_fabricated_raw_bytes(tmp_path, monkeypatch, parquet):
    recipe = fabricated_recipe(tmp_path, monkeypatch, parquet=parquet)
    mapped = normalize(recipe["source"])
    expected = cli.native_inputs(fixture()["native"])
    assert mapped.canonical() == expected.canonical()
    assert type(mapped.samples[CODE, DAYS[0], 895].shares) is int
    audit = mapped.audit
    assert audit["source_kind"] == "certified-real"
    assert audit["source_certification"] == "verified"
    assert audit["certification_scope"] == "structure_and_pins_only"
    assert audit["evidence_origin"] == "fabricated_test"
    assert audit["real_lake_run"] == audit["host_attestation"] == "NOT_RUN"
    assert len(audit["pinned_inputs"]) == 12
    assert audit["resolver"]["environment"]["OSKH_SOURCE_PARQUET_ROOT"] == str(tmp_path / "invented-lake")


def add_neighbor(rows, period, side):
    row = deepcopy(rows[period][0])
    date = "2026-08-28" if side == "before" else "2026-09-02"
    if period == "1m":
        for key in ("timestamp", "begin", "end", "available_at"):
            row[key] = date + row[key][10:]
    else:
        row["day"] = date.replace("-", "")
    rows[period].insert(0 if side == "before" else len(rows[period]), row)
    return row


@pytest.mark.parametrize("parquet", [False, True])
@pytest.mark.parametrize("label", ["START", "END"])
def test_valid_neighbor_rows_are_checked_then_counted_and_excluded(tmp_path, monkeypatch, parquet, label):
    def neighbors(rows):
        for period in ("1m", "1d"):
            for side in ("before", "after"):
                add_neighbor(rows, period, side)

    source = fabricated_recipe(tmp_path, monkeypatch, parquet=parquet, label=label,
                               raw_mutator=neighbors)["source"]
    mapped = normalize(source)
    assert mapped.canonical() == cli.native_inputs(fixture()["native"]).canonical()
    assert mapped.audit["source_certification"] == "verified"
    assert mapped.audit["raw_row_counts"] == {
        "1m": {"validated": 242, "selected": 240, "excluded_outside_window": 2},
        "1d": {"validated": 4, "selected": 2, "excluded_outside_window": 2},
    }
    assert mapped.audit["requested_window"] == mapped.audit["actual_window"] == [DAYS[0], DAYS[0]]


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("period,case,stage", [
    ("1m", "bad_volume", "volume"), ("1m", "null_volume", "volume"),
    ("1m", "bool_volume", "volume"), ("1m", "fractional_volume", "volume"),
    ("1m", "negative_volume", "volume"), ("1m", "inexact_volume", "volume"),
    ("1m", "null_ohlc", "prices"), ("1d", "null_ohlc", "prices"),
    ("1m", "negative_ohlc", "prices"), ("1d", "negative_ohlc", "prices"),
    ("1m", "inconsistent_ohlc", "prices"), ("1d", "inconsistent_ohlc", "prices"),
    ("1m", "unknown_symbol", "symbols"), ("1d", "unknown_symbol", "symbols"),
    ("1m", "duplicate", "coverage"), ("1d", "duplicate", "coverage"),
    ("1m", "unordered", "coverage"), ("1d", "unordered", "coverage"),
    ("1m", "fractional_time", "time"), ("1m", "out_of_session", "time"),
    ("1m", "wrong_interval", "time"), ("1m", "backdated", "availability"),
    ("1m", "late_publication", "availability"), ("1m", "wrong_zero_status", "volume"),
    ("1d", "invalid_day", "calendar"),
])
def test_corrupt_neighbor_rows_cannot_be_certified(tmp_path, monkeypatch, side, period, case, stage):
    def corrupt(rows):
        row = add_neighbor(rows, period, side)
        if case.endswith("volume"):
            row["volume"] = {"bad_volume": "not-shares", "null_volume": None,
                             "bool_volume": True, "fractional_volume": 1.5,
                             "negative_volume": -1, "inexact_volume": float(2**53)}[case]
        elif case.endswith("ohlc"):
            row["close"] = {"null_ohlc": None, "negative_ohlc": -1, "inconsistent_ohlc": 11}[case]
        elif case == "unknown_symbol":
            row["symbol"] = "UNKNOWN_TEST_SYMBOL"
        elif case == "duplicate":
            rows[period].insert(0 if side == "before" else len(rows[period]), deepcopy(row))
        elif case == "unordered":
            rows[period].reverse()
        elif case == "fractional_time":
            row["timestamp"] += ".5"
        elif case == "out_of_session":
            row["timestamp"] = row["timestamp"][:10] + "T12:00:00"
        elif case == "wrong_interval":
            row["begin"] = row["end"]
        elif case == "backdated":
            row["available_at"] = row["begin"]
        elif case == "late_publication":
            row["available_at"] = row["timestamp"][:10] + "T23:59:59"
        elif case == "wrong_zero_status":
            row["volume_state"] = "zero"
        else:
            row["day"] = "20260800" if side == "before" else "20260932"

    source = fabricated_recipe(tmp_path, monkeypatch, raw_mutator=corrupt)["source"]
    with pytest.raises(IngressError) as failure:
        normalize(source)
    assert failure.value.stage == stage


@pytest.mark.parametrize("side", ["before", "after"])
def test_neighbor_minute_requires_publication_proof(tmp_path, monkeypatch, side):
    source = fabricated_recipe(tmp_path, monkeypatch,
                               raw_mutator=lambda rows: add_neighbor(rows, "1m", side))["source"]
    edit_pack(source, "availability", lambda p: p["binding"]["records"].pop(0 if side == "before" else -1))
    with pytest.raises(IngressError, match="missing publication proof"):
        normalize(source)


@pytest.mark.parametrize("period,column,value,stage", [
    ("1m", "volume", float("nan"), "volume"),
    ("1m", "volume", float("inf"), "volume"),
    ("1m", "close", None, "prices"),
    ("1m", "close", float("inf"), "prices"),
    ("1d", "close", float("nan"), "prices"),
    ("1d", "close", float("inf"), "prices"),
])
def test_decoded_parquet_neighbor_values_fail_closed(tmp_path, monkeypatch, period, column, value, stage):
    def corrupt(rows):
        add_neighbor(rows, period, "before")[column] = value

    source = fabricated_recipe(tmp_path, monkeypatch, parquet=True, raw_mutator=corrupt)["source"]
    with pytest.raises(IngressError) as failure:
        normalize(source)
    assert failure.value.stage == stage


@pytest.mark.parametrize("encoding", ["local_wall", "utc_instant", "utc_wall"])
def test_physical_datetime_parquet_columns(tmp_path, monkeypatch, encoding):
    source = fabricated_recipe(tmp_path, monkeypatch, parquet=True, physical_datetime=True,
                               encoding=encoding)["source"]
    assert source["raw_sources"][0]["schema"]["timestamp"].startswith("timestamp[")
    mapped = normalize(source)
    assert mapped.canonical() == cli.native_inputs(fixture()["native"]).canonical()
    assert mapped.audit["real_lake_run"] == mapped.audit["host_attestation"] == "NOT_RUN"


@pytest.mark.parametrize("sentinel", [
    "null", "unknown", "unfilled", "todo", "tbd", "none", "n/a", "placeholder",
    "nil", "nan", "na", "n.a.", "not applicable", "not available", "not provided",
    "missing", "tbc", "-", "--", "?",
])
def test_unfilled_template_words_reject_even_with_valid_pins(tmp_path, monkeypatch, sentinel):
    source = fabricated_recipe(tmp_path, monkeypatch)["source"]
    edit_pack(source, "units", lambda p: p.update(issuer=f"  {sentinel.upper()}  "))
    with pytest.raises(IngressError, match="units.issuer: unfilled text"):
        normalize(source)


@pytest.mark.parametrize("subject", list(cert.PACKS))
@pytest.mark.parametrize("failure", ["missing", "unfilled", "pin", "original_pin", "binding", "basis", "refs", "scope", "issuer"])
def test_required_packs_fail_closed(tmp_path, monkeypatch, subject, failure):
    source = fabricated_recipe(tmp_path, monkeypatch)["source"]
    if failure == "missing":
        del source["packs"][subject]
    elif failure in {"pin", "original_pin"}:
        spec = (source["packs"][subject] if failure == "pin" else
                next(s for s in source["materials"] if s["id"] == f"original_{subject}"))
        Path(spec["path"]).write_text("{}", encoding="utf-8")
    else:
        def change(pack):
            if failure == "unfilled":
                pack["complete"] = False
            elif failure == "binding":
                pack["binding"]["unproved_extra"] = True
            elif failure == "basis":
                pack["basis"] = "amount/(close*volume)~=100" if subject == "units" else "ST_list_or_silence"
            elif failure == "refs":
                pack["refs"] = []
            elif failure == "scope":
                pack["scope_hash"] = "0" * 64
            else:
                pack["issuer"] = None
        edit_pack(source, subject, change, original=False)
    with pytest.raises(IngressError):
        normalize(source)


@pytest.mark.parametrize("subject,key,value", [
    ("units", "unit", "lots"),
    ("units", "float_exact", False),
    ("availability", "rule", "close_or_mtime"),
    ("no_events", "start", "20260901"),
    ("context", "daily_price_domain", "front"),
    ("halt", "missing_rule", "halt_from_silence"),
])
def test_repinned_original_claim_must_match_requested_values(tmp_path, monkeypatch, subject, key, value):
    source = fabricated_recipe(tmp_path, monkeypatch)["source"]
    edit_pack(source, subject, lambda p: p["binding"].update({key: value}))
    with pytest.raises(IngressError):
        normalize(source)


@pytest.mark.parametrize("case", ["missing_grid", "duplicate_grid", "missing_false", "halted_true",
                                  "bool_hm", "active_missing", "missing_publication", "other_row",
                                  "backdated", "late_session", "wrong_interval", "duplicate_publication"])
def test_complete_session_and_publication_bindings(tmp_path, monkeypatch, case):
    source = fabricated_recipe(tmp_path, monkeypatch)["source"]
    subject = "halt" if case in {"missing_grid", "duplicate_grid", "missing_false", "halted_true", "bool_hm", "active_missing"} else "availability"

    def change(pack):
        rows = pack["binding"]["grid" if subject == "halt" else "records"]
        row = rows[0]
        if case in {"missing_grid", "missing_publication"}:
            rows.pop()
        elif case in {"duplicate_grid", "duplicate_publication"}:
            rows.append(deepcopy(row))
        elif case == "missing_false":
            row["missing"] = 0  # bool required; false/0 are not interchangeable.
        elif case == "halted_true":
            row["halted"] = True
        elif case == "bool_hm":
            row["hm"] = True
        elif case == "active_missing":
            row["missing"] = True
        elif case == "other_row":
            row["timestamp"] = rows[1]["timestamp"]
        elif case == "backdated":
            row["available_at"] = row["begin"]
        elif case == "late_session":
            row["available_at"] = "2026-09-01T23:59:59"
        else:
            row["begin"] = row["end"]
    edit_pack(source, subject, change)
    with pytest.raises(IngressError):
        normalize(source)


@pytest.mark.parametrize("parquet", [False, True])
def test_suspended_missing_is_explicit_and_preserves_daily_marks(tmp_path, monkeypatch, parquet):
    mapped = normalize(fabricated_recipe(tmp_path, monkeypatch, suspended=(0,), parquet=parquet)["source"])
    assert mapped.minute == {}
    assert len(mapped.samples) == 240 and set(mapped.samples.values()) == {None}
    assert len(mapped.daily[CODE]) == 2
    assert mapped.audit["suspensions"][0]["absent_buckets"] == 240


@pytest.mark.parametrize("case", ["raw_hash", "schema", "missing_file", "front_path", "cleaned", "synthetic",
                                  "no_resolver", "inline", "reused_raw_evidence", "wrong_snapshot"])
def test_raw_identity_and_origin_are_required(tmp_path, monkeypatch, case):
    source = fabricated_recipe(tmp_path, monkeypatch)["source"]
    spec = source["raw_sources"][0]
    path = Path(spec["path"])
    if case == "raw_hash":
        path.write_bytes(path.read_bytes() + b" ")
    elif case == "schema":
        spec["schema"] = "cleaned_frame"
    elif case == "missing_file":
        path.unlink()
    elif case == "front_path":
        target = path.parent.parent / "dividend_type=front" / path.name
        target.parent.mkdir()
        path.rename(target)
        spec["path"] = str(target)
    elif case == "cleaned":
        spec["representation"] = "read_lake_minute_ohlc"
    elif case == "synthetic":
        source = fixture()["source"]
        source["kind"] = "certified-real"
    elif case == "no_resolver":
        monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT")
    elif case == "inline":
        source["minute"] = fixture()["source"]["minute"]
    elif case == "wrong_snapshot":
        source["snapshot_id"] = "another-snapshot"
    else:
        source["materials"][0].update({k: spec[k] for k in ("path", "size", "sha256")})
    with pytest.raises((IngressError, FileNotFoundError, UnconfiguredDataRootError)):
        normalize(source)


@pytest.mark.parametrize("quantity", [True, -1, 2.5, float(2**53)])
def test_pinned_invalid_shares_cannot_pass_with_complete_packs(tmp_path, monkeypatch, quantity):
    source = fabricated_recipe(tmp_path, monkeypatch, volume=quantity)["source"]
    with pytest.raises(IngressError, match="volume"):
        normalize(source)


def test_valid_zero_and_delayed_publication_are_preserved(tmp_path, monkeypatch):
    source = fabricated_recipe(tmp_path, monkeypatch, volume=0,
                               overrides={(0, 895): {"delay_seconds": 1}})["source"]
    mapped = normalize(source)
    assert mapped.samples[CODE, DAYS[0], 895].available_at == 896
    assert mapped.samples[CODE, DAYS[0], 895].shares == 0
    assert len(mapped.minute[CODE]) == 240
    assert len(mapped.audit["zero_keys"]) == 240


@pytest.mark.parametrize("subject,document_type", [
    ("units", "amount_close_volume_ratio"), ("units", "minute_bars"),
    ("availability", "filesystem_mtime"), ("halt", "ST_list"), ("halt", "silence"),
])
def test_heuristics_cannot_be_hidden_by_a_valid_pack_basis(tmp_path, monkeypatch, subject, document_type):
    source = fabricated_recipe(tmp_path, monkeypatch)["source"]
    material = next(s for s in source["materials"] if s["id"] == f"original_{subject}")
    path = Path(material["path"])
    document = json.loads(path.read_text())
    document["document_type"] = document_type
    material.update(pin_json(path, document))
    with pytest.raises(IngressError, match="not independent source documents"):
        normalize(source)


def test_source_drift_after_mapping_is_rejected(tmp_path, monkeypatch):
    source = fabricated_recipe(tmp_path, monkeypatch)["source"]
    original = cert._map_records

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        path = Path(source["raw_sources"][0]["path"])
        path.write_bytes(path.read_bytes() + b" ")
        return result
    monkeypatch.setattr(cert, "_map_records", changed)
    with pytest.raises(IngressError, match="changed after preflight"):
        normalize(source)


def recipe_args(root, recipe):
    spec = pin_json(root / "recipe" / "recipe.json", recipe)
    go = root / "authority" / "HUMAN_GO.md"
    go.parent.mkdir(exist_ok=True)
    go.write_text("Fabricated local structural test GO only. No lake execution.\n", encoding="utf-8")
    return ["--recipe", spec["path"], "--recipe-sha256", spec["sha256"],
            "--human-go", str(go), "--human-go-sha256", hashlib.sha256(go.read_bytes()).hexdigest(),
            "--external-parent", str(root / "outputs"), "--run-id", "preflight", "--participation-rate", ".1"]


@pytest.mark.parametrize("failure", [None, "units", "availability", "no_events", "halt", "context",
                                    "null_pack", "missing_pack_file", "go_hash", "recipe_hash"])
@pytest.mark.parametrize("origin", ["fabricated_test", "host_supplied"])
def test_recipe_cli_receipts_never_claim_lake_or_matrix_pass(monkeypatch, failure, origin):
    with tempfile.TemporaryDirectory(prefix="d5-certified-") as tmp:
        root = Path(tmp)
        # host_supplied exercises receipt semantics using the same fabricated facts.
        recipe = fabricated_recipe(root, monkeypatch, evidence_origin=origin)
        if failure in cert.PACKS:
            del recipe["source"]["packs"][failure]
        elif failure == "null_pack":
            recipe["source"]["packs"]["units"] = None
        elif failure == "missing_pack_file":
            Path(recipe["source"]["packs"]["units"]["path"]).unlink()
        args = recipe_args(root, recipe)
        if failure in {"go_hash", "recipe_hash"}:
            args[7 if failure == "go_hash" else 3] = "0" * 64

        def forbidden(*_a, **_kw):
            raise AssertionError("recipe preflight must not run engine/shared IO")
        for name in ("simulate", "run", "main", "_read_one_minute", "read_minute_cache", "write_minute_cache"):
            monkeypatch.setattr(cli.engine, name, forbidden)
        assert cli.main(args) == (0 if failure is None else 1)
        receipt_path = root / "outputs" / "preflight" / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["real_lake_run"] == receipt["host_attestation"] == "NOT_RUN"
        assert receipt["comparison_status"] == "no_ssot_compare_authorization"
        assert all(v["status"] == "NOT_RUN" for v in receipt["matrix"].values())
        if failure is None:
            assert receipt["source_certification"] == "verified"
            assert receipt["evidence_origin"] == receipt["coverage"]["evidence_origin"] == origin
            assert receipt["certification_scope"] == receipt["coverage"]["certification_scope"] == "structure_and_pins_only"
            assert receipt["coverage"]["real_lake_run"] == receipt["coverage"]["host_attestation"] == "NOT_RUN"
            assert receipt["preflight"]["scope"] == "structure_and_mapping_only"
            assert set(receipt["output_files"]) == {"preflight.json", "receipt.json"}
            before = receipt_path.read_bytes()
            assert cli.main(args) == 1
            assert receipt_path.read_bytes() == before
        else:
            assert receipt["preflight"]["intentional_reject"] is True
            assert receipt["source_certification"] == "NOT_RUN"
            assert receipt["output_files"] == ["receipt.json"]


@pytest.mark.parametrize("payload", [b"{bad", b'{"source":', b'{"source":{},"source":{}}', b"\xff"])
def test_invalid_json_recipe_writes_identity_parse_rejection(monkeypatch, payload):
    with tempfile.TemporaryDirectory(prefix="d5-invalid-recipe-") as tmp:
        root = Path(tmp)
        args = recipe_args(root, fabricated_recipe(root, monkeypatch))
        Path(args[1]).write_bytes(payload)
        args[3] = hashlib.sha256(payload).hexdigest()
        assert cli.main(args) == 1
        receipt = json.loads((root / "outputs" / "preflight" / "receipt.json").read_text())
        assert receipt["failure"]["stage"] == "identity/parse"
        assert receipt["source"]["before"]["sha256"] == args[3]
        assert receipt["source_certification"] == receipt["host_attestation"] == receipt["real_lake_run"] == "NOT_RUN"
        assert receipt["preflight"] == {"status": "REJECTED", "intentional_reject": True}
        assert all(v["status"] == "NOT_RUN" for v in receipt["matrix"].values())
        assert receipt["output_files"] == ["receipt.json"]


@pytest.mark.parametrize("protected", ["recipe", "authority", "invented-lake"])
def test_invalid_json_recipe_cannot_write_into_known_inputs(monkeypatch, protected, capsys):
    with tempfile.TemporaryDirectory(prefix="d5-invalid-isolation-") as tmp:
        root = Path(tmp)
        args = recipe_args(root, fabricated_recipe(root, monkeypatch))
        Path(args[1]).write_bytes(b"{bad")
        args[3] = hashlib.sha256(b"{bad").hexdigest()
        args[9] = str(root / protected / "outputs")
        assert cli.main(args) == 1
        result = json.loads(capsys.readouterr().out)
        assert result["failure"]["stage"] == "output"
        assert result["root"] is None
        assert not (root / protected / "outputs").exists()


@pytest.mark.parametrize("period", ["1m", "1d"])
def test_corrupt_neighbor_cli_receipt_never_claims_verified(monkeypatch, period):
    def corrupt(rows):
        add_neighbor(rows, period, "before")["close"] = None

    with tempfile.TemporaryDirectory(prefix="d5-neighbor-reject-") as tmp:
        root = Path(tmp)
        args = recipe_args(root, fabricated_recipe(root, monkeypatch, raw_mutator=corrupt))
        assert cli.main(args) == 1
        receipt = json.loads((root / "outputs" / "preflight" / "receipt.json").read_text())
        assert receipt["failure"]["stage"] == "prices"
        assert receipt["source_certification"] == receipt["host_attestation"] == receipt["real_lake_run"] == "NOT_RUN"
        assert receipt["output_files"] == ["receipt.json"]
        assert all(v["status"] == "NOT_RUN" for v in receipt["matrix"].values())


def test_recipe_subprocess_and_evidence_output_isolation(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="d5-certified-cli-") as tmp:
        root = Path(tmp)
        recipe = fabricated_recipe(root, monkeypatch, parquet=True)
        args = recipe_args(root, recipe)
        process = subprocess.run([sys.executable, cli.__file__, *args], capture_output=True, text=True)
        assert process.returncode == 0, process.stdout + process.stderr
        args[9] = str(root / "materials" / "outputs")
        assert cli.main(args) == 1
        assert not (root / "materials" / "outputs").exists()


def test_strict_json_rejects_duplicate_keys():
    with pytest.raises(IngressError, match="duplicate JSON"):
        cert.strict_json('{"kind":"synthetic","kind":"certified-real"}')
