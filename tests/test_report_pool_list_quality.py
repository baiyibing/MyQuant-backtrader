# -*- coding: utf-8 -*-
"""H9 pool list-quality reporter (tmp_path fixtures)."""

from __future__ import annotations

from pathlib import Path

from backtest.research.pool_list_quality import (
    code_count_histogram,
    empty_day_stems,
    format_report,
    load_pool_codes_by_day,
    main,
    overlap_pools,
    report_pool_list_quality,
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

    bad = tmp_path / "bad"
    _write(bad / "20260303.csv", "SZ300190,x\n")
    assert main(["--pool-dir", str(bad)]) == 1

    assert main(["--pool-dir", str(tmp_path / "missing")]) == 2
