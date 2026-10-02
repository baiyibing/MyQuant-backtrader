from pathlib import Path

import pandas as pd
import pytest

from backtest.research.csv_pool import PoolDuplicateCodeError
from backtest.tools import file_compare


@pytest.mark.parametrize("second", ["000001", "000001.SZ", "sz000001"])
def test_compare_stock_files_rejects_normalized_duplicates(
    tmp_path: Path, monkeypatch, second: str
):
    path = tmp_path / "20260926.csv"
    path.write_text(f"代码,名称\n000001,first\n{second},second\n", encoding="utf-8")
    monkeypatch.setattr(
        file_compare, "read_simple_method", lambda _: pd.DataFrame([["000001", "first"]])
    )

    with pytest.raises(PoolDuplicateCodeError) as caught:
        file_compare.compare_stock_files(tmp_path / "source.xls", path)

    error = caught.value
    assert str(path) in str(error)
    assert "000001.SZ" in str(error)
    assert (error.first_line, error.second_line) == (2, 3)
    assert "2" in str(error) and "3" in str(error)


def test_comparison_duplicate_uses_physical_csv_line_numbers(tmp_path: Path):
    path = tmp_path / "20260926.csv"
    path.write_text(
        '# comment\n\n000001,"first\nname"\n600000,other\n000001.SZ,again\n',
        encoding="utf-8",
    )

    with pytest.raises(PoolDuplicateCodeError) as caught:
        file_compare._read_pool_csv_stocks(path)

    assert (caught.value.first_line, caught.value.second_line) == (3, 6)


def test_comparison_pool_keeps_gbk_and_normalized_codes(tmp_path: Path, monkeypatch):
    path = tmp_path / "20260926.csv"
    path.write_text("sz000001,平安银行\n600000.SH,浦发银行\n", encoding="gbk")
    monkeypatch.setattr(file_compare, "check_bom", lambda _: "unknown")
    monkeypatch.setattr(file_compare, "detect_encoding", lambda _: ("GB2312", 1.0))

    assert file_compare._read_pool_csv_stocks(path) == {
        "000001": "平安银行", "600000": "浦发银行"
    }


def test_comparison_accepts_same_code_in_distinct_day_files(tmp_path: Path):
    for day in ("20260925", "20260926"):
        path = tmp_path / f"{day}.csv"
        path.write_text("000001,name\n", encoding="utf-8")
        assert file_compare._read_pool_csv_stocks(path) == {"000001": "name"}
