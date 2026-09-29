"""Real synthetic CLI -> S4 artifacts, with hand calculations and failure exits."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from backtest.research.minute_orders_backend import artifacts, cli, runner
from backtest.research.minute_orders_backend.input_codec import load_run_input
from tests.test_minute_orders_artifacts import check_manifest, read
from tests.test_minute_orders_input_codec import FIXTURE, document

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/run_minute_orders_research.py"
SHA = "6cd29e6bf4fe06b4c2e5d27d5a93d0bc304745a6"  # Synthetic provenance override.
REL_ROOT = Path("backtest_output/minute_orders_research_v1/case")


def arguments(input_path=FIXTURE, parent="output"):
    return ["--input", str(input_path), "--parent", str(parent), "--run-id", "case",
            "--evidence-level", "synthetic", "--code-sha", SHA]


def launch(cwd, argv=None):
    return subprocess.run([sys.executable, str(SCRIPT), *(arguments() if argv is None else argv)],
                          cwd=cwd, capture_output=True, check=False, timeout=30)


def write_input(cwd, raw):
    path = cwd / "input.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def scenario_document(scenario):
    raw = document()
    data = raw["data"]
    if scenario == "mark_failure":
        data["marks"][1]["prices"] = []
    elif scenario == "rejected":
        data["initial_cash"] = "0.00"
    elif scenario == "illegal_economics":
        data["commands"][0]["qty"] = 101
    elif scenario == "parse_failure":
        data["commands"][0]["qty"] = True
    return raw


def test_cli_full_trace_partial_cancel_expiry_fee_reserve_handcalc(tmp_path):
    process = launch(tmp_path)
    assert process.returncode == 0, process.stderr
    assert process.stderr == b""
    report = json.loads(process.stdout)
    assert report["status"] == "success"
    root = tmp_path / "output" / REL_ROOT
    assert report["root"] == str(Path("output") / REL_ROOT)
    check_manifest(root, "success")
    summary = read(root, "summary.json")
    assert (summary["fill_count"], summary["filled_qty"], summary["fees_paid"]) == (3, 400, "10.00")
    assert summary["orders"] == [
        dict(order_id="A", status="Cancelled", filled_qty=300, remaining_qty=100, active=False),
        dict(order_id="E", status="Expired", filled_qty=100, remaining_qty=100, active=False),
    ]
    fills = read(root, "fills.jsonl")
    assert [(f["order_id"], f["qty"], f["fee_delta"]) for f in fills] == [
        ("A", 200, "5.00"), ("A", 100, "0.00"), ("E", 100, "5.00"),
    ]
    orders = read(root, "orders.jsonl")
    assert [o["reservation_after"]["cash"] for o in orders if o["order_id"] == "A"] == [
        "0.00", "4005.00", "2000.00", "1000.00", "0.00",
    ]
    assert [o["reservation_after"]["cash"] for o in orders if o["order_id"] == "E"] == [
        "0.00", "2005.00", "1000.00", "0.00",
    ]
    final = read(root, "ledger.jsonl")[-1]
    assert (final["cash"], final["reserved_cash"], final["fees_paid"]) == ("5990.00", "0.00", "10.00")
    assert sum(lot["qty"] for lot in final["lots"]) == 400
    assert {lot["sellable_date"] for lot in final["lots"]} == {"2026-09-29"}
    assert read(root, "marks.jsonl")[-1]["valuation_valid"] is True


@pytest.mark.parametrize("scenario,exit_code", [
    ("mark_failure", 3), ("illegal_economics", 3), ("rejected", 0), ("parse_failure", 2),
])
def test_failure_categories_and_business_rejects(scenario, exit_code, tmp_path):
    path = write_input(tmp_path, scenario_document(scenario))
    process = launch(tmp_path, arguments(path))
    assert process.returncode == exit_code, process.stderr
    root = tmp_path / "output" / REL_ROOT
    if exit_code == 2:
        assert not (tmp_path / "output").exists()
        assert json.loads(process.stderr)["status"] == "input_error"
    elif exit_code == 3:
        assert process.stdout == b""
        assert json.loads(process.stderr)["status"] == "engine_failed"
        check_manifest(root, "failed")
        assert not (root / "summary.json").exists()
        assert read(root, "failure.json")["stage"] == "run"
        assert len(read(root, "fills.jsonl")) == (1 if scenario == "mark_failure" else 0)
    else:
        check_manifest(root, "success")
        summary = read(root, "summary.json")
        assert summary["status_counts"]["Rejected"] == 2 and summary["fill_count"] == 0


@pytest.mark.parametrize("case", ["missing", "halted", "sell", "company_actions", "uncovered", "rounding"])
def test_explicit_input_policies_reach_native(case, tmp_path):
    raw = document()
    data = raw["data"]
    if case in ("missing", "halted"):
        for bucket in data["buckets"]:
            bucket[case] = True
            if case == "missing":
                bucket.update(close=None, volume_shares=None)
    elif case == "sell":
        data["initial_lots"] = [dict(lot_id="seed", symbol="X", acquire_date="2026-09-25",
                                    sellable_date="2026-09-28", qty=200, lot_size=100, reserved_qty=0)]
        data["commands"] = [dict(data["commands"][0], side="SELL", qty=100)]
    elif case == "company_actions":
        data["calendar"]["company_actions"] = [{"kind": "dividend", "cash": "0.50"}]
    elif case == "uncovered":
        data["calendar"]["company_actions_covered"] = False
    else:
        data["buy_fees"]["rounding"] = "unknown"
    process = launch(tmp_path, arguments(write_input(tmp_path, raw)))
    failed = case in ("company_actions", "uncovered", "rounding")
    assert process.returncode == (3 if failed else 0), process.stderr
    root = tmp_path / "output" / REL_ROOT
    check_manifest(root, "failed" if failed else "success")
    if not failed:
        summary = read(root, "summary.json")
        assert summary["fill_count"] == (1 if case == "sell" else 0)
        if case == "sell":
            assert summary["fees_paid"] == "2.00"
            assert read(root, "ledger.jsonl")[-1]["cash"] == "10998.00"


@pytest.mark.parametrize("flag", ["--input", "--parent", "--run-id", "--evidence-level"])
def test_required_arguments_have_no_defaults(flag, tmp_path):
    argv = arguments()
    i = argv.index(flag)
    del argv[i:i + 2]
    process = launch(tmp_path, argv)
    assert process.returncode == 2 and flag.encode() in process.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("flag,value", [
    ("--evidence-level", "lake"), ("--run-id", "../escape"), ("--code-sha", "short"),
    ("--parent", ""), ("--input", ""), ("--input", "missing.json"),
])
def test_invalid_arguments_never_create_output(flag, value, tmp_path):
    argv = arguments()
    argv[argv.index(flag) + 1] = value
    process = launch(tmp_path, argv)
    assert process.returncode == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["directory", "foreign", "file", "symlink", "dangling"])
def test_existing_root_is_never_reused(kind, tmp_path):
    root = tmp_path / "output" / REL_ROOT
    root.parent.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep").write_bytes(b"foreign evidence")
    if kind == "file":
        root.write_bytes(b"keep")
    elif kind in ("symlink", "dangling"):
        root.symlink_to(foreign if kind == "symlink" else tmp_path / "absent", target_is_directory=True)
    else:
        root.mkdir()
        if kind == "foreign":
            (root / "summary.json").write_bytes(b"existing summary")
    from tests.test_research_run_protocol_minute_orders import tree_bytes
    before = tree_bytes(tmp_path)
    process = launch(tmp_path)
    assert process.returncode == 4 and process.stdout == b""
    assert json.loads(process.stderr)["status"] == "output_error"
    assert tree_bytes(tmp_path) == before


def test_parent_file_is_output_error(tmp_path):
    (tmp_path / "output").write_bytes(b"keep")
    process = launch(tmp_path)
    assert process.returncode == 4
    assert (tmp_path / "output").read_bytes() == b"keep"


@pytest.mark.parametrize("mode,code", [
    ("success", 0), ("failed", 3), ("writer", 4), ("missing_summary", 4),
    ("bad_summary", 4), ("wrong_identity", 4), ("summary_hash", 4), ("unknown_status", 4),
    ("invalid_fees", 4), ("invalid_order", 4), ("invalid_counts", 4),
    ("lake_manifest", 4), ("failure_marker", 4), ("malformed_json", 4),
])
def test_one_wrapper_call_and_completion_validation(mode, code, tmp_path, monkeypatch, capsys):
    original = runner.run_minute_orders_research_with_artifacts
    calls = []

    def once(run_input, *args, **kwargs):
        calls.append(run_input)
        if mode == "failed":
            run_input = replace(run_input, marks=(replace(run_input.marks[1], prices=()),))
        result = original(run_input, *args, **kwargs)
        if mode == "missing_summary":
            (result.root / "summary.json").unlink()
        elif mode == "bad_summary":
            (result.root / "summary.json").write_text("{}", encoding="utf-8")
        elif mode == "wrong_identity":
            result = replace(result, input_hash="f" * 64)
        elif mode == "summary_hash":
            with (result.root / "summary.json").open("ab") as stream:
                stream.write(b" ")
        elif mode == "unknown_status":
            result = replace(result, status="returned")
        elif mode in ("invalid_fees", "invalid_order", "invalid_counts"):
            summary = read(result.root, "summary.json")
            if mode == "invalid_fees":
                summary["fees_paid"] = "NaN"
            elif mode == "invalid_order":
                summary["orders"][0]["filled_qty"] = True
            else:
                summary["status_counts"]["Filled"] = 100
            body = json.dumps(summary).encode()
            (result.root / "summary.json").write_bytes(body)
            manifest = read(result.root, "manifest.json")
            for ref in manifest["artifacts"]:
                if ref["path"] == "summary.json":
                    ref["sha256"] = hashlib.sha256(body).hexdigest()
            (result.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        elif mode == "lake_manifest":
            manifest = read(result.root, "manifest.json")
            manifest["evidence_level"] = "lake"
            (result.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        elif mode == "failure_marker":
            (result.root / "failure.json").write_text("{}", encoding="utf-8")
        elif mode == "malformed_json":
            (result.root / "summary.json").write_text("{", encoding="utf-8")
        return result

    if mode == "writer":
        original_write = artifacts._write_file

        def break_write(root, name, body):
            if name == "fills.jsonl":
                raise OSError("injected disk failure")
            return original_write(root, name, body)

        monkeypatch.setattr(artifacts, "_write_file", break_write)
    monkeypatch.setattr(runner, "run_minute_orders_research_with_artifacts", once)
    assert cli.main(arguments(parent=tmp_path)) == code
    assert calls == [load_run_input(FIXTURE)]
    captured = capsys.readouterr()
    assert bool(captured.out) is (code == 0)
    if mode == "writer":
        root = tmp_path / REL_ROOT
        check_manifest(root, "failed")
        assert read(root, "failure.json")["stage"] == "fills.jsonl"
        assert not (root / "summary.json").exists()


def test_parse_failure_never_calls_wrapper_and_system_exit_propagates(tmp_path, monkeypatch):
    calls = []
    error = SystemExit(17)

    def stop(*args, **kwargs):
        calls.append(1)
        raise error

    monkeypatch.setattr(runner, "run_minute_orders_research_with_artifacts", stop)
    path = write_input(tmp_path, scenario_document("parse_failure"))
    assert cli.main(arguments(path, tmp_path / "output")) == 2 and calls == []
    with pytest.raises(SystemExit) as caught:
        cli.main(arguments(parent=tmp_path / "output"))
    assert caught.value is error and calls == [1]
    assert not (tmp_path / "output").exists()


def test_native_script_full_run_imports_no_lake_or_legacy_engines(tmp_path):
    code = textwrap.dedent("""
        import runpy
        import sys
        blocked = ('oskh_data', 'l2_analytics', 'live_trading',
                   'backtest.research.csv_minute_backtest',
                   'backtest.research.csv_minute_backtest_v7',
                   'backtest.research.joint_return_replay',
                   'backtest.research.unified_exit_modeb')
        class Fence:
            def find_spec(self, fullname, path=None, target=None):
                assert not any(fullname == p or fullname.startswith(p + '.') for p in blocked), fullname
        sys.meta_path.insert(0, Fence())
        sys.argv = sys.argv[1:]
        runpy.run_path(sys.argv[0], run_name='__main__')
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", code, str(SCRIPT), *arguments()],
        cwd=tmp_path, capture_output=True, timeout=30, check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    check_manifest(tmp_path / "output" / REL_ROOT, "success")
