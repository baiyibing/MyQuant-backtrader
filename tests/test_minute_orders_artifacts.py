"""Synthetic S4 schema/isolation oracles; every artifact lives under tmp_path."""

from dataclasses import asdict, replace
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal, Inexact, ROUND_HALF_UP, localcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from zoneinfo import ZoneInfo

import pytest

from backtest.research.minute_orders_backend import artifacts
from backtest.research.minute_orders_backend.runner import (
    run_minute_orders_research, run_minute_orders_research_with_artifacts,
)
from backtest.research.minute_orders_backend.types import (
    CalendarFacts, CancelOrder, CompletedBucket, FeeModelParams, InstrumentFacts,
    LotPosition, MarkEvent, MarkPrice, RunInput, SessionBucket, Side, SubmitOrder,
)

SHA = "b065c99b402a1d82184c7ad2ec2bef5ee59c09ad"  # Explicit test provenance override.
D = Decimal
DAY, PREV, NEXT = date(2026, 9, 28), date(2026, 9, 25), date(2026, 9, 29)
TZ = ZoneInfo("Asia/Shanghai")


def at(time):
    return datetime.fromisoformat(f"{DAY}T{time}").replace(tzinfo=TZ)


def request():
    order = SubmitOrder("submit:A", "A", "X", Side.BUY, 400, D("10.00"),
                        at("09:29:00"), at("09:29:00"), at("09:30:00"), at("09:35:00"), 1)
    cancel = CancelOrder("cancel:A", "A", at("09:32:00"), at("09:32:00"), at("09:32:30"), 2)
    buckets = tuple(CompletedBucket("X", f"B{i}", at(start), at(start) + timedelta(minutes=1),
                                    D("10.00"), volume, False, False)
                    for i, (start, volume) in enumerate((("09:30:00", 1000), ("09:31:00", 500))))
    return RunInput(
        at("09:28:00"), at("09:35:00"), (order, cancel), buckets,
        CalendarFacts((PREV, DAY, NEXT), tuple(SessionBucket(b.bucket_id, b.start, b.end, "continuous")
                                              for b in buckets), True, ()),
        (InstrumentFacts("X", DAY, "main", "raw", D("0.01"), 100, D("10.00"), D("9.00"), D("11.00")),),
        D("10000.00"), (), FeeModelParams(D("0.001"), D("5.00"), ROUND_HALF_UP),
        FeeModelParams(D("0"), D("0.00"), ROUND_HALF_UP), D("0.20"),
        tuple(MarkEvent(f"M{i}", at(time), at(time), (MarkPrice("X", D("10.00")),), "raw", "合成手算")
              for i, time in enumerate(("09:29:00", "09:31:00", "09:32:30"))), True,
    )


def run_disk(parent, *, run_id="test", run_input=None, **kwargs):
    return run_minute_orders_research_with_artifacts(
        request() if run_input is None else run_input, parent,
        run_id=run_id, evidence_level="synthetic", code_sha=SHA, **kwargs,
    )


def read(root, name):
    data = (root / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in data.splitlines()] if name.endswith(".jsonl") else json.loads(data)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def check_manifest(root, status):
    manifest = read(root, "manifest.json")
    assert manifest["status"] == status
    assert manifest["backend_id"] == "minute_orders_research_v1"
    assert manifest["evidence_level"] == "synthetic"
    assert manifest["comparison_status"] == "no_ssot_compare_authorization"
    for ref in manifest["artifacts"]:
        assert "/" not in ref["path"] and "\\" not in ref["path"]
        assert digest((root / ref["path"]).read_bytes()) == ref["sha256"]
    assert {r["path"] for r in manifest["artifacts"]} == {
        p.name for p in root.iterdir() if not p.name.startswith(".") and p.name != "manifest.json"
    }
    return manifest


def test_full_tree_summary_published_last_and_exact_handcalcs(tmp_path, monkeypatch):
    writes = []
    original_write, original_publish = artifacts._write_file, artifacts._publish

    def write(root, name, body):
        assert not (root / "summary.json").exists()
        writes.append(name)
        original_write(root, name, body)

    def publish(root, name, body):
        if name == "summary.json":
            assert read(root, "manifest.json")["status"] == "success"
            assert set(p.name for p in root.iterdir()) == {
                "contract.json", "inputs.json", "commands.jsonl", "orders.jsonl",
                "fills.jsonl", "ledger.jsonl", "marks.jsonl", "manifest.json",
            }
        original_publish(root, name, body)

    monkeypatch.setattr(artifacts, "_write_file", write)
    monkeypatch.setattr(artifacts, "_publish", publish)
    result = run_disk(tmp_path)
    root = result.root
    assert root == tmp_path / "backtest_output/minute_orders_research_v1/test"
    assert result.status == "success"
    assert writes[-1] == ".summary.json.pending"
    assert len(list(root.iterdir())) == 9
    manifest = check_manifest(root, "success")
    assert manifest["code_sha"] == SHA and manifest["code_sha_source"] == "caller_override"
    contract, inputs = read(root, "contract.json"), read(root, "inputs.json")
    assert digest(canonical(contract)) == manifest["contract_hash"] == result.contract_hash
    assert digest(canonical(inputs["data"])) == inputs["input_hash"] == manifest["input_hash"] == result.input_hash
    for name, component in inputs["components"].items():
        assert component == {"sha256": digest(canonical(inputs["data"][name])), "ref": f"inputs.json#/data/{name}"}
    assert inputs["data"]["calendar"]["company_actions_covered"] is True
    assert contract["parameters"]["participation_rate"] == {"value": "0.20", "source": "inputs.json#/data/participation_rate"}
    commands = read(root, "commands.jsonl")
    assert [c["kind"] for c in commands] == ["submit", "cancel"]
    assert commands[1]["symbol"] == "X" and commands[1]["side"] == "BUY"
    assert "qty" not in commands[1] and "expires_at" not in commands[1]
    orders = read(root, "orders.jsonl")
    assert [o["status"] for o in orders] == ["Submitted", "Accepted", "PartiallyFilled", "PartiallyFilled", "Cancelled"]
    assert [o["reservation_after"]["cash"] for o in orders] == ["0.00", "4005.00", "2000.00", "1000.00", "0.00"]
    assert [o["reservation_before"]["cash"] for o in orders] == ["0.00", "0.00", "4005.00", "2000.00", "1000.00"]
    assert orders[-1]["command_id"] == "cancel:A" and orders[-1]["remaining_qty"] == 100
    fills = read(root, "fills.jsonl")
    assert [(f["qty"], f["notional"], f["fee_delta"], f["cumulative_notional"], f["cumulative_fee"],
             f["capacity_before"], f["capacity_after"]) for f in fills] == [
        (200, "2000.00", "5.00", "2000.00", "5.00", 200, 0),
        (100, "1000.00", "0.00", "3000.00", "5.00", 100, 0),
    ]
    for fill in fills:
        assert fill["matched_at"] == fill["booked_at"] == fill["available_at"] == fill["bucket_end"]
        assert datetime.fromisoformat(fill["booked_at"]).utcoffset() == timedelta(hours=8)
        assert fill["ledger_version"] == fill["expected_version"] + 1
    ledger = read(root, "ledger.jsonl")
    keys = [row["event_key"] for row in ledger if "event_key" in row]
    assert keys == sorted(keys)
    assert ledger[-1]["cash"] == "6995.00" and ledger[-1]["reserved_cash"] == "0.00"
    assert ledger[-1]["fees_paid"] == "5.00"
    assert all(lot["sellable_date"] == str(NEXT) and lot["free_qty"] == lot["qty"] for lot in ledger[-1]["lots"])
    marks = read(root, "marks.jsonl")
    assert all(m["valuation_valid"] and m["source"] == "合成手算" for m in marks)
    assert [p["market_value"] for p in marks[-1]["positions"]] == ["2000.00", "1000.00"]
    summary = read(root, "summary.json")
    assert summary["status"] == "success" and summary["fees_paid"] == "5.00"
    assert summary["fill_count"] == 2 and summary["filled_qty"] == 300
    assert summary["orders"] == [{"order_id": "A", "status": "Cancelled", "filled_qty": 300,
                                  "remaining_qty": 100, "active": False}]
    assert summary["mark_refs"] == ["marks.jsonl#row=1", "marks.jsonl#row=2", "marks.jsonl#row=3"]
    assert not (root / "failure.json").exists()


@pytest.mark.parametrize("kind", ["empty", "foreign", "file", "symlink", "dangling_symlink"])
def test_existing_destination_always_refused_without_foreign_mutation(tmp_path, kind):
    root = tmp_path / "backtest_output/minute_orders_research_v1/test"
    root.parent.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "summary.json").write_bytes(b"foreign evidence")
    if kind == "file":
        root.write_bytes(b"foreign file")
    elif "symlink" in kind:
        root.symlink_to(foreign if kind == "symlink" else tmp_path / "absent")
    else:
        root.mkdir()
        if kind == "foreign":
            (root / "summary.json").write_bytes(b"existing success")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        run_disk(tmp_path)
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert not (root / "failure.json").exists()


@pytest.mark.parametrize("run_id", ["", ".", "..", "../foreign", "/tmp/outside", "x/y", "x\\y"])
def test_bad_run_id_fails_before_any_root_creation(tmp_path, run_id):
    with pytest.raises(ValueError):
        run_disk(tmp_path, run_id=run_id)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("namespace", ["backtest_output", "backtest_output/minute_orders_research_v1"])
def test_namespace_symlink_cannot_redirect_into_foreign_family(tmp_path, namespace):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "pin").write_bytes(b"unchanged")
    link = tmp_path / namespace
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(FileExistsError):
        run_disk(tmp_path)
    assert list(foreign.iterdir()) == [foreign / "pin"]


@pytest.mark.parametrize("stage", ["validation", "after_fill"])
def test_failed_engine_preserves_only_available_committed_evidence(tmp_path, stage):
    req = request()
    if stage == "validation":
        req = replace(req, calendar=replace(req.calendar, company_actions_covered=False))
    else:
        req = replace(req, marks=(replace(req.marks[1], prices=()),))
    with pytest.raises(ValueError):
        run_minute_orders_research(req)
    outcome = run_disk(tmp_path, run_input=req)
    root = outcome.root
    assert outcome.status == "failed"
    manifest = check_manifest(root, "failed")
    failure = read(root, "failure.json")
    assert failure["stage"] == "run" and failure["status"] == "failed"
    assert not (root / "summary.json").exists()
    assert "nav" not in failure and "nav" not in manifest
    if stage == "after_fill":
        assert len(read(root, "fills.jsonl")) == 1
        assert read(root, "ledger.jsonl")[-1]["cash"] == "7995.00"
        assert "last_committed_ledger_version" in failure and "last_recorded_event_key" in failure
    else:
        assert read(root, "fills.jsonl") == []
        assert "last_committed_ledger_version" not in failure


def test_direct_success_or_exception_writer_omits_unavailable_snapshots(tmp_path):
    req = request()
    result = run_minute_orders_research(req)
    good = artifacts.write_minute_orders_artifacts(req, result, tmp_path, run_id="good",
                                                   evidence_level="synthetic", code_sha=SHA)
    assert all("reservation_after" not in row for row in read(good.root, "orders.jsonl"))
    bad = artifacts.write_minute_orders_artifacts(req, ValueError("explicit run failure"), tmp_path,
                                                  run_id="bad", evidence_level="synthetic", code_sha=SHA)
    assert bad.status == "failed" and read(bad.root, "ledger.jsonl") == []
    assert read(bad.root, "failure.json")["reason"] == "explicit run failure"
    check_manifest(bad.root, "failed")


@pytest.mark.parametrize("fail_at", ["contract.json", "orders.jsonl", "fills.jsonl", "manifest.json", ".summary.json.pending"])
def test_injected_partial_disk_failure_never_leaves_summary(tmp_path, monkeypatch, fail_at):
    original = artifacts._write_file

    def fail(root, name, body):
        if name == fail_at:
            (root / name).write_bytes(body[:17])
            raise OSError("injected partial write")
        original(root, name, body)

    monkeypatch.setattr(artifacts, "_write_file", fail)
    with pytest.raises(artifacts.ArtifactWriteError) as error:
        run_disk(tmp_path)
    root = error.value.root
    assert error.value.evidence_error is None
    assert not (root / "summary.json").exists()
    assert read(root, "failure.json")["reason"] == "injected partial write"
    check_manifest(root, "failed")


def test_corrupted_written_body_fails_validation_before_summary(tmp_path, monkeypatch):
    original = artifacts._write_file

    def corrupt(root, name, body):
        original(root, name, body)
        if name == "fills.jsonl":
            (root / name).write_bytes(b"{}\n")

    monkeypatch.setattr(artifacts, "_write_file", corrupt)
    with pytest.raises(artifacts.ArtifactWriteError, match="verification failed") as error:
        run_disk(tmp_path)
    assert read(error.value.root, "failure.json")["stage"] == "validate_artifacts"
    assert not (error.value.root / "summary.json").exists()
    check_manifest(error.value.root, "failed")


def test_summary_publish_failure_and_failure_after_publish_remove_marker(tmp_path, monkeypatch):
    original = artifacts.os.replace

    def fail(source, dest):
        original(source, dest)
        if dest.name == "summary.json":
            raise OSError("injected at final publication")

    monkeypatch.setattr(artifacts.os, "replace", fail)
    with pytest.raises(artifacts.ArtifactWriteError) as error:
        run_disk(tmp_path)
    assert not (error.value.root / "summary.json").exists()
    check_manifest(error.value.root, "failed")


@pytest.mark.parametrize("crash_at", ["orders.jsonl", "manifest.json", ".summary.json.pending"])
def test_uncatchable_crash_leaves_partial_evidence_without_success_marker(tmp_path, monkeypatch, crash_at):
    original = artifacts._write_file

    def crash(root, name, body):
        original(root, name, body)
        if name == crash_at:
            raise KeyboardInterrupt("simulated abrupt interruption")

    monkeypatch.setattr(artifacts, "_write_file", crash)
    with pytest.raises(KeyboardInterrupt):
        run_disk(tmp_path)
    root = tmp_path / "backtest_output/minute_orders_research_v1/test"
    assert (root / "orders.jsonl").exists()
    assert not (root / "summary.json").exists()
    with pytest.raises(FileExistsError):
        run_disk(tmp_path)


def test_concurrent_claim_of_same_root_has_exactly_one_owner(tmp_path):
    def attempt():
        try:
            return run_disk(tmp_path)
        except FileExistsError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    winners = [r for r in results if isinstance(r, artifacts.ArtifactWriteResult)]
    assert len(winners) == 1 and sum(isinstance(r, FileExistsError) for r in results) == 1
    check_manifest(winners[0].root, "success")


def test_persistent_io_failure_reports_failed_evidence_error_without_summary(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr(artifacts, "_write_file", fail)
    with pytest.raises(artifacts.ArtifactWriteError) as error:
        run_disk(tmp_path)
    assert isinstance(error.value.evidence_error, OSError)
    assert not (error.value.root / "summary.json").exists()


def test_determinism_new_ids_hash_scope_and_decimal_context(tmp_path):
    first = run_disk(tmp_path, run_id="one")
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        second = run_disk(tmp_path, run_id="two")
    assert (first.contract_hash, first.input_hash) == (second.contract_hash, second.input_hash)
    for path in first.root.iterdir():
        other = second.root / path.name
        if path.name in ("summary.json", "manifest.json"):
            a, b = read(first.root, path.name), read(second.root, path.name)
            a.pop("run_id")
            b.pop("run_id")
            if path.name == "manifest.json":
                a["artifacts"] = [r for r in a["artifacts"] if r["path"] != "summary.json"]
                b["artifacts"] = [r for r in b["artifacts"] if r["path"] != "summary.json"]
            assert a == b
        else:
            assert path.read_bytes() == other.read_bytes()
    with pytest.raises(FileExistsError):
        run_disk(tmp_path, run_id="one")
    changed_input = run_disk(tmp_path, run_id="cash", run_input=replace(request(), initial_cash=D("20000.00")))
    assert changed_input.contract_hash == first.contract_hash
    assert changed_input.input_hash != first.input_hash
    changed_config = run_disk(tmp_path, run_id="config", run_input=replace(request(), participation_rate=D("0.10")))
    assert changed_config.contract_hash != first.contract_hash
    assert changed_config.input_hash != first.input_hash


def test_empty_marks_active_remainder_and_business_rejected_are_success(tmp_path):
    req = replace(request(), end_at=at("09:32:00"), marks=(), requires_marks=False)
    outcome = run_disk(tmp_path, run_input=req)
    assert (outcome.root / "marks.jsonl").read_bytes() == b""
    summary = read(outcome.root, "summary.json")
    assert summary["orders"][0]["status"] == "PartiallyFilled"
    assert summary["orders"][0]["active"] is True
    assert summary["orders"][0]["remaining_qty"] == 100
    assert summary["mark_refs"] == []
    rejected = run_disk(tmp_path, run_id="rejected", run_input=replace(req, initial_cash=D("0.00")))
    assert rejected.status == "success"
    assert read(rejected.root, "summary.json")["status_counts"]["Rejected"] == 1
    assert read(rejected.root, "fills.jsonl") == []


def test_sell_reservation_partial_then_cancel_and_shared_capacity(tmp_path):
    req = request()
    buy = replace(req.commands[0], qty=300)
    sell = replace(buy, command_id="submit:S", order_id="S", qty=400, side=Side.SELL, sequence=2)
    cancel = replace(req.commands[1], command_id="cancel:S", order_id="S")
    # Both orders compete for the same buckets; sell consumes all 300 available shares.
    req = replace(req, commands=(buy, sell, cancel), initial_lots=(LotPosition("old", "X", PREV, DAY, 400, 100),))
    outcome = run_disk(tmp_path, run_input=req)
    orders = [r for r in read(outcome.root, "orders.jsonl") if r["order_id"] == "S"]
    assert [r["reservation_after"]["sellable_qty"] for r in orders] == [0, 400, 200, 100, 0]
    assert orders[-1]["status"] == "Cancelled"
    assert all(r["side"] == "SELL" for r in read(outcome.root, "fills.jsonl"))
    assert all(r["capacity_after"] == 0 for r in read(outcome.root, "fills.jsonl"))


def test_default_in_memory_and_disk_opt_in_preserve_input_cwd_env_and_old_roots(tmp_path, monkeypatch):
    req = request()
    before = asdict(req)
    monkeypatch.chdir(tmp_path)
    old_roots = [tmp_path / "backtest_output" / family for family in ("csv", "v7", "joint_return", "unified_exit_modeb")]
    for root in old_roots:
        root.mkdir(parents=True)
        (root / "pin").write_bytes(b"foreign bytes")
    context = os.getcwd(), dict(os.environ)
    in_memory = run_minute_orders_research(req)
    assert all(t.ledger is None for t in in_memory.transitions)
    assert not (tmp_path / "backtest_output/minute_orders_research_v1").exists()
    run_disk(Path("."), run_input=req)
    assert before == asdict(req)
    assert context == (os.getcwd(), dict(os.environ))
    for root in old_roots:
        assert list(root.iterdir()) == [root / "pin"]
        assert (root / "pin").read_bytes() == b"foreign bytes"


def test_missing_fields_omitted_and_unencodable_failure_never_succeeds(tmp_path):
    req = request()
    missing = replace(req.buckets[0], missing=True, close=None, volume_shares=None)
    good = run_disk(tmp_path, run_input=replace(req, buckets=(missing, req.buckets[1])))
    recorded = read(good.root, "inputs.json")["data"]["buckets"][0]
    assert "close" not in recorded and "volume_shares" not in recorded
    bad = replace(req, start_at=req.start_at.replace(tzinfo=None))
    with pytest.raises(artifacts.ArtifactWriteError) as error:
        run_disk(tmp_path, run_id="bad", run_input=bad)
    failure = read(error.value.root, "failure.json")
    assert "run_error" in failure and "input_ref" not in failure
    assert not (error.value.root / "summary.json").exists()
    check_manifest(error.value.root, "failed")


def test_unknown_code_sha_is_omitted_and_real_git_sha_is_discovered(tmp_path, monkeypatch):
    req = request()
    result = run_minute_orders_research(req)
    expected = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    actual = artifacts.write_minute_orders_artifacts(req, result, tmp_path, run_id="git", evidence_level="synthetic")
    assert read(actual.root, "manifest.json")["code_sha"] == expected

    def unavailable(*args, **kwargs):
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(artifacts.subprocess, "run", unavailable)
    missing = artifacts.write_minute_orders_artifacts(req, result, tmp_path, run_id="unknown", evidence_level="synthetic")
    manifest = read(missing.root, "manifest.json")
    assert "code_sha" not in manifest and manifest["code_sha_source"] == "unavailable"


def test_provenance_and_outcome_validation_fail_closed(tmp_path):
    req = request()
    result = run_minute_orders_research(req)
    for options in ({"code_sha": "invented"}, {"evidence_level": "lake"}):
        kwargs = dict(code_sha=SHA, evidence_level="synthetic")
        kwargs.update(options)
        with pytest.raises(ValueError):
            artifacts.write_minute_orders_artifacts(req, result, tmp_path, run_id="bad", **kwargs)
        assert list(tmp_path.iterdir()) == []
    with pytest.raises(artifacts.ArtifactWriteError):
        artifacts.write_minute_orders_artifacts(req, replace(result, orders=()), tmp_path,
                                                run_id="bad", evidence_level="synthetic", code_sha=SHA)
    root = tmp_path / "backtest_output/minute_orders_research_v1/bad"
    assert not (root / "summary.json").exists()
    check_manifest(root, "failed")


@pytest.mark.parametrize("field", ["buckets", "order_totals"])
def test_inconsistent_committed_capacity_or_totals_cannot_publish_success(tmp_path, field):
    req = request()
    result = run_minute_orders_research(req)
    if field == "buckets":
        items = (replace(result.ledger.buckets[0], remaining=100),) + result.ledger.buckets[1:]
    else:
        items = (replace(result.ledger.order_totals[0], notional=D("9999.00")),)
    result = replace(result, ledger=replace(result.ledger, **{field: items}))
    with pytest.raises(artifacts.ArtifactWriteError, match="projection differs") as error:
        artifacts.write_minute_orders_artifacts(req, result, tmp_path, run_id="bad",
                                                evidence_level="synthetic", code_sha=SHA)
    assert not (error.value.root / "summary.json").exists()
    check_manifest(error.value.root, "failed")


def test_writer_import_fence_in_clean_process_and_no_import_time_io(tmp_path):
    code = textwrap.dedent("""
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        allowed = {'backtest', 'backtest.research', 'backtest.research.minute_orders_backend'}
        allowed.update('backtest.research.minute_orders_backend.' + part for part in
                       ('types', 'match', 'fees', 'ledger', 'clock', 'broker', 'runner', 'artifacts'))
        def permitted(name):
            return name in allowed or name.split('.')[0] in sys.stdlib_module_names
        class Fence:
            def find_spec(self, fullname, path=None, target=None):
                assert permitted(fullname), 'forbidden import: ' + fullname
        sys.meta_path.insert(0, Fence())
        before = set(sys.modules)
        context = os.getcwd(), dict(os.environ)
        from backtest.research.minute_orders_backend.artifacts import write_minute_orders_artifacts
        from backtest.research.minute_orders_backend.runner import run_minute_orders_research_with_artifacts
        assert all(permitted(name) for name in set(sys.modules) - before)
        assert context == (os.getcwd(), dict(os.environ))
        assert os.listdir('.') == []
    """)
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code,
                             str(Path(__file__).resolve().parents[1])],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
