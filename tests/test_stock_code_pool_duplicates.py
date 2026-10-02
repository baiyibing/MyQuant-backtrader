"""Legacy pool readers enforce the shared same-day duplicate contract."""

from pathlib import Path

import pytest

from backtest.research.csv_pool import PoolDuplicateCodeError
from common.infra.qmt_utils_adv import StockCodeProcessor, read_stock_codes
from oskh_data.integrity import collect_stock_codes


@pytest.mark.parametrize("loader", [StockCodeProcessor.read_stock_codes, read_stock_codes])
@pytest.mark.parametrize("second", ["000001", "000001.SZ", "sz000001"])
def test_legacy_pool_rejects_normalized_duplicate(tmp_path, loader, second):
    path = tmp_path / "20260921.csv"
    path.write_text(f"000001,first\n{second},second\n", encoding="utf-8")

    with pytest.raises(PoolDuplicateCodeError) as caught:
        loader(str(path))

    error = caught.value
    assert error.path == path
    assert error.code == "000001.SZ"
    assert (error.first_line, error.second_line) == (1, 2)
    for expected in (str(path), "000001.SZ", "1", "2"):
        assert expected in str(error)


def test_legacy_pool_duplicate_reports_physical_record_start(tmp_path):
    path = tmp_path / "20260921.csv"
    path.write_text(
        'code,name\n\n# 000001,comment\n000001,"first\nname"\n\nsz000001,second\n',
        encoding="utf-8",
    )

    with pytest.raises(PoolDuplicateCodeError) as caught:
        read_stock_codes(str(path))

    assert (caught.value.first_line, caught.value.second_line) == (4, 7)


def test_legacy_pool_keeps_dataframe_and_detected_encoding(tmp_path):
    path = tmp_path / "20260921.csv"
    path.write_bytes("000001,平安银行\n600000,浦发银行\n".encode("gbk"))

    frame = read_stock_codes(str(path))

    assert frame is not None
    assert frame.columns.tolist() == ["stock_code", "stock_name"]
    assert frame["stock_code"].tolist() == ["000001", "600000"]
    assert frame["stock_name"].tolist() == ["平安银行", "浦发银行"]


def test_integrity_collector_propagates_duplicate(tmp_path):
    path = tmp_path / "20260921.csv"
    path.write_text("000001,first\n000001.SZ,second\n", encoding="utf-8")

    with pytest.raises(PoolDuplicateCodeError) as caught:
        collect_stock_codes(str(tmp_path), "20260921", "20260922")

    assert caught.value.path == path
    assert (caught.value.first_line, caught.value.second_line) == (1, 2)


def test_integrity_collector_allows_same_code_on_different_days(tmp_path):
    for day in ("20260921", "20260922"):
        Path(tmp_path, f"{day}.csv").write_text("000001,平安银行\n", encoding="utf-8")

    assert collect_stock_codes(str(tmp_path), "20260921", "20260922") == {"000001.SZ"}
