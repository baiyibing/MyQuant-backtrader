"""Data-free Wind/Kimi fixtures; never invoke a vendor client."""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.data import pull_corp_actions_incremental as driver


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT", raising=False)
    monkeypatch.delenv("OSKH_AUTHORITY_HINT_ROOT", raising=False)
    lake = tmp_path / "lake" / "corp_actions"
    lake.mkdir(parents=True)
    row = {
        "code": "600036.SH", "event_id": "600036.SH_20260930_1",
        "ex_date": date(2026, 9, 30), "record_date": date(2026, 9, 29),
        "pay_date": None, "cash_div_per_share": Decimal("1.234567890123"),
        "bonus_ratio": None, "transfer_ratio": Decimal("0"), "bonus_list_date": None,
        "source": "wind:wind_get_stock_events",
    }
    pq.write_table(pa.Table.from_pylist([row], schema=driver.EVENT_SCHEMA), lake / "events.parquet")
    pq.write_table(pa.table({"code": ["600036.SH"], "ipo_date": [date(2002, 4, 9)],
                             "delist_date": pa.array([None], type=pa.date32()), "source": ["wind"]}),
                   lake / "listing.parquet")
    pq.write_table(pa.table({k: [v] for k, v in
                             {"code": "000004.SZ", "call": "listing", "error": "old failure"}.items()}),
                   lake / "failures.parquet")
    (lake / "manifest.json").write_bytes(driver.json_bytes({
        "schema_version": 1, "snapshot": "bt_corp_actions_20261006", "revision": "r20261023_01",
        "coverage_window": {"ask_start": "2015-01-01", "ask_end": "2026-10-06"},
    }))
    prior = tmp_path / "prior"
    prior.mkdir()
    universe = prior / "universe.txt"
    universe.write_text("600036.SH\n000001.SZ\n000004.SZ\n", encoding="utf-8")
    return lake, universe, tmp_path / "exports" / "bt_corp_actions_incr_20261024"


def init_run(inputs, **kwargs):
    lake, universe, out = inputs
    args = driver.parser().parse_args([
        "init", "--lake-dir", str(lake), "--universe", str(universe),
        "--out-dir", str(out), "--end", "2026-10-24",
    ])
    for key, value in kwargs.items():
        setattr(args, key, value)
    args.model = args.model or driver.MODELS[0]
    return driver.initialize(args)


def pull_args(run, *extra):
    return driver.parser().parse_args(["pull", "--out-dir", str(run.out), *extra])


def raw_row(code="000001.SZ", **kwargs):
    row = {"code": code, "progress": "实施完毕", "ex_date": "2026-10-12",
           "record_date": "2026-10-09", "pay_date": "2026-10-13",
           "cash_div_per_share": "0.123456789123", "bonus_ratio": "", "transfer_ratio": "0.3",
           "bonus_list_date": "2026-10-14"}
    row.update(kwargs)
    return row


def write_raw(path, rows):
    import csv
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Wind代码", "证券简称"] + ["2026年10月7日到2026年10月24日分红" + s
                                                     for s in driver.WIND_FIELDS.values()])
        for row in rows:
            writer.writerow([row["code"], "fixture"] + [row[k] for k in driver.WIND_FIELDS])


class FakeKimi:
    """Reads only the generated prompt, emits fixture raw CSV and RESULT_JSON."""

    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def __call__(self, command, **kwargs):
        assert command[1:3] == ["-m", driver.MODELS[0]]
        assert kwargs["capture_output"] and kwargs["timeout"] > 0
        prompt = command[command.index("-p") + 1]
        results = []
        for line in prompt.splitlines():
            if not line.startswith("[ev_"):
                continue
            tid = line[1:line.index("]")]
            params = json.loads(line.split(" params=", 1)[1])
            assert "2014" not in params["question"]
            assert "2026年10月7日至2026年10月24日" in params["question"]
            codes = params["question"].split(" ")[0].split(",")
            self.calls.append(codes)
            response = self.handler(codes)
            if isinstance(response, str):
                results.append({"id": tid, "status": "error", "rows": None, "error": response})
            else:
                write_raw(params["file_path"], response)
                results.append({"id": tid, "status": "ok", "rows": len(response), "error": ""})
        return SimpleNamespace(stdout="RESULT_JSON: " + json.dumps(results), stderr="", returncode=0)


def no_data(_):
    return "API_CALL_ERROR: 没找到数据"


def test_window_model_universe_frozen_and_no_init_overwrite(inputs):
    run = init_run(inputs)
    assert run.config["start"] == "2026-10-07"
    assert run.config["end"] == "2026-10-24"
    assert run.config["codes"] == ["000001.SZ", "000004.SZ", "600036.SH"]  # OOS bank retained
    assert run.config["model"] == "kimi-code/kimi-for-coding-highspeed"
    assert not run.config["lake_write_authorized"]
    with pytest.raises(ValueError, match="new/empty"):
        init_run(inputs)
    assert driver.main(["pull", "--out-dir", str(run.out), "--end", "2026-10-24"]) == 2
    with pytest.raises(SystemExit):
        driver.parser().parse_args(["init", "--out-dir", "unused", "--model", "kimi-code/k3"])


@pytest.mark.parametrize("start,end", [("2014-01-01", "2026-10-24"),
                                        ("2026-10-06", "2026-10-24"),
                                        ("2026-10-08", "2026-10-24"),
                                        (None, "2026-10-05"), (None, "2099-01-01")])
def test_refuse_full_repull_overlap_gap_and_future(inputs, start, end):
    with pytest.raises(ValueError, match="window"):
        init_run(inputs, start=start, end=end)
    assert not inputs[2].exists()


def test_end_defaults_cst_today_and_listing_universe_fallback(inputs):
    run = init_run(inputs, universe=None, end=None)
    assert run.config["end"] == str(driver.datetime.now(driver.CST).date())
    assert run.config["codes"] == ["600036.SH"]


def test_unconfigured_lake_reports_cli_error_without_guessing(inputs, capsys):
    assert driver.main(["init", "--out-dir", str(inputs[2])]) == 2
    assert "lake root is not configured" in capsys.readouterr().err
    assert not inputs[2].exists()


@pytest.mark.parametrize("where", ["lake", "lake_child", "prior", "parent", "container"])
def test_output_guard_protects_inputs_and_configured_lake(inputs, monkeypatch, where):
    lake, universe, _ = inputs
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(lake.parent))
    out = {"lake": lake, "lake_child": lake / "new", "prior": universe.parent / "new",
           "parent": lake.parent.parent, "container": lake.parent / "other"}[where]
    with pytest.raises(ValueError, match="separate"):
        init_run((lake, universe, out))


def test_output_symlink_escape_and_single_runner(inputs, tmp_path):
    run = init_run(inputs)
    escaped = tmp_path / "elsewhere"
    escaped.mkdir()
    (run.out / "raw_events").symlink_to(escaped, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        run.write("raw_events/test.csv", b"no")
    assert list(escaped.iterdir()) == []
    with run.locked():
        with pytest.raises(FileExistsError):
            with run.locked():
                pytest.fail("second writer admitted")


def test_assemble_prepare_preserves_base_and_all_precision(inputs):
    run = init_run(inputs)
    before = {p.name: driver.digest(p) for p in inputs[0].iterdir()}
    fake = FakeKimi(lambda codes: [raw_row()] if "000001.SZ" in codes else no_data(codes))
    assert driver.pull(run, pull_args(run), fake) == 0
    assert fake.calls == [["000001.SZ", "000004.SZ", "600036.SH"], ["000004.SZ"], ["600036.SH"]]
    assert driver.pull(run, pull_args(run), fake) == 0
    assert len(fake.calls) == 3  # resume does not re-pull accepted work
    delta, report = driver.assemble(run)
    assert report["unresolved_tasks"] == 0
    row = delta.to_pylist()[0]
    assert row["cash_div_per_share"] == Decimal("0.123456789123")
    assert row["transfer_ratio"] == Decimal("0.3")  # already per-share; no /10
    assert row["bonus_ratio"] is None
    assert row["event_id"].startswith("000001.SZ_20261012_incr_")
    assert driver.assemble(run)[0].equals(delta)
    plan = driver.prepare_merge(run)
    assert plan["added_event_rows"] == 1 and plan["deleted_event_rows"] == 0
    assert not plan["lake_write_authorized"] and not plan["automatically_applicable"]
    assert plan["coverage_patch_requires_vendor_window_review"]
    candidate = pq.read_table(run.out / "merge-prep/events.parquet").to_pylist()
    assert len(candidate) == 2
    assert next(r for r in candidate if r["code"] == "600036.SH") == pq.read_table(inputs[0] / "events.parquet").to_pylist()[0]
    for name in ("listing.parquet", "failures.parquet"):
        assert driver.digest(run.out / "merge-prep" / name) == before[name]
    assert {p.name: driver.digest(p) for p in inputs[0].iterdir()} == before
    assert not (run.out / "merge-prep/manifest.json").exists()  # no publishable replacement manifest
    with pytest.raises(ValueError, match="already exists"):
        driver.prepare_merge(run)


def test_all_vendor_no_data_is_valid_zero_delta_but_not_coverage_proof(inputs):
    run = init_run(inputs)
    fake = FakeKimi(no_data)
    assert driver.pull(run, pull_args(run), fake) == 0
    assert len(fake.calls) == 4  # batch cannot confirm singleton absence
    table, report = driver.assemble(run)
    assert table.num_rows == 0 and table.schema == driver.EVENT_SCHEMA
    assert report["codes_vendor_no_data"] == 3 and report["coverage_is_vendor_query_only"]
    assert driver.prepare_merge(run)["added_event_rows"] == 0


def test_quota_sticky_partial_file_not_accepted_and_explicit_resume(inputs):
    run = init_run(inputs)
    calls = []
    def quota(command, **kwargs):
        calls.append(command)
        # Even a valid-looking raw file must not override the session's quota stop.
        task = run.state()["tasks"][0]
        write_raw(run.path(task["raw"]), [raw_row()])
        return SimpleNamespace(stdout="RESULT_JSON: []", stderr="403 auth_error: usage limit", returncode=1)
    assert driver.pull(run, pull_args(run), quota) == 3
    task = run.state()["tasks"][0]
    assert driver.attempts_used(task) == 0 and not task.get("accepted_codes")
    assert driver.pull(run, pull_args(run), quota) == 3
    assert len(calls) == 1
    with pytest.raises(ValueError, match="unresolved"):
        driver.prepare_merge(run)
    assert driver.pull(run, pull_args(run, "--resume-quota"), FakeKimi(no_data)) == 0
    assert not run.path("work/QUOTA_STOP.json").exists()
    assert list((run.out / "work").glob("QUOTA_STOP.*.json"))


def test_no_false_quota_on_instructions_or_normal_thinking():
    assert not driver.quota_hit("Stop if quota exhausted or auth/rate limit errors")
    assert not driver.quota_hit("only stop on quota exhausted, auth, or rate limit errors")
    assert not driver.quota_hit("I will stop on quota errors and then report results.")
    assert not driver.quota_hit('RESULT_JSON: [{"rows":403},{"rows":429}]')
    assert not driver.quota_hit('RESULT_JSON: [{"error":"API_CALL_ERROR: 没找到数据"}]')
    assert not driver.quota_hit("I will stop on quota exhausted and then report results.")
    assert not driver.quota_hit("Stop  if\tquota exhausted or auth/rate limit errors")


@pytest.mark.parametrize("text", [
    "quota has been exhausted", "quota exceeded", "quota reached",
    "HTTP 429", "HTTP 403", "HTTP/1.1 429",
    "too many requests", "usage limit", "quota_exceeded",
    "rate limit exceeded", "auth_error",
    "403: quota denied", "429: usage denied", "403: auth failed",
    "429: rate-limit error",
    "Stop if quota exhausted or auth/rate limit errors\nquota has been exhausted",
    "only stop on quota exhausted, auth, or rate limit errors\nHTTP 429",
])
def test_provider_quota_signals(text):
    assert driver.quota_hit(text)


@pytest.mark.parametrize("kind", ["infra", "timeout", "missing_binary"])
def test_startup_timeout_stop_without_spin_and_resume(inputs, kind):
    run = init_run(inputs)
    calls = []
    def broken(*args, **kwargs):
        calls.append(1)
        if kind == "timeout":
            raise subprocess.TimeoutExpired("fixture", 1)
        if kind == "missing_binary":
            raise FileNotFoundError("fixture executable missing")
        return SimpleNamespace(stdout="", stderr="storage write failed: EPERM", returncode=1)
    assert driver.pull(run, pull_args(run), broken) == 2
    assert len(calls) == 1
    assert driver.attempts_used(run.state()["tasks"][0]) == (0 if kind == "infra" else 1)
    assert driver.pull(run, pull_args(run), FakeKimi(no_data)) == 0


def test_missing_result_or_bad_raw_remains_unresolved_not_empty(inputs):
    run = init_run(inputs)
    def bad(command, **kwargs):
        task = run.state()["tasks"][0]
        run.path(task["raw"]).write_text("bad,header\n", encoding="utf-8")
        # A raw file alone never counts as success.
        return SimpleNamespace(stdout="not a result", stderr="", returncode=0)
    assert driver.pull(run, pull_args(run, "--max-attempts", "2"), bad) == 2
    assert driver.summary(run.state(), 2)["exhausted_tasks"] == 1
    assert driver.assemble(run)[1]["event_rows"] == 0
    with pytest.raises(ValueError, match="unresolved"):
        driver.prepare_merge(run)


def test_capped_batch_splits_and_capped_singleton_blocks(inputs):
    run = init_run(inputs)
    fake = FakeKimi(lambda codes: [raw_row(codes[0])] * 100)
    assert driver.pull(run, pull_args(run, "--max-attempts", "1"), fake) == 2
    assert len(fake.calls) == 4
    assert driver.summary(run.state(), 1)["exhausted_tasks"] == 3
    assert driver.assemble(run)[0].num_rows == 0
    with pytest.raises(ValueError, match="unresolved"):
        driver.prepare_merge(run)


def test_header_only_singletons_not_confirmed_no_events(inputs):
    run = init_run(inputs)
    assert driver.pull(run, pull_args(run, "--max-attempts", "1"), FakeKimi(lambda _: [])) == 2
    assert driver.summary(run.state())["codes_vendor_no_data"] == 0


def test_raw_drift_lake_drift_universe_drift_fail_closed(inputs):
    run = init_run(inputs)
    fake = FakeKimi(lambda codes: [raw_row(c) for c in codes])
    assert driver.pull(run, pull_args(run), fake) == 0
    task = run.state()["tasks"][0]
    original = run.path(task["raw"]).read_bytes()
    run.path(task["raw"]).write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="raw evidence changed"):
        driver.assemble(run)
    run.path(task["raw"]).write_bytes(original)
    path = inputs[0] / "manifest.json"
    before = path.read_bytes()
    path.write_bytes(before + b"\n")
    with pytest.raises(ValueError, match="base lake changed"):
        driver.prepare_merge(run)
    path.write_bytes(before)
    inputs[1].write_text("000001.SZ\n", encoding="utf-8")
    with pytest.raises(ValueError, match="universe input changed"):
        driver.pull(run, pull_args(run), fake)


def test_no_data_log_drift_is_not_accepted_as_evidence(inputs):
    run = init_run(inputs)
    assert driver.pull(run, pull_args(run), FakeKimi(no_data)) == 0
    task = next(t for t in run.state()["tasks"] if t["status"] == "no_data")
    log = next(iter(task["attempts"][-1]["logs_sha256"]))
    run.path(log).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="session evidence changed"):
        driver.prepare_merge(run)


@pytest.mark.parametrize("change", [{"cash_div_per_share": "NaN"}, {"bonus_ratio": "-0.1"},
                                    {"cash_div_per_share": "0.1234567891234"},
                                    {"record_date": ""}, {"pay_date": "2026-10-11"},
                                    {"record_date": "2026-10-13"}, {"ex_date": "2026-02-30"}])
def test_invalid_economics_dates_never_prepare(inputs, change):
    run = init_run(inputs)
    assert driver.pull(run, pull_args(run), FakeKimi(lambda codes: [raw_row(c, **change) for c in codes])) == 0
    with pytest.raises((ValueError, pa.ArrowException)):
        driver.prepare_merge(run)
    assert not (run.out / "merge-prep").exists()


def test_filter_outside_window_unimplemented_and_keep_same_day_multi_events(inputs):
    run = init_run(inputs)
    def response(codes):
        return [r for c in codes for r in [
            raw_row(c), raw_row(c), raw_row(c, cash_div_per_share="0.5"),
            raw_row(c, ex_date="2026-10-06"), raw_row(c, ex_date="2026-10-25"),
            raw_row(c, progress="董事会预案"),
        ]]
    assert driver.pull(run, pull_args(run), FakeKimi(response)) == 0
    delta, report = driver.assemble(run)
    assert delta.num_rows == 6 and report["rejected_rows"] == 9
    assert len(set(delta["event_id"].to_pylist())) == 6


def test_conflicting_duplicate_fields_do_not_silently_keep_last(inputs):
    run = init_run(inputs)
    def response(codes):
        return [r for c in codes for r in [raw_row(c), raw_row(c, pay_date="2026-10-15")]]
    assert driver.pull(run, pull_args(run), FakeKimi(response)) == 0
    with pytest.raises(ValueError, match="conflicting duplicate"):
        driver.prepare_merge(run)


def test_cli_smoke_without_vendor_process(inputs):
    run = init_run(inputs)
    assert driver.pull(run, pull_args(run), FakeKimi(no_data)) == 0
    script = Path(driver.__file__)
    for command in ("pending", "assemble", "prepare-merge"):
        proc = subprocess.run([sys.executable, str(script), command, "--out-dir", str(run.out)],
                              capture_output=True, text=True, check=True)
        assert "ERROR" not in proc.stderr
        json.loads(proc.stdout)
    assert (run.out / "merge-prep/manifest-patch-plan.json").exists()
