from pathlib import Path

from datetime import date

from backtest.research.csv_pool import (
    load_pool_day_map,
    load_pool_names_by_day,
    parse_pool_csv,
    parse_pool_csv_entries,
    validate_pool_dir,
)


def test_parse_pool_csv_bare_codes_and_header(tmp_path: Path):
    path = tmp_path / "20260106.csv"
    path.write_text(
        "代码,名称\n002515,金字火腿\n600785,新华百货\n",
        encoding="utf-8",
        newline="\n",
    )
    assert parse_pool_csv(path) == ["002515.SZ", "600785.SH"]
    assert parse_pool_csv_entries(path) == [
        ("002515.SZ", "金字火腿"),
        ("600785.SH", "新华百货"),
    ]


def test_parse_excel_formula_code(tmp_path: Path):
    path = tmp_path / "20260106.csv"
    path.write_text('="000688",科创板\n', encoding="utf-8", newline="\n")
    assert parse_pool_csv(path) == ["000688.SZ"]


def test_parse_pool_csv_already_suffixed_and_comments(tmp_path: Path):
    path = tmp_path / "20260805.csv"
    path.write_text(
        "# comment\n\n600000.SH\n000001,extra\n600000\n",
        encoding="utf-8",
        newline="\n",
    )
    assert parse_pool_csv(path) == ["600000.SH", "000001.SZ"]


def test_validate_pool_dir_rejects_prefixed_code_but_parser_stays_loose(tmp_path: Path):
    path = tmp_path / "20260805.csv"
    path.write_text("代码,名称\nSZ300190,维尔利\n", encoding="utf-8", newline="\n")

    failures = validate_pool_dir(tmp_path)

    assert len(failures) == 1
    assert "SZ300190" in failures[0]
    assert parse_pool_csv(path) == ["300190.SZ"]
    assert parse_pool_csv_entries(path) == [("300190.SZ", "维尔利")]


def test_validate_pool_dir_accepts_exact_six_digit_rows(tmp_path: Path):
    (tmp_path / "20260805.csv").write_text(
        'code,name\n"300190",维尔利\n920014,倍益康\n',
        encoding="utf-8",
        newline="\n",
    )

    assert validate_pool_dir(tmp_path) == []


def test_validate_pool_dir_collects_filename_and_row_failures(tmp_path: Path):
    (tmp_path / "pool.csv").write_text("600000.SH,浦发银行\n", encoding="utf-8")
    (tmp_path / "20260230.csv").write_text("000001,平安银行\n", encoding="utf-8")

    failures = validate_pool_dir(tmp_path)

    assert len(failures) == 3
    assert any("pool.csv: filename" in failure for failure in failures)
    assert any("600000.SH" in failure for failure in failures)
    assert any("20260230.csv: filename" in failure for failure in failures)


def test_load_pool_day_map_empty_policy_and_key_type(tmp_path: Path):
    (tmp_path / "20260804.csv").write_text("代码,名称\n", encoding="utf-8")
    (tmp_path / "20260805.csv").write_text("600000,浦发银行\n", encoding="utf-8")

    omitted = load_pool_day_map(
        tmp_path, "20260804", "20260805", key="ymd", empty_in_map=False
    )
    assert omitted == {"20260805": ["600000.SH"]}

    retained = load_pool_day_map(
        tmp_path, date(2026, 8, 4), date(2026, 8, 5), key="date", empty_in_map=True
    )
    assert retained == {
        date(2026, 8, 4): [],
        date(2026, 8, 5): ["600000.SH"],
    }


def test_load_pool_names_by_day_keeps_dates_and_non_empty_names(tmp_path: Path):
    (tmp_path / "20260804.csv").write_text(
        "600000,浦发\n000001,\n", encoding="utf-8"
    )
    (tmp_path / "20260805.csv").write_text(
        "600000,*ST 浦发\n920014,倍益康\n", encoding="utf-8"
    )

    names = load_pool_names_by_day(tmp_path, "20260804", "20260805")

    assert names == {
        "20260804": {"600000.SH": "浦发"},
        "20260805": {"600000.SH": "*ST 浦发", "920014.BJ": "倍益康"},
    }
