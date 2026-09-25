"""Daily lake loading distinguishes missing partitions from failed reads."""

from pathlib import Path

import pandas as pd
import pytest

from backtest.research import csv_daily_loader as loader
from oskh_data.symbol_format import to_partition_key

VALID_CODE = "600000.SH"
OTHER_CODE = "600519.SH"
START = "20260901"
END = "20260902"


def _partition_file(root: Path, code: str) -> Path:
    path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_valid_partition(root: Path, code: str) -> pd.DataFrame:
    dates = pd.to_datetime(["2026-09-01", "2026-09-02"]).as_unit("ms")
    expected = pd.DataFrame(
        {
            "open": [10.0, 10.5],
            "high": [10.8, 10.9],
            "low": [9.9, 10.2],
            "close": [10.5, 10.7],
        },
        index=dates,
        dtype="float64",
    )
    frame = expected.reset_index(drop=True)
    frame.insert(
        0,
        "time",
        [int(date.tz_localize("UTC").timestamp() * 1000) for date in dates],
    )
    frame.to_parquet(_partition_file(root, code), index=False)
    return expected


def _assert_read_error(error: loader.DailyBarReadError, code: str, path: Path):
    assert error.code == code
    assert Path(error.path) == path
    assert code in str(error)
    assert str(path) in str(error)
    assert isinstance(error.__cause__, Exception)
    assert not isinstance(error.__cause__, loader.DailyBarReadError)


def test_read_one_daily_missing_file_returns_none(tmp_path):
    assert loader._read_one_daily(VALID_CODE, tmp_path, START, END) is None


def test_read_one_daily_empty_range_returns_none(tmp_path):
    _write_valid_partition(tmp_path, VALID_CODE)

    result = loader._read_one_daily(VALID_CODE, tmp_path, "20260903", "20260904")

    assert result is None


def test_read_one_daily_corrupt_bytes_raise(tmp_path):
    path = _partition_file(tmp_path, VALID_CODE)
    path.write_bytes(b"not a parquet")

    with pytest.raises(loader.DailyBarReadError) as caught:
        loader._read_one_daily(VALID_CODE, tmp_path, START, END)

    _assert_read_error(caught.value, VALID_CODE, path)


def test_load_daily_bars_omits_missing_symbol_and_keeps_valid_sibling(tmp_path):
    expected = _write_valid_partition(tmp_path / "dividend_type=none", VALID_CODE)

    result = loader.load_daily_bars(
        {VALID_CODE, OTHER_CODE}, START, END, workers=1, daily_root=tmp_path
    )

    assert set(result) == {VALID_CODE}
    pd.testing.assert_frame_equal(result[VALID_CODE], expected)


def test_load_daily_bars_corrupt_symbol_fails_closed(tmp_path):
    root = tmp_path / "dividend_type=none"
    _write_valid_partition(root, VALID_CODE)
    path = _partition_file(root, OTHER_CODE)
    path.write_bytes(b"not a parquet")

    with pytest.raises(loader.DailyBarReadError) as caught:
        loader.load_daily_bars(
            {VALID_CODE, OTHER_CODE}, START, END, workers=1, daily_root=tmp_path
        )

    _assert_read_error(caught.value, OTHER_CODE, path)
