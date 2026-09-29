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
    assert result["differences"][1]["path"] == "trades.csv/bytes"
    assert result["differences"][1]["allowed"] is False


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
    result = harness.compare_observations(*pair)
    assert result["status"] == "FAIL"
    assert result["differences"][0]["path"] == "files/unexpected.json"
    assert result["differences"][0]["allowed"] is False


@pytest.mark.parametrize("field,value", [("exit_code", 2), ("stdout", b"changed\xff"), ("stderr", b"warning\x00")])
def test_exit_and_raw_stream_differences_fail(pair, field, value):
    right = replace(pair[1], **{field: value})
    result = harness.compare_observations(pair[0], right)
    assert result["status"] == "FAIL"
    assert result["differences"][0]["path"].startswith(field)


@pytest.mark.parametrize("serialization", ["unchanged", "key_order", "whitespace"])
def test_explicit_non_economic_json_policy_records_not_hides_diff(pair, serialization):
    for observation, stamp in zip(pair, ("2026-09-29T01:00:00Z", "2026-09-29T01:01:00Z")):
        (observation.root / "metadata.json").write_text(json.dumps({"created_at": stamp, "equity": 10}))
    path = pair[1].root / "metadata.json"
    data = json.loads(path.read_text())
    if serialization == "key_order":
        path.write_text(json.dumps({"equity": data["equity"], "created_at": data["created_at"]}))
    elif serialization == "whitespace":
        path.write_text(json.dumps(data, indent=2) + "\n")
    policy = harness.ComparePolicy(allowed_json_fields=(("metadata.json", "/created_at"),))
    assert harness.compare_observations(*pair)["status"] == "FAIL"
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == ("PASS" if serialization == "unchanged" else "FAIL")
    assert not result["byte_identical"]
    assert result["raw"]["metadata.json"]["byte_equal"] is False
    assert result["differences"][0]["path"] == "metadata.json/created_at"
    assert result["differences"][0]["allowed"] is True
    assert result["differences"][1] == {
        "path": "metadata.json/bytes",
        "left": harness.digest((pair[0].root / "metadata.json").read_bytes()),
        "right": harness.digest(path.read_bytes()),
        "allowed": serialization == "unchanged",
        "reason": "raw bytes differ",
    }
    (pair[1].root / "metadata.json").write_text(json.dumps({"created_at": "later", "equity": 11}))
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == "FAIL"
    assert any(item["path"] == "metadata.json/equity" and item["allowed"] is False
               for item in result["differences"])
    assert result["differences"][-1]["path"] == "metadata.json/bytes"
    assert result["differences"][-1]["allowed"] is False


@pytest.mark.parametrize("left_json,right_json,pointers,status", [
    ('{"nested": [{"a/b~c": "old\\\"stamp\\\\字"}], "equity": 10}',
     '{"nested": [{"a/b~c": "new\\\"stamp\\\\字"}], "equity": 10}',
     ("/nested/0/a~1b~0c",), "PASS"),
    ('{"elapsed": 1, "equity": 1.0}', '{"elapsed": 222, "equity": 1.0}',
     ("/elapsed",), "PASS"),
    ('{"elapsed": 1, "equity": 1.0}', '{"elapsed": 222, "equity": 1.00}',
     ("/elapsed",), "FAIL"),
    ('{"created_at": "a", "checked_at": "b", "a": 0, "b": 0}',
     '{"created_at": "b", "checked_at": "a", "b": 0, "a": 0}',
     ("/created_at", "/checked_at"), "FAIL"),
    ('{"created_at": "a", "created_at": "a"}',
     '{"created_at": "b", "created_at": "b"}', ("/created_at",), "FAIL"),
])
def test_json_mask_is_scoped_to_encoded_values(pair, left_json, right_json, pointers, status):
    for observation, text in zip(pair, (left_json, right_json)):
        (observation.root / "metadata.json").write_text(text, encoding="utf-8")
    policy = harness.ComparePolicy(allowed_json_fields=tuple(("metadata.json", p) for p in pointers))
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == status and not result["byte_identical"]
    assert all(item["allowed"] for item in result["differences"][:-1])
    assert result["differences"][-1]["path"] == "metadata.json/bytes"
    assert result["differences"][-1]["allowed"] is (status == "PASS")


@pytest.mark.parametrize("right_json", [
    '{"equity": 10, "created_at": "same"}',
    '{ "created_at": "same", "equity": 10 }',
    '{"created_at": "later", "equity": 10',
])
def test_json_serialization_only_or_parse_error_keeps_bytes_disallowed(pair, right_json):
    (pair[0].root / "metadata.json").write_text('{"created_at": "same", "equity": 10}')
    (pair[1].root / "metadata.json").write_text(right_json)
    policy = harness.ComparePolicy(allowed_json_fields=(("metadata.json", "/created_at"),))
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == "FAIL" and not result["byte_identical"]
    assert len(result["differences"]) == 1
    assert result["differences"][0]["path"] == "metadata.json/bytes"
    assert result["differences"][0]["allowed"] is False


@pytest.mark.parametrize("line,forbidden_before,forbidden_after", [
    ("loaded minute=lake daily=lake: minute_names=2 daily_names=2 exdiv_names=0 st_names=2 in 1.23s\n",
     "minute_names=2", "minute_names=0"),
    ("  耗时: 池 1.23s | 日线 1.0s | 分钟 1.0s | 模拟 1.0s | 缓存 bypass\n",
     "缓存 bypass", "缓存 hit"),
    ("timing load=1.23s simulate=2.34s total=3.57s\n", "\n", "\r\n"),
])
def test_duration_policy_keeps_counts_and_cache_posture_exact(pair, line, forbidden_before, forbidden_after):
    left = replace(pair[0], stdout=line.encode("utf-8"))
    right = replace(pair[1], stdout=left.stdout.replace(b"1.23s", b"12.345s"))
    policy = harness.ComparePolicy(duration_stdout=True)
    assert harness.compare_observations(left, right)["status"] == "FAIL"
    result = harness.compare_observations(left, right, policy)
    assert result["status"] == "PASS" and not result["byte_identical"]
    assert not result["raw"]["stdout"]["byte_equal"]
    assert len(result["differences"]) == 2
    assert result["differences"][0]["path"] == "stdout/line/1"
    assert result["differences"][0]["allowed"] is True
    assert result["differences"][1]["path"] == "stdout/bytes"
    assert result["differences"][1]["allowed"] is True
    assert result["differences"][1]["left"] == harness.digest(left.stdout)
    assert result["differences"][1]["right"] == harness.digest(right.stdout)
    right = replace(right, stdout=right.stdout.replace(forbidden_before.encode("utf-8"), forbidden_after.encode("utf-8")))
    result = harness.compare_observations(left, right, policy)
    assert result["status"] == "FAIL"
    assert result["differences"][0]["allowed"] is False
    assert result["differences"][1]["allowed"] is False


def make_manifest(root):
    data = (root / "summary.txt").read_bytes()
    manifest = {"artifacts": [{"path": "artifacts/summary.txt", "md5": hashlib.md5(data).hexdigest(),
                              "sha256": harness.digest(data)}]}
    (root / "run-manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize("family,cell", [
    ("csv_minute", "normal"), ("csv_minute", "bad_output"),
    ("v7", "normal"), ("v7", "low_cash"), ("v7", "bad_output"),
])
def test_windows_lake_duration_only_stdout_bytes_pass(pair, family, cell):
    # Data-free reproduction of the five reported 4090 FAIL cells: summary
    # files use LF here, while Windows stdout has CRLF on both sides.
    observations = []
    for i, observation in enumerate(pair):
        summary = "NAV=10008\n"
        if family == "csv_minute":
            pool, daily, minute, sim = (("0.0", "1.2", "3.4", "5.6"),
                                       ("0.1", "12.3", "0.4", "56.7"))[i]
            summary += (f"  耗时: 池 {pool}s | 日线 {daily}s | 分钟 {minute}s | 模拟 {sim}s"
                        " | 缓存 bypass\n")
            stdout = "loaded daily 2 / minute 2 / pool days 2\n" + summary + "\n"
        else:
            load, sim, total = (("1.23", "2.34", "3.57"), ("12.34", "20.01", "32.35"))[i]
            stdout = ("loaded minute=lake daily=lake: minute_names=2 daily_names=2 "
                      f"exdiv_names=0 st_names=2 in {load}s\n")
            if cell != "bad_output":
                stdout += summary + f"timing load={load}s simulate={sim}s total={total}s\n"
        if cell == "bad_output":
            sentinel = observation.root / "artifacts"
            sentinel.write_bytes(b"B-native-CV-01 refusal sentinel\n")
            error = "NotADirectoryError" if family == "csv_minute" else "FileExistsError"
            observation = replace(observation, root=sentinel, exit_code=1,
                                  stderr=f"{error}: artifacts\r\n".encode())
        else:
            (observation.root / "summary.txt").write_bytes(summary.encode("utf-8"))
            if family == "csv_minute":
                make_manifest(observation.root)
            else:
                (observation.root / "run-config.json").write_bytes(b'{"minute_source": "lake"}\n')
                if cell == "low_cash":
                    (observation.root / "trades.csv").write_bytes(b"side,reason\nskip,skip_cash\n")
        observations.append(replace(observation, stdout=stdout.replace("\n", "\r\n").encode("utf-8")))

    policy = harness.ComparePolicy(
        required_files=() if cell == "bad_output" else harness.REQUIRED[family],
        duration_files=("summary.txt",), duration_stdout=True,
        verify_manifest=family == "csv_minute" and cell != "bad_output",
    )
    assert harness.compare_observations(*observations)["status"] == "FAIL"
    result = harness.compare_observations(*observations, policy)
    differences = {item["path"]: item for item in result["differences"]}
    if family == "csv_minute" and cell == "normal":
        for path in ("summary.txt/line/2", "summary.txt/bytes", "run-manifest.json/bytes"):
            assert differences[path]["allowed"] is True
    assert differences["stdout/bytes"]["allowed"] is True
    assert result["status"] == "PASS" and not result["byte_identical"]
    assert all(item["allowed"] for item in result["differences"])
    assert result["raw"]["stdout"] == {
        "left_sha256": harness.digest(observations[0].stdout),
        "right_sha256": harness.digest(observations[1].stdout), "byte_equal": False,
    }
    assert harness.cell_verdict(family, cell, observations, result)[0] == "PASS"


@pytest.mark.parametrize("ending", ["\n", "\r\n", ""])
@pytest.mark.parametrize("cache", ["", " | 缓存 bypass"])
def test_multiline_summary_and_stdout_duration_residue_preserves_endings(pair, ending, cache):
    observations = []
    for observation, durations in zip(pair, (("0.0", "1.2", "3.4", "5.6"),
                                           ("0.1", "12.3", "0.4", "56.7"))):
        pool, daily, minute, sim = durations
        text = ("NAV=10008\r\n\n"
                f"  耗时: 池 {pool}s | 日线 {daily}s | 分钟 {minute}s | 模拟 {sim}s{cache}{ending}")
        data = text.encode("utf-8")
        (observation.root / "summary.txt").write_bytes(data)
        observations.append(replace(observation, stdout=data))
    policy = harness.ComparePolicy(duration_files=("summary.txt",), duration_stdout=True)
    result = harness.compare_observations(*observations, policy)
    assert result["status"] == "PASS" and not result["byte_identical"]
    assert {item["path"] for item in result["differences"]} == {
        "summary.txt/line/3", "summary.txt/bytes", "stdout/line/3", "stdout/bytes",
    }
    assert all(item["allowed"] for item in result["differences"])


@pytest.mark.parametrize("field,value,path", [
    ("exit_code", 1, "exit_code"),
    ("stderr", b"warning\r\n", "stderr/bytes"),
    ("stdout", b"NAV=10008.000000001\r\n", "stdout/bytes"),
    ("stdout", b"NAV=10008\n", "stdout/bytes"),
    ("stdout", b"NAV=10008\r\n\r\n", "stdout/bytes"),
    ("trades.csv", b"side,shares,price,commission,position_id,phase\n"
     b"buy,100,10.000000001,1.00,600000@20251103,close\n"
     b"sell,100,10.10,1.01,600000@20251103,close\n", "trades.csv/bytes"),
    ("daily_equity.csv", b"date,equity\n20251103,9999\n20251104,10008.000000001\n", "daily_equity.csv/bytes"),
    ("execution-audit.json", b'{"events": [{"phase": "close", "commission": 1.000000001}]}',
     "execution-audit.json/bytes"),
])
def test_allowed_windows_timing_never_excuses_other_differences(pair, field, value, path):
    line = b"timing load=1.23s simulate=2.34s total=3.57s\r\n"
    left = replace(pair[0], stdout=line + b"NAV=10008\r\n")
    right = replace(pair[1], stdout=line.replace(b"1.23s", b"12.34s") + b"NAV=10008\r\n")
    if field == "stdout":
        right = replace(right, stdout=right.stdout.splitlines(keepends=True)[0] + value)
    elif field in ("exit_code", "stderr"):
        right = replace(right, **{field: value})
    else:
        (right.root / field).write_bytes(value)
    result = harness.compare_observations(left, right, harness.ComparePolicy(duration_stdout=True))
    assert result["status"] == "FAIL"
    differences = {item["path"]: item for item in result["differences"]}
    assert differences["stdout/line/1"]["allowed"] is True
    assert differences[path]["allowed"] is False


def test_duration_derived_manifest_hashes_must_match_actual_bytes(pair):
    for observation, timing in zip(pair, ("1.0", "2.0")):
        (observation.root / "summary.txt").write_text(f"NAV=10008\n  耗时: 池 {timing}s | 日线 1.0s | 分钟 1.0s | 模拟 1.0s | 缓存 bypass\n")
        make_manifest(observation.root)
    policy = harness.ComparePolicy(duration_files=("summary.txt",), verify_manifest=True)
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == "PASS" and not result["byte_identical"]
    assert len(result["differences"]) == 5
    assert all(item["allowed"] for item in result["differences"])
    assert {item["path"] for item in result["differences"]} == {
        "run-manifest.json/artifacts/0/md5", "run-manifest.json/artifacts/0/sha256",
        "run-manifest.json/bytes", "summary.txt/line/2", "summary.txt/bytes",
    }
    for item in result["differences"]:
        if item["path"].endswith("/bytes"):
            name = item["path"].removesuffix("/bytes")
            assert item["left"] == harness.digest((pair[0].root / name).read_bytes())
            assert item["right"] == harness.digest((pair[1].root / name).read_bytes())
    data = json.loads((pair[1].root / "run-manifest.json").read_text())
    data["artifacts"][0]["sha256"] = "0" * 64
    (pair[1].root / "run-manifest.json").write_text(json.dumps(data))
    result = harness.compare_observations(*pair, policy)
    assert result["status"] == "FAIL"
    assert any(item["path"] == "right/run-manifest.json/artifacts/0/sha256" and item["allowed"] is False
               for item in result["differences"])
    assert any(item["path"] == "run-manifest.json/bytes" and item["allowed"] is False
               for item in result["differences"])


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
