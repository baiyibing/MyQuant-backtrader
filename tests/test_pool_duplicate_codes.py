"""Same-day duplicates are input errors across every pool loading route."""

from datetime import date
from pathlib import Path

import pytest

from backtest.research import csv_pool, pool_list_quality
from backtest.research.capital_ration_probe import report_capital_ration
from backtest.research.csv_minute_backtest_v7 import load_pool_days
from backtest.research.topk_app_dropout import intersect_app_qlib
from backtest.research.unified_exit_modea import iterate_pool_entries
from backtest.research.unified_exit_precheck import _pool_and_calendar
from scripts.data.m5_hand_topn import truncate_pool_file


DAY = "20260106"
DAY_DATE = date(2026, 1, 6)


def _load(loader: str, root: Path):
    path = root / f"{DAY}.csv"
    if loader in {"parse_pool_csv", "parse_pool_csv_entries"}:
        return getattr(csv_pool, loader)(path)
    if loader in {"load_pool_day_map", "load_pool_name_map", "load_pool_names_by_day"}:
        return getattr(csv_pool, loader)(root, DAY, DAY)
    if loader == "validate_pool_dir":
        return csv_pool.validate_pool_dir(root)
    if loader in {"load_pool_codes_by_day", "report_pool_list_quality"}:
        return getattr(pool_list_quality, loader)(root)
    if loader == "v7":
        return load_pool_days(root, DAY_DATE, DAY_DATE)
    if loader == "mode_a":
        return iterate_pool_entries(root, [DAY])
    if loader == "precheck":
        return _pool_and_calendar(root, DAY, DAY)
    if loader == "capital_ration":
        return report_capital_ration(root / "unused_trades.csv", root)
    if loader == "app_intersection":
        return intersect_app_qlib(root, {DAY: ["600000"]}, start=DAY, end=DAY)
    if loader == "topn":
        return truncate_pool_file(path, 1)
    raise AssertionError(loader)


@pytest.mark.parametrize("loader", [
    "parse_pool_csv", "parse_pool_csv_entries", "validate_pool_dir",
    "load_pool_day_map", "load_pool_name_map", "load_pool_names_by_day",
    "load_pool_codes_by_day", "report_pool_list_quality", "v7", "mode_a",
    "precheck", "capital_ration", "app_intersection", "topn",
])
@pytest.mark.parametrize("repeated", ["000001", "000001.SZ", "sz000001"])
def test_all_pool_loaders_reject_normalized_duplicates(tmp_path, loader, repeated):
    path = tmp_path / f"{DAY}.csv"
    path.write_text(
        f'\ufeff代码,名称\n# comment,"\n000001,first\n\n600000,other\n{repeated},second\n',
        encoding="utf-8",
    )

    with pytest.raises(csv_pool.PoolDuplicateCodeError) as error:
        _load(loader, tmp_path)

    exc = error.value
    assert isinstance(exc, ValueError)
    assert (exc.path, exc.code, exc.first_line, exc.second_line) == (
        path, "000001.SZ", 3, 6,
    )
    assert str(path) in str(exc)
    assert "000001.SZ" in str(exc)
    assert "first occurrence at line 3" in str(exc)
    assert "second occurrence at line 6" in str(exc)


def test_daily_files_allow_the_same_code_on_different_dates(tmp_path):
    for day, code in [("20260105", "000001"), (DAY, "sz000001")]:
        (tmp_path / f"{day}.csv").write_text(f"{code},name\n", encoding="utf-8")

    expected = {"20260105": ["000001.SZ"], DAY: ["000001.SZ"]}
    assert csv_pool.load_pool_day_map(tmp_path, "20260105", DAY) == expected
    assert pool_list_quality.load_pool_codes_by_day(tmp_path) == expected
    assert csv_pool.load_pool_names_by_day(tmp_path, "20260105", DAY) == {
        day: {"000001.SZ": "name"} for day in expected
    }
    assert csv_pool.load_pool_name_map(tmp_path, "20260105", DAY) == {"000001.SZ": "name"}
    assert load_pool_days(tmp_path, date(2026, 1, 5), DAY_DATE) == {
        date(2026, 1, 5): ["000001.SZ"], DAY_DATE: ["000001.SZ"],
    }
    assert len(iterate_pool_entries(tmp_path, list(expected))) == 2


def test_quoted_name_continuation_is_not_a_pool_code(tmp_path):
    path = tmp_path / f"{DAY}.csv"
    path.write_text('000001,"name, with comma\n000001\n# name"\n', encoding="utf-8")
    assert csv_pool.parse_pool_csv_entries(path) == [
        ("000001.SZ", "name, with comma\n000001\n# name"),
    ]


def test_duplicate_after_multiline_field_uses_physical_lines(tmp_path):
    path = tmp_path / f"{DAY}.csv"
    path.write_text(
        'code,name\n\n000001,"first\nname"\n# comment\n000001.SZ,second\n',
        encoding="utf-8",
    )
    with pytest.raises(csv_pool.PoolDuplicateCodeError) as error:
        csv_pool.parse_pool_csv(path)
    assert (error.value.first_line, error.value.second_line) == (3, 6)


def test_duplicate_checker_scopes_multi_day_records_by_date(tmp_path):
    path = tmp_path / "multi_day.csv"
    seen = {}
    csv_pool.check_pool_duplicate(path, seen, "000001.SZ", 2, day="20260105")
    csv_pool.check_pool_duplicate(path, seen, "000001.SZ", 3, day=DAY)
    with pytest.raises(csv_pool.PoolDuplicateCodeError) as error:
        csv_pool.check_pool_duplicate(path, seen, "000001.SZ", 5, day=DAY)
    assert error.value.day == DAY
    assert (error.value.first_line, error.value.second_line) == (3, 5)
    assert DAY in str(error.value)


@pytest.mark.parametrize("side", ["primary", "other"])
def test_quality_report_and_cli_reject_duplicates_on_either_side(tmp_path, capsys, side):
    primary, other = tmp_path / "primary", tmp_path / "other"
    for root in (primary, other):
        root.mkdir()
        (root / f"{DAY}.csv").write_text("000001,name\n", encoding="utf-8")
    bad_path = (primary if side == "primary" else other) / f"{DAY}.csv"
    bad_path.write_text("000001,first\n000001,second\n", encoding="utf-8")

    with pytest.raises(csv_pool.PoolDuplicateCodeError):
        pool_list_quality.report_pool_list_quality(primary, other_dir=other)
    assert pool_list_quality.main([
        "--pool-dir", str(primary), "--other-dir", str(other),
    ]) == 1
    captured = capsys.readouterr()
    assert str(bad_path) in captured.err
    assert "000001.SZ" in captured.err
    assert "line 1" in captured.err and "line 2" in captured.err
    assert captured.out == ""
