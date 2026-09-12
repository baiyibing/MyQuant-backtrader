from pathlib import Path

from backtest.research.csv_pool import parse_pool_csv, parse_pool_csv_entries


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
