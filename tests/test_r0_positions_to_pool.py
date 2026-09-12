from pathlib import Path

import pytest

from backtest.research.csv_pool import parse_pool_csv
from scripts.data.r0_positions_to_pool import (
    convert_positions_file,
    parse_positions_text,
    resolve_source,
)


FIXTURE = Path(__file__).parent / "fixtures" / "r0_position_analysis.txt"


def test_converter_writes_only_non_empty_holdings_lists(tmp_path: Path):
    parsed = parse_positions_text(FIXTURE.read_text(encoding="utf-8"))
    assert parsed == {
        "20260302": [],
        "20260311": ["300190", "920014"],
    }

    out_dir = tmp_path / "pools"
    written = convert_positions_file(FIXTURE, out_dir)

    assert written == [out_dir / "20260311.csv"]
    assert not (out_dir / "20260302.csv").exists()
    assert (out_dir / "20260311.csv").read_text(encoding="utf-8").splitlines() == [
        "300190",
        "920014",
    ]
    assert parse_pool_csv(out_dir / "20260311.csv") == ["300190.SZ", "920014.BJ"]


def test_converter_ignores_the_holdings_table(tmp_path: Path):
    convert_positions_file(FIXTURE, tmp_path)
    assert "600000" not in (tmp_path / "20260311.csv").read_text(encoding="utf-8")


def test_converter_skips_report_date_range_header():
    text = (
        "日期范围: 2026-03-02 00:00:00 至 2026-03-23 00:00:00\n"
        "日期: 2026-03-03 00:00:00\n"
        "持仓标的列表: ['SZ300190']\n"
    )
    assert parse_positions_text(text) == {"20260303": ["300190"]}


def test_missing_explicit_source_reports_tried_path(tmp_path: Path):
    missing = tmp_path / "missing-position_analysis.txt"
    with pytest.raises(SystemExit, match="tried paths") as exc_info:
        resolve_source(missing)
    assert str(missing) in str(exc_info.value)
