"""Synthetic artifact import, coverage, and candidate tests; socket access is banned."""

from datetime import date, datetime
from decimal import Decimal
import socket
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.data import pull_corp_actions_incremental as driver
from scripts.data import hithink_incremental as hi
from oskh_data import hithink_artifact as art
from tests import test_corp_actions_incremental_driver as wind_tests

inputs = wind_tests.inputs


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("BT must not access a network")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.delenv("HITHINK_FINANCE_API_KEY", raising=False)


def init(inputs, **changes):
    lake, universe, out = inputs
    args = driver.parser().parse_args(
        [
            "init",
            "--channel",
            "hithink",
            "--out-dir",
            str(out),
            "--lake-dir",
            str(lake),
            "--universe",
            str(universe),
            "--end",
            "2026-10-24",
        ]
    )
    for key, value in changes.items():
        setattr(args, key, value)
    return driver.initialize(args)


def row(ticker="600036.SH", stamp="2026-10-12", **changes):
    return {
        "thscode": ticker,
        "ticker": ticker[:6],
        "currency": "CNY",
        "ex_date_ms": int(
            datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
            * 1000
        ),
        "dividend_per_share": 0.199999,
        "per_share_bonus": 0.2999985,
        "allotment_ratio": 0.0,
        "allotment_price": 0.0,
        **changes,
    }


def bundle(run, path, rows=None, business_code=3002, *, quarantine=False):
    rows = rows if rows is not None else [row(), row("000001.SZ"), row("000004.SZ", "2026-09-01")]
    path.mkdir()
    pq.write_table(pa.Table.from_pylist(rows), path / "hithink_dump.parquet")
    parsed, stats = art.parse_dump(
        path / "hithink_dump.parquet",
        quarantine_window=(run.config["start"], run.config["end"]) if quarantine else None,
    )
    version = 2 if quarantine else 1
    request = art.request_identity(run.config)
    files = (*art.FILES[:2], "quarantine.json") if quarantine else art.FILES[:2]
    if quarantine:
        request["quarantine_policy"] = art.QUARANTINE_POLICY
        (path / "quarantine.json").write_bytes(
            driver.json_bytes(
                {
                    "format_version": 1,
                    "policy": art.QUARANTINE_POLICY,
                    "window": {k: run.config[k] for k in ("start", "end")},
                    "rows": stats["quarantine_records"],
                }
            )
        )
    probes = []
    for ticker in sorted(set(run.config["codes"]) - art.present_codes(parsed, stats)):
        probes.append(
            {
                "code": ticker,
                "identity": {
                    "endpoint": art.IDENTITY_ENDPOINT,
                    "params": {"q": ticker, "asset_type": "a-share", "limit": 50},
                    "http_status": 200,
                    "business_code": 0,
                    "identities": [ticker],
                    "response_sha256": "0" * 64,
                    "request_id": "identity-fixture",
                },
                "events": {
                    "endpoint": art.EVENT_ENDPOINT,
                    "params": {
                        "thscode": ticker,
                        "from": run.config["start"],
                        "to": run.config["end"],
                    },
                    "http_status": 200,
                    "business_code": business_code,
                    "data_thscode": ticker,
                    "item_count": 0,
                    "response_sha256": "1" * 64,
                    "request_id": "events-fixture",
                },
            }
        )
    (path / "probes.json").write_bytes(driver.json_bytes({"format_version": 1, "probes": probes}))
    manifest = {
        "format_version": version,
        "producer": "OSkhQuant1.3",
        "source": art.SOURCE,
        "endpoint": art.DUMP_ENDPOINT,
        "request": request,
        "fetched_at": "2026-10-24T08:00:00+00:00",
        "files": {k: art.digest(path / k) for k in files},
        "dump": stats,
        "coverage_passed": False,
        "lake_write_authorized": False,
    }
    (path / "manifest.json").write_bytes(driver.json_bytes(manifest))
    (path / "COMMITTED.json").write_bytes(
        driver.json_bytes(
            {"format_version": version, "manifest_sha256": art.digest(path / "manifest.json")}
        )
    )
    return path


def reseal(path):
    manifest = art.read_json(path / "manifest.json")
    manifest["files"] = {k: art.digest(path / k) for k in manifest["files"]}
    (path / "manifest.json").write_bytes(driver.json_bytes(manifest))
    (path / "COMMITTED.json").write_bytes(
        driver.json_bytes(
            {
                "format_version": manifest["format_version"],
                "manifest_sha256": art.digest(path / "manifest.json"),
            }
        )
    )


def test_artifact_only_import_assemble_prepare_preserves_base(inputs, tmp_path):
    run = init(inputs)
    base = {p.name: art.digest(p) for p in inputs[0].iterdir()}
    artifact = bundle(run, tmp_path / "bundle")
    assert hi.import_artifact(run, artifact) == 0
    state, _, _ = hi.imported(run)
    assert state["fetched_at"] != state["imported_at"]
    assert state["codes_no_events"] == ["000004.SZ"]
    assert hi.import_artifact(run, artifact) == 0
    table, report = driver.assemble(run)
    assert table.num_rows == 2 and report["unresolved_tasks"] == 0
    assert table["record_date"].null_count == 2 and table["transfer_ratio"].null_count == 2
    assert table["bonus_ratio"][0].as_py() == Decimal(".2999985")
    assert not report["economics_ready"]
    plan = driver.prepare_merge(run)
    assert plan["added_event_rows"] == 2 and not plan["lake_write_authorized"]
    assert base == {p.name: art.digest(p) for p in inputs[0].iterdir()}
    assert not (run.out / "merge-prep" / "manifest.json").exists()


def test_channel_freeze_missing_artifact_and_model_rejected(inputs):
    with pytest.raises(ValueError, match="model"):
        init(inputs, model=driver.MODELS[0])
    run = init(inputs)
    assert run.channel == "hithink" and run.config["model"] is None
    assert driver.main(["pull", "--out-dir", str(run.out)]) == 2
    assert driver.main(["pull", "--out-dir", str(run.out), "--channel", "wind"]) == 2


@pytest.mark.parametrize(
    "target", ["hithink_dump.parquet", "probes.json", "manifest.json", "COMMITTED.json"]
)
def test_partial_and_changed_artifacts(inputs, tmp_path, target):
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle")
    (artifact / target).write_bytes(b"broken")
    with pytest.raises((ValueError, KeyError, OSError, pa.ArrowException)):
        hi.import_artifact(run, artifact)
    assert not run.path("work/hithink_committed.json").exists()


def test_refresh_rebuilds_entire_snapshot_and_stops_after_assemble(inputs, tmp_path):
    run = init(inputs)
    first = bundle(run, tmp_path / "one")
    second = bundle(run, tmp_path / "two", [row(), row("000001.SZ"), row("000004.SZ")])
    hi.import_artifact(run, first)
    with pytest.raises(ValueError, match="refresh"):
        hi.import_artifact(run, second)
    hi.import_artifact(run, second, refresh=True)
    state, _, _ = hi.imported(run)
    assert not state["codes_no_events"]
    driver.assemble(run)
    with pytest.raises(ValueError, match="forbidden"):
        hi.import_artifact(run, first, refresh=True)


def test_orphan_local_dump_never_reports_success(inputs, tmp_path):
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle")
    run.path("raw_events").mkdir()
    run.path("raw_events/hithink_dump.parquet").write_bytes(b"partial")
    with pytest.raises(ValueError, match="incomplete"):
        hi.import_artifact(run, artifact)
    hi.import_artifact(run, artifact, refresh=True)
    run.path("work/hithink_state.json").write_bytes(b"{}")
    with pytest.raises((ValueError, KeyError)):
        driver.assemble(run)


def test_wrong_probe_scope_and_identity_not_empty_evidence(inputs, tmp_path):
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle", [row()], business_code=0)
    probes = art.read_json(artifact / "probes.json")
    probes["probes"][0]["events"]["params"]["from"] = "2026-10-08"
    (artifact / "probes.json").write_bytes(driver.json_bytes(probes))
    reseal(artifact)
    with pytest.raises(ValueError, match="scope"):
        hi.import_artifact(run, artifact)


def replace_listing(inputs, records):
    pq.write_table(
        pa.Table.from_pylist(
            records,
            schema=pa.schema(
                [("code", pa.string()), ("ipo_date", pa.date32()), ("delist_date", pa.date32())]
            ),
        ),
        inputs[0] / "listing.parquet",
    )


@pytest.mark.parametrize(
    "business,expected", [(0, "trading_eventless"), (3002, "unexplained"), (4001, "unexplained")]
)
def test_c_requires_successful_exact_identity_empty_probe(inputs, tmp_path, business, expected):
    replace_listing(
        inputs,
        [
            {"code": c, "ipo_date": date(2000, 1, 1), "delist_date": None}
            for c in ("600036.SH", "000001.SZ", "000004.SZ")
        ],
    )
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle", [row()], business_code=business)
    hi.import_artifact(run, artifact)
    _, report = driver.assemble(run)
    assert report["vendor_unknown_classification"]["000001.SZ"]["classification"] == expected
    if business:
        with pytest.raises(ValueError, match="unresolved"):
            driver.prepare_merge(run)


@pytest.mark.parametrize(
    "delist,expected",
    [
        (date(2026, 10, 6), "delisted_no_history"),
        (date(2026, 10, 7), "unexplained"),
        (date(2026, 10, 24), "unexplained"),
        (date(2027, 1, 1), "unexplained"),
    ],
)
def test_delisting_must_precede_window(inputs, tmp_path, delist, expected):
    replace_listing(
        inputs, [{"code": "000001.SZ", "ipo_date": date(2000, 1, 1), "delist_date": delist}]
    )
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle", [row(), row("000004.SZ")])
    hi.import_artifact(run, artifact)
    _, report = driver.assemble(run)
    assert report["vendor_unknown_classification"]["000001.SZ"]["classification"] == expected


def test_override_uses_real_calendar_and_fact_scope(inputs, tmp_path):
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle", [row(), row("000004.SZ")])
    hi.import_artifact(run, artifact)
    config = art.read_json(run.path("hithink_exclusions.json"))
    override = {
        "code": "000001.SZ",
        "classification": "delisted_explained",
        "reason": "fixture",
        "evidence": "fixture://notice",
        "approved_by": "fixture-human",
        "approved_at": "2026-10-29",
        "review_after": "2026-10-31",
        "scope_start": "2015-01-01",
        "scope_end": "2026-10-31",
    }
    config["manual_overrides"] = [override]
    run.write("hithink_exclusions.json", driver.json_bytes(config))
    _, rows, probes = hi.imported(run)
    assert not hi.coverage(run, rows, probes, today=date(2026, 10, 30))["unresolved_codes"]
    with pytest.raises(ValueError, match="expired"):
        hi.coverage(run, rows, probes, today=date(2026, 11, 1))
    override["scope_start"] = "2026-10-08"
    run.write("hithink_exclusions.json", driver.json_bytes(config))
    with pytest.raises(ValueError, match="scope"):
        hi.coverage(run, rows, probes, today=date(2026, 10, 30))


def test_dedup_window_rights_and_mixed_block(inputs, tmp_path):
    run = init(inputs)
    records = [
        row(),
        row(),
        row("600036.SH", dividend_per_share=0.3),
        row("000001.SZ", allotment_ratio=0.1),
        row("000004.SZ", allotment_ratio=0.1, dividend_per_share=0.0, per_share_bonus=0.0),
        row("600036.SH", "2026-11-05"),
    ]
    artifact = bundle(run, tmp_path / "bundle", records)
    hi.import_artifact(run, artifact)
    table, report = driver.assemble(run)
    assert table.num_rows == 2 and report["multiple_event_code_dates"] == 1
    assert report["hithink_allotment_rows"] == 2 and report["mixed_economics_requires_review"] == 1
    with pytest.raises(ValueError, match="mixed economics"):
        driver.prepare_merge(run)


def test_raw_projection_collision_and_unknown_base_source(inputs, tmp_path):
    run = init(inputs)
    artifact = bundle(
        run,
        tmp_path / "bundle",
        [row(extra="a"), row(extra="b"), row("000001.SZ", extra="a"), row("000004.SZ", extra="a")],
    )
    hi.import_artifact(run, artifact)
    with pytest.raises(ValueError, match="collide"):
        driver.assemble(run)
    base = pq.read_table(inputs[0] / "events.parquet").to_pylist()
    base[0]["source"] = "unknown:vendor"
    with pytest.raises(ValueError, match="unknown"):
        driver.validate_base(pa.Table.from_pylist(base, schema=driver.EVENT_SCHEMA), run.config)
    base[0]["source"] = art.SOURCE
    base[0]["record_date"] = None
    assert driver.validate_base(pa.Table.from_pylist(base, schema=driver.EVENT_SCHEMA), run.config)


def test_no_request_id_is_not_c_evidence(inputs, tmp_path):
    replace_listing(
        inputs,
        [
            {"code": c, "ipo_date": date(2000, 1, 1), "delist_date": None}
            for c in ("600036.SH", "000001.SZ", "000004.SZ")
        ],
    )
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle", [row()], business_code=0)
    probes = art.read_json(artifact / "probes.json")
    for probe in probes["probes"]:
        probe["events"].pop("request_id")
    (artifact / "probes.json").write_bytes(driver.json_bytes(probes))
    reseal(artifact)
    hi.import_artifact(run, artifact)
    _, report = driver.assemble(run)
    assert report["unresolved_codes"] == ["000001.SZ", "000004.SZ"]


def test_prepared_candidate_evidence_is_never_overwritten(inputs, tmp_path):
    run = init(inputs)
    hi.import_artifact(run, bundle(run, tmp_path / "bundle"))
    driver.prepare_merge(run)
    original = {
        p: art.digest(run.path(p)) for p in ("assembled/summary.json", "assembled/events.parquet")
    }
    for operation in (driver.assemble, driver.prepare_merge):
        with pytest.raises(ValueError, match="immutable"):
            operation(run)
    assert original == {p: art.digest(run.path(p)) for p in original}


def test_changed_exclusions_during_coverage_are_detected(inputs, tmp_path, monkeypatch):
    run = init(inputs)
    hi.import_artifact(run, bundle(run, tmp_path / "bundle"))
    _, rows, probes = hi.imported(run)
    original = hi.read_exclusions

    def concurrent_change(run):
        result = original(run)
        run.write(
            "hithink_exclusions.json", driver.json_bytes({"manual_overrides": [], "changed": True})
        )
        return result

    monkeypatch.setattr(hi, "read_exclusions", concurrent_change)
    with pytest.raises(ValueError, match="exclusions changed"):
        hi.coverage(run, rows, probes)


@pytest.mark.parametrize(
    "changes",
    [
        {"record_date": date(2026, 10, 1)},
        {"pay_date": date(2026, 9, 29)},
        {"bonus_list_date": date(2026, 9, 29)},
    ],
)
def test_base_date_consistency(inputs, changes):
    run = init(inputs)
    base = pq.read_table(inputs[0] / "events.parquet").to_pylist()
    base[0].update(changes)
    with pytest.raises(ValueError, match="inconsistent base"):
        driver.validate_base(pa.Table.from_pylist(base, schema=driver.EVENT_SCHEMA), run.config)


def test_source_independent_code_date_collision(inputs, tmp_path, monkeypatch):
    run = init(inputs)
    hi.import_artifact(run, bundle(run, tmp_path / "bundle"))
    original = driver.validate_base

    def collide(table, config):
        rows = original(table, config)
        rows[0]["ex_date"] = date(2026, 10, 12)
        return rows

    monkeypatch.setattr(driver, "validate_base", collide)
    with pytest.raises(ValueError, match="code/ex_date overlaps"):
        driver.prepare_merge(run)


def test_v2_import_keeps_quarantine_only_identity_present(inputs, tmp_path):
    run = init(inputs)
    bad = row("600036.SH", "2007-03-30", per_share_bonus=-0.5)
    artifact = bundle(
        run, tmp_path / "bundle", [bad, bad, row("000001.SZ"), row("000004.SZ")], quarantine=True
    )
    hi.import_artifact(run, artifact)
    state, _, _ = hi.imported(run)
    assert state["codes_vendor_unknown"] == [] and state["codes_no_events"] == ["600036.SH"]
    assert state["deduped_rows"] == state["accepted_rows"] + state["quarantined_rows"] == 3
    table, report = driver.assemble(run)
    assert (
        table.num_rows == 2
        and report["quarantined_codes"] == ["600036.SH"]
        and report["quarantined_rows"] == 1
    )
    assert not report["unresolved_codes"]


@pytest.mark.parametrize("operation", ["delete", "tamper", "reseal", "window"])
def test_v2_quarantine_evidence_is_recomputed(inputs, tmp_path, operation):
    run = init(inputs)
    artifact = bundle(
        run,
        tmp_path / "bundle",
        [row("600036.SH", "2007-03-30", per_share_bonus=-0.5)],
        quarantine=True,
    )
    if operation == "delete":
        (artifact / "quarantine.json").unlink()
    else:
        value = art.read_json(artifact / "quarantine.json")
        if operation == "window":
            value["window"]["start"] = "2026-10-08"
        else:
            value["rows"][0]["row_index"] = 999
        (artifact / "quarantine.json").write_bytes(driver.json_bytes(value))
        if operation in ("reseal", "window"):
            reseal(artifact)
    with pytest.raises((ValueError, OSError)):
        hi.import_artifact(run, artifact)
    assert not run.path("work/hithink_committed.json").exists()


@pytest.mark.parametrize("version", [True, 3])
def test_invalid_artifact_version_cannot_be_accepted(inputs, tmp_path, version):
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle")
    manifest = art.read_json(artifact / "manifest.json")
    manifest["format_version"] = version
    (artifact / "manifest.json").write_bytes(driver.json_bytes(manifest))
    reseal(artifact)
    with pytest.raises(ValueError, match="version"):
        hi.import_artifact(run, artifact)


def test_v1_cannot_ignore_an_unbound_quarantine_sidecar(inputs, tmp_path):
    run = init(inputs)
    artifact = bundle(run, tmp_path / "bundle")
    (artifact / "quarantine.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="v1"):
        hi.import_artifact(run, artifact)


def test_parity_rejects_quarantine_inside_historical_comparison(inputs, tmp_path):
    from scripts.gates.verify_corp_actions_hithink_parity import verify

    run = init(inputs)
    artifact = bundle(
        run,
        tmp_path / "bundle",
        [row("600036.SH", "2026-09-30", per_share_bonus=-0.5), row("000001.SZ"), row("000004.SZ")],
        quarantine=True,
    )
    hi.import_artifact(run, artifact)
    result = verify(run)
    assert not result["passed"] and len(result["quarantine_in_comparison"]) == 1


@pytest.mark.parametrize("target", ["sidecar_version", "sidecar_index", "manifest_count"])
def test_v2_boolean_metadata_does_not_equal_recomputed_integers(inputs, tmp_path, target):
    run = init(inputs)
    artifact = bundle(
        run,
        tmp_path / "bundle",
        [row("600036.SH", "2007-03-30", per_share_bonus=-0.5), row("000001.SZ")],
        quarantine=True,
    )
    if target == "manifest_count":
        manifest = art.read_json(artifact / "manifest.json")
        manifest["dump"]["accepted_rows"] = True
        (artifact / "manifest.json").write_bytes(driver.json_bytes(manifest))
    else:
        q = art.read_json(artifact / "quarantine.json")
        if target == "sidecar_version":
            q["format_version"] = True
        else:
            q["rows"][0]["row_index"] = False
        (artifact / "quarantine.json").write_bytes(driver.json_bytes(q))
    reseal(artifact)
    with pytest.raises(ValueError):
        hi.import_artifact(run, artifact)


def test_resealed_import_state_cannot_drop_verified_quarantine(inputs, tmp_path):
    run = init(inputs)
    artifact = bundle(
        run,
        tmp_path / "bundle",
        [row("600036.SH", "2007-03-30", per_share_bonus=-0.5), row("000001.SZ"), row("000004.SZ")],
        quarantine=True,
    )
    hi.import_artifact(run, artifact)
    state = art.read_json(run.path("work/hithink_state.json"))
    state["quarantine_records"] = []
    run.write("work/hithink_state.json", driver.json_bytes(state))
    marker = art.read_json(run.path("work/hithink_committed.json"))
    marker["state_sha256"] = art.digest(run.path("work/hithink_state.json"))
    run.write("work/hithink_committed.json", driver.json_bytes(marker))
    with pytest.raises(ValueError, match="verified artifact facts"):
        hi.imported(run)


def test_v1_state_cannot_inject_unverified_quarantine(inputs, tmp_path):
    run = init(inputs)
    hi.import_artifact(run, bundle(run, tmp_path / "bundle"))
    state = art.read_json(run.path("work/hithink_state.json"))
    state["quarantine_records"] = [{"code": "000001.SZ"}]
    run.write("work/hithink_state.json", driver.json_bytes(state))
    marker = art.read_json(run.path("work/hithink_committed.json"))
    marker["state_sha256"] = art.digest(run.path("work/hithink_state.json"))
    run.write("work/hithink_committed.json", driver.json_bytes(marker))
    with pytest.raises(ValueError, match="verified artifact facts"):
        hi.imported(run)
