"""Data-free evidence/comparator checks; these fixtures are NOT lake evidence."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile

import pytest

from scripts.research import verify_run_protocol_lake_parity as harness


@pytest.fixture
def pair(tmp_path):
    observations = []
    for side in ("direct", "l1"):
        root = tmp_path / side
        root.mkdir()
        (root / "trades.csv").write_text(
            "side,shares,price,commission,position_id,phase\n"
            "buy,100,10.00,1.00,600000@20251103,close\n"
            "sell,100,10.10,1.01,600000@20251103,close\n", encoding="utf-8")
        (root / "daily_equity.csv").write_text("date,equity\n20251103,9999\n20251104,10008\n", encoding="utf-8")
        (root / "summary.txt").write_text("NAV=10008\n", encoding="utf-8")
        (root / "execution-audit.json").write_text(json.dumps({"events": [{"phase": "close", "commission": 1.00}]}), encoding="utf-8")
        observations.append(harness.Observation(root, 0, b"native stdout\n", b""))
    return observations


def test_equal_artifacts_exit_and_streams_pass(pair):
    result = harness.compare_observations(*pair, harness.ComparePolicy(required_files=("trades.csv",)))
    assert result["status"] == "PASS" and result["byte_identical"]
    assert result["differences"] == []


@pytest.mark.parametrize("column,value", [
    ("shares", "200"), ("price", "10.01"), ("commission", "1.01"),
    ("position_id", "600001@20251103"), ("phase", "open"),
])
def test_economic_mismatch_has_exact_field_path(pair, column, value):
    path = pair[1].root / "trades.csv"
    lines = path.read_text().splitlines()
    columns, row = lines[0].split(","), lines[1].split(",")
    row[columns.index(column)] = value
    lines[1] = ",".join(row)
    path.write_text("\n".join(lines) + "\n")
    result = harness.compare_observations(*pair)
    assert result["status"] == "FAIL"
    assert result["differences"][0]["path"] == "trades.csv/rows/0/" + column


def test_trade_order_is_not_sorted_away(pair):
    path = pair[1].root / "trades.csv"
    header, buy, sell = path.read_text().splitlines()
    path.write_text("\n".join((header, sell, buy)) + "\n")
    assert harness.compare_observations(*pair)["status"] == "FAIL"


@pytest.mark.parametrize("both", [False, True])
def test_missing_required_file_fails_even_when_both_omit_it(pair, both):
    (pair[1].root / "trades.csv").unlink()
    if both:
        (pair[0].root / "trades.csv").unlink()
    result = harness.compare_observations(*pair, harness.ComparePolicy(required_files=("trades.csv",)))
    assert result["status"] == "FAIL"
    assert result["differences"][0]["path"] == "files/trades.csv"


def test_extra_file_is_not_ignored(pair):
    (pair[1].root / "unexpected.json").write_text("{}")
    assert harness.compare_observations(*pair)["differences"][0]["path"] == "files/unexpected.json"


@pytest.mark.parametrize("field,value", [("exit_code", 2), ("stdout", b"changed\xff"), ("stderr", b"warning\x00")])
def test_exit_and_raw_stream_differences_fail(pair, field, value):
    right = replace(pair[1], **{field: value})
    result = harness.compare_observations(pair[0], right)
    assert result["status"] == "FAIL"
    assert result["differences"][0]["path"].startswith(field)


def test_explicit_non_economic_json_policy_records_not_hides_diff(pair):
    for observation, stamp in zip(pair, ("2026-09-29T01:00:00Z", "2026-09-29T01:01:00Z")):
        (observation.root / "metadata.json").write_text(json.dumps({"created_at": stamp, "equity": 10}))
    policy = harness.ComparePolicy(allowed_json_fields=(("metadata.json", "/created_at"),))
    assert harness.compare_observations(*pair)["status"] == "FAIL"
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == "PASS" and not result["byte_identical"]
    assert result["differences"][0]["allowed"]
    (pair[1].root / "metadata.json").write_text(json.dumps({"created_at": "later", "equity": 11}))
    assert harness.compare_observations(*pair, policy)["status"] == "FAIL"


def test_duration_policy_keeps_counts_and_cache_posture_exact(pair):
    left = replace(pair[0], stdout=b"loaded minute=lake daily=lake: minute_names=2 daily_names=2 exdiv_names=0 st_names=2 in 1.23s\n")
    right = replace(pair[1], stdout=left.stdout.replace(b"1.23s", b"2.34s"))
    policy = harness.ComparePolicy(duration_stdout=True)
    result = harness.compare_observations(left, right, policy)
    assert result["status"] == "PASS" and not result["raw"]["stdout"]["byte_equal"]
    assert result["differences"][0]["path"] == "stdout/line/1"
    right = replace(right, stdout=right.stdout.replace(b"minute_names=2", b"minute_names=0"))
    assert harness.compare_observations(left, right, policy)["status"] == "FAIL"


def make_manifest(root):
    data = (root / "summary.txt").read_bytes()
    manifest = {"artifacts": [{"path": "artifacts/summary.txt", "md5": hashlib.md5(data).hexdigest(),
                              "sha256": harness.digest(data)}]}
    (root / "run-manifest.json").write_text(json.dumps(manifest))


def test_duration_derived_manifest_hashes_must_match_actual_bytes(pair):
    for observation, timing in zip(pair, ("1.0", "2.0")):
        (observation.root / "summary.txt").write_text(f"NAV=10008\n  耗时: 池 {timing}s | 日线 1.0s | 分钟 1.0s | 模拟 1.0s | 缓存 bypass\n")
        make_manifest(observation.root)
    policy = harness.ComparePolicy(duration_files=("summary.txt",), verify_manifest=True)
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == "PASS" and not result["byte_identical"]
    assert len(result["differences"]) == 3
    data = json.loads((pair[1].root / "run-manifest.json").read_text())
    data["artifacts"][0]["sha256"] = "0" * 64
    (pair[1].root / "run-manifest.json").write_text(json.dumps(data))
    assert harness.compare_observations(*pair, policy)["status"] == "FAIL"


def test_economic_summary_change_not_excused_by_derived_hash_policy(pair):
    (pair[1].root / "summary.txt").write_text("NAV=99999\n")
    for observation in pair:
        make_manifest(observation.root)
    result = harness.compare_observations(*pair, harness.ComparePolicy(duration_files=("summary.txt",), verify_manifest=True))
    assert result["status"] == "FAIL"


def test_normal_and_low_cash_cannot_pass_without_trigger(pair):
    passing = {"status": "PASS"}
    assert harness.cell_verdict("v7", "normal", pair, passing)[0] == "PASS"
    for family in ("csv_minute", "v7"):
        assert harness.cell_verdict(family, "low_cash", pair, passing)[0] == "NOT_COVERED"
    (pair[0].root / "trades.csv").write_text("side,shares\nbuy,100\n")
    assert harness.cell_verdict("v7", "normal", pair, passing)[0] == "NOT_COVERED"


def test_low_cash_refusal_requires_real_exception_signature(pair):
    passing = {"status": "PASS"}
    genuine = [replace(o, exit_code=1, stderr=b"backtest.research.csv_ledger.InsufficientCashError: InsufficientCashError: date=20251103 code=600000.SH needed=100 available=1\n") for o in pair]
    assert harness.cell_verdict("csv_minute", "low_cash", genuine, passing)[0] == "PASS"
    broken = [replace(o, exit_code=1, stderr=b"ModuleNotFoundError: pandas\n") for o in pair]
    assert harness.cell_verdict("csv_minute", "low_cash", broken, passing)[0] == "FAIL"
    for o in pair:
        (o.root / "trades.csv").write_text("side,reason\nskip,skip_cash\n")
    assert harness.cell_verdict("v7", "low_cash", pair, passing)[0] == "PASS"


@pytest.mark.parametrize("statuses,expected", [
    (["PASS", "PASS"], ("PASS", 0)), (["PASS", "FAIL"], ("FAIL", 1)),
    (["PASS", "NOT_RUN"], ("NOT_RUN", 2)), (["NOT_RUN", "FAIL"], ("FAIL", 1)),
    (["NOT_COVERED", "PASS"], ("NOT_COVERED", 3)),
])
def test_harness_exit_codes(statuses, expected):
    assert harness.aggregate_status([{"status": s} for s in statuses]) == expected


@pytest.fixture
def external_tmp():
    # This repository relocates pytest tmp_path inside the checkout. Harness
    # outputs deliberately must live outside it, even in this data-free test.
    with tempfile.TemporaryDirectory(prefix="cv01-test-") as directory:
        yield Path(directory)


def test_preregistration_precedes_refusals_and_no_lake_never_launches_live(external_tmp, monkeypatch, capsys):
    import scripts._script_bootstrap as bootstrap
    import sys

    output = external_tmp / "receipt"
    exact = "UnconfiguredDataRootError: actual resolver error for this test"
    monkeypatch.setattr(bootstrap, "resolve_oskh_python", lambda: Path(sys.executable))
    monkeypatch.setattr(harness, "resolve_roots", lambda: {"minute": {"error": exact}})
    monkeypatch.setattr(harness, "input_identity", lambda *args: {"sources": {"errors": [exact]}})
    calls = []

    def launch(side, family, argv, cwd, *args):
        recipe = json.loads((output / "recipe.json").read_text())
        assert recipe["experiment"] == "B-native-CV-01"
        assert "B_NATIVE_INVALID" in argv  # No live launch, even with a valid pool.
        calls.append((family, side))
        return harness.Observation(cwd / "artifacts", 2, b"", b"invalid choice: 'B_NATIVE_INVALID'")

    monkeypatch.setattr(harness, "launch", launch)
    assert harness.main(["--output-root", str(output)]) == 2
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "BLOCKED"
    assert len(calls) == 4
    assert sum(row["status"] == "NOT_RUN" for row in result["cells"]) == 6
    assert exact in capsys.readouterr().out
    with pytest.raises(FileExistsError):
        harness.main(["--output-root", str(output)])
