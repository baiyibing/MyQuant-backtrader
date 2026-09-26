"""Unified-exit prechecks reject invalid pools before producing a report."""

from datetime import date
import json
from pathlib import Path
import subprocess
import sys

import pytest

from backtest.research import unified_exit_precheck as precheck
from backtest.research.csv_pool import PoolDuplicateCodeError


DAY = "20260106"


def _duplicate_pool(root: Path) -> Path:
    path = root / f"{DAY}.csv"
    path.write_text("code,name\n000001,first\nsz000001,second\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("entrypoint", ["_pool_and_calendar", "run_precheck"])
def test_precheck_duplicate_propagates_before_calendar_loading(
    tmp_path, monkeypatch, entrypoint,
):
    path = _duplicate_pool(tmp_path)
    monkeypatch.setattr(
        precheck, "load_index_daily_closes",
        lambda *args, **kwargs: pytest.fail("invalid pool must stop before lake access"),
    )

    with pytest.raises(PoolDuplicateCodeError) as error:
        if entrypoint == "run_precheck":
            precheck.run_precheck(DAY, DAY, pool_dir=tmp_path)
        else:
            precheck._pool_and_calendar(tmp_path, DAY, DAY)

    assert (error.value.path, error.value.code) == (path, "000001.SZ")
    assert (error.value.first_line, error.value.second_line) == (2, 3)


def test_precheck_cli_reports_duplicate_without_traceback(tmp_path):
    path = _duplicate_pool(tmp_path)
    destination = tmp_path / "report" / "precheck.json"
    repo = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable, str(repo / "scripts/research/report_unified_exit_precheck.py"),
            "--start", DAY, "--end", DAY, "--pool-dir", str(tmp_path),
            "--out-json", str(destination),
        ],
        cwd=repo, capture_output=True, text=True, check=False, timeout=30,
    )

    assert result.returncode == 1
    expected = PoolDuplicateCodeError(path, "000001.SZ", 2, 3)
    assert f"error: {expected}" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
    assert not destination.exists()


def test_valid_precheck_report_uses_instances_field(tmp_path, monkeypatch, capsys):
    (tmp_path / f"{DAY}.csv").write_text(
        "code,name\n000001,first\n600000,second\n", encoding="utf-8",
    )
    (tmp_path / "20260107.csv").write_text("000001,first\n", encoding="utf-8")
    monkeypatch.setattr(
        precheck, "load_index_daily_closes",
        lambda *args: {date(2026, 1, 6): 100.0, date(2026, 1, 7): 101.0},
    )
    report = precheck._pool_and_calendar(tmp_path, DAY, "20260107")
    assert report["pool"] == {
        "files": 2, "raw_rows": 3, "instances": 3, "union_codes": 2,
        "per_day_min": 1, "per_day_max": 2,
    }
    report.pop("_per_day")
    report.pop("_sess_ymd")
    report.update({
        "front": {
            "missing_codes": [], "early_stop_codes": [], "gap_ge10_count": 0,
            "frozen_instances": 0, "no_bar_buyday_instances": 0,
        },
        "limit": {},
        "exdiv": {
            "events": 0, "codes_with_events": 0, "gt5pct": 0,
            "mid_0p5_5pct": 0, "le0p5pct_noise": 0,
        },
        "concurrency": [],
        "fingerprint": {
            "files": 0, "bytes": 0, "mtime_min": None, "mtime_max": None,
            "meta_sha256": "", "body_sha256": "",
        },
    })
    monkeypatch.setattr(precheck, "run_precheck", lambda *args, **kwargs: report)
    destination = tmp_path / "precheck.json"

    assert precheck.main(["--pool-dir", str(tmp_path), "--out-json", str(destination)]) == 0

    output = capsys.readouterr()
    assert "[pool] files=2 rows=3 instances=3 union=2" in output.out
    assert "dedup" not in output.out and "dup_files" not in output.out
    assert output.err == ""
    assert json.loads(destination.read_text(encoding="utf-8"))["pool"] == report["pool"]
