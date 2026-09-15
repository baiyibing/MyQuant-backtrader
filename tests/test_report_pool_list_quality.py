# -*- coding: utf-8 -*-
"""H9/H16 pool list-quality reporter (tmp_path fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backtest.research.csv_pool import validate_pool_dir
from backtest.research.pool_list_quality import (
    code_count_histogram,
    day_over_day_churn,
    empty_day_stems,
    format_report,
    format_report_json,
    format_report_markdown,
    invalid_calendar_stems,
    load_pool_codes_by_day,
    main,
    overlap_pools,
    report_pool_list_quality,
    top_frequent_codes,
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def test_load_and_histogram_empty_and_nonempty(tmp_path: Path):
    pool = tmp_path / "pool"
    _write(pool / "20260303.csv", "代码,名称\n600000,浦发\n000001,平安\n")
    _write(pool / "20260304.csv", "代码,名称\n")
    _write(pool / "20260305.csv", "600000,浦发\n600001,邯郸\n600002,齐鲁\n")
    _write(pool / "notes.txt", "ignore me\n")

    by_day = load_pool_codes_by_day(pool)
    assert set(by_day) == {"20260303", "20260304", "20260305"}
    assert len(by_day["20260303"]) == 2
    assert by_day["20260304"] == []
    assert len(by_day["20260305"]) == 3
    assert empty_day_stems(by_day) == ["20260304"]
    assert code_count_histogram(by_day) == {0: 1, 2: 1, 3: 1}


def test_validate_errors_surface_in_report(tmp_path: Path):
    pool = tmp_path / "pool"
    _write(pool / "20260303.csv", "代码,名称\nSZ300190,维尔利\n")
    _write(pool / "badname.csv", "600000,浦发\n")

    report = report_pool_list_quality(pool)
    assert report.day_count == 1
    assert len(report.validation_errors) >= 2
    assert any("SZ300190" in e for e in report.validation_errors)
    assert any("badname.csv" in e for e in report.validation_errors)
    text = format_report(report)
    assert "validate_pool_dir errors" in text
    assert "SZ300190" in text


def test_overlap_jaccard_and_day_sets(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write(a / "20260303.csv", "600000,a\n000001,b\n")
    _write(a / "20260304.csv", "600000,a\n")
    _write(a / "20260305.csv", "600000,a\n")
    _write(b / "20260303.csv", "600000,a\n600001,c\n")
    _write(b / "20260304.csv", "600000,a\n")
    _write(b / "20260306.csv", "000001,b\n")

    report = report_pool_list_quality(a, other_dir=b)
    assert report.overlap is not None
    ov = report.overlap
    assert ov.shared_days == ["20260303", "20260304"]
    assert ov.days_only_a == ["20260305"]
    assert ov.days_only_b == ["20260306"]
    by_ymd = {d.ymd: d for d in ov.per_day}
    assert by_ymd["20260303"].n_intersection == 1
    assert abs(by_ymd["20260303"].jaccard - (1 / 3)) < 1e-9
    assert by_ymd["20260304"].jaccard == 1.0
    assert ov.mean_jaccard is not None
    assert abs(ov.mean_jaccard - (by_ymd["20260303"].jaccard + 1.0) / 2) < 1e-9


def test_overlap_pools_empty_union_is_jaccard_one():
    ov = overlap_pools({"20260101": []}, {"20260101": []})
    assert ov.per_day[0].jaccard == 1.0
    assert ov.per_day[0].n_intersection == 0


def test_main_cli_exit_codes(tmp_path: Path, capsys):
    pool = tmp_path / "pool"
    _write(pool / "20260303.csv", "600000,浦发\n")
    assert main(["--pool-dir", str(pool)]) == 0
    out = capsys.readouterr().out
    assert "day_count: 1" in out
    assert "validate_pool_dir errors (0)" in out
    assert "valid_calendar_day_count: 1" in out

    bad = tmp_path / "bad"
    _write(bad / "20260303.csv", "SZ300190,x\n")
    assert main(["--pool-dir", str(bad)]) == 1

    assert main(["--pool-dir", str(tmp_path / "missing")]) == 2


def test_invalid_calendar_stems_reported(tmp_path: Path):
    pool = tmp_path / "pool"
    _write(pool / "20260303.csv", "600000,a\n")
    _write(pool / "20260230.csv", "000001,b\n")  # invalid calendar

    by_day = load_pool_codes_by_day(pool)
    assert invalid_calendar_stems(by_day) == ["20260230"]
    report = report_pool_list_quality(pool)
    assert report.day_count == 2
    assert report.valid_calendar_day_count == 1
    assert report.invalid_calendar_stems == ["20260230"]
    assert "invalid_calendar_stems (1): 20260230" in format_report(report)
    # validate_pool_dir also flags the bad filename
    assert any("20260230" in e for e in report.validation_errors)


def test_top_frequent_codes_and_churn(tmp_path: Path):
    pool = tmp_path / "pool"
    _write(pool / "20260303.csv", "600000,a\n000001,b\n")
    _write(pool / "20260304.csv", "600000,a\n600001,c\n")
    _write(pool / "20260305.csv", "600000,a\n")

    by_day = load_pool_codes_by_day(pool)
    top = top_frequent_codes(by_day, top_n=2)
    assert top[0] == ("600000.SH", 3)
    assert top[1][1] == 1  # tie among 1-day codes; stable by code asc
    assert top_frequent_codes(by_day, top_n=0) == []

    ch = day_over_day_churn(by_day)
    assert len(ch.per_day) == 2
    assert ch.per_day[0].from_ymd == "20260303"
    assert ch.per_day[0].to_ymd == "20260304"
    assert ch.per_day[0].n_added == 1  # 600001.SH
    assert ch.per_day[0].n_removed == 1  # 000001.SZ
    assert ch.per_day[1].n_added == 0
    assert ch.per_day[1].n_removed == 1  # 600001.SH
    assert ch.total_added == 1
    assert ch.total_removed == 2

    report = report_pool_list_quality(pool, top_n=5)
    assert report.top_codes[0] == ("600000.SH", 3)
    assert report.churn is not None
    assert "churn: transitions=2" in format_report(report)


def test_format_json_and_markdown(tmp_path: Path, capsys):
    pool = tmp_path / "pool"
    _write(pool / "20260303.csv", "600000,a\n000001,b\n")
    _write(pool / "20260304.csv", "600000,a\n")

    report = report_pool_list_quality(pool, top_n=3)
    payload = json.loads(format_report_json(report))
    assert payload["day_count"] == 2
    assert payload["valid_calendar_day_count"] == 2
    assert payload["top_codes"][0] == {"code": "600000.SH", "days": 2}
    assert "codes_by_day" not in payload
    assert payload["churn"]["total_removed"] == 1

    md = format_report_markdown(report)
    assert "# Pool list-quality summary" in md
    assert "| `600000.SH` | 2 |" in md
    assert "Day-over-day churn" in md

    assert main(["--pool-dir", str(pool), "--format", "json", "--top-n", "1"]) == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert len(parsed["top_codes"]) == 1

    assert main(["--pool-dir", str(pool), "--format", "markdown"]) == 0
    md_out = capsys.readouterr().out
    assert md_out.startswith("# Pool list-quality summary")


@pytest.mark.parametrize("fmt", ["text", "json", "markdown"])
@pytest.mark.parametrize("side", ["primary", "other", "both"])
@pytest.mark.parametrize("filename,body,diagnostic", [
    ("20260303.csv", "SZ300190,x\n", "SZ300190"),
    ("20260230.csv", "600000,x\n", "20260230.csv"),
    ("badname.csv", "600000,x\n", "badname.csv"),
])
def test_two_dir_contract_errors(tmp_path, capsys, fmt, side, filename, body, diagnostic):
    primary, other = tmp_path / "a", tmp_path / "b"
    for label, directory in [("primary", primary), ("other", other)]:
        _write(directory / "20260303.csv", "600000,x\n")
        if side in (label, "both"):
            _write(directory / filename, body)

    report = report_pool_list_quality(primary, other_dir=other)
    assert report.validation_errors == validate_pool_dir(primary)
    assert report.other_validation_errors == validate_pool_dir(other)
    assert main([
        "--pool-dir", str(primary), "--other-dir", str(other), "--format", fmt,
    ]) == 1
    output = capsys.readouterr().out
    if fmt == "json":
        payload = json.loads(output)
        errors = payload["validation_errors_by_side"]
        assert payload["validation_errors"] == errors["primary"]
    else:
        prefix = "## " if fmt == "markdown" else ""
        primary_output, other_output = output.split(f"{prefix}other validate_pool_dir", 1)
        assert f"{prefix}primary validate_pool_dir" in primary_output
        errors = {"primary": primary_output, "other": other_output}
    for label in ("primary", "other"):
        assert (diagnostic in str(errors[label])) == (side in (label, "both"))


def test_two_clean_dirs_exit_zero(tmp_path, capsys):
    primary, other = tmp_path / "a", tmp_path / "b"
    for directory in (primary, other):
        _write(directory / "20260303.csv", "600000,x\n")
    assert main(["--pool-dir", str(primary), "--other-dir", str(other)]) == 0
    output = capsys.readouterr().out
    assert "primary validate_pool_dir errors (0)" in output
    assert "other validate_pool_dir errors (0)" in output
    assert "mean_jaccard=1.0000" in output


@pytest.mark.parametrize("side", ["primary", "other"])
@pytest.mark.parametrize("failure", ["missing", "file", "read", "scan"])
def test_two_dir_io_errors_exit_two(tmp_path, capsys, monkeypatch, side, failure):
    primary, other = tmp_path / "a", tmp_path / "b"
    broken = primary if side == "primary" else other
    good = other if side == "primary" else primary
    # IO errors take precedence even when the opposite side has contract errors.
    _write(good / "20260303.csv", "SZ300190,x\n")
    if failure == "file":
        _write(broken, "not a directory\n")
    elif failure in ("read", "scan"):
        _write(broken / "20260303.csv", "600000,x\n")
        method = "read_text" if failure == "read" else "glob"
        original = getattr(Path, method)

        def fail(path, *args, **kwargs):
            if path == broken or path.parent == broken:
                raise PermissionError("fixture denied")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, method, fail)
    assert main(["--pool-dir", str(primary), "--other-dir", str(other)]) == 2
    captured = capsys.readouterr()
    if failure in ("missing", "file"):
        assert ("--pool-dir" if side == "primary" else "--other-dir") in captured.err
    else:
        assert side in captured.out + captured.err
        assert "fixture denied" in captured.out + captured.err
