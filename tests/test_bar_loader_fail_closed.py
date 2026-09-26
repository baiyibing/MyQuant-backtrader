"""Unreadable book-bar sources abort instead of dropping affected symbols."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backtest.research import ashare_bars, qlib_bin_1min, qlib_bin_daily
from oskh_data.symbol_format import to_partition_key

CODE = "600000.SH"
OTHER_CODE = "600519.SH"
DAY = "20260901"


def _qlib_root(root: Path) -> Path:
    (root / "features").mkdir()
    calendars = root / "calendars"
    calendars.mkdir()
    (calendars / "day.txt").write_text("2026-09-01\n", encoding="utf-8")
    (calendars / "1min.txt").write_text("2026-09-01 09:30:00\n", encoding="utf-8")
    return root


def _partition_file(root: Path, code: str) -> Path:
    path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _assert_minute_read_error(error, code: str, path: Path) -> None:
    assert error.code == code
    assert Path(error.path) == path
    assert code in str(error)
    assert str(path) in str(error)
    assert isinstance(error.__cause__, Exception)
    assert not isinstance(error.__cause__, ashare_bars.MinuteBarReadError)


def test_qlib_daily_loader_propagates_read_error(tmp_path, monkeypatch):
    root = _qlib_root(tmp_path)
    original = OSError("daily feature read failed")

    def fail_read(*_args):
        raise original

    monkeypatch.setattr(qlib_bin_daily, "_read_one", fail_read)

    with pytest.raises(qlib_bin_daily.QlibBinReadError) as caught:
        qlib_bin_daily.load_qlib_bin_daily_bars(
            {CODE}, DAY, DAY, qlib_root=root, workers=1
        )

    assert caught.value.code == CODE
    assert CODE in str(caught.value)
    assert caught.value.__cause__ is original


def test_qlib_daily_loader_omits_none_without_raising(tmp_path, monkeypatch):
    root = _qlib_root(tmp_path)
    monkeypatch.setattr(qlib_bin_daily, "_read_one", lambda *_args: None)

    result = qlib_bin_daily.load_qlib_bin_daily_bars(
        {CODE}, DAY, DAY, qlib_root=root, workers=1
    )

    assert result == {}


def test_qlib_1min_loader_propagates_read_error(tmp_path, monkeypatch):
    root = _qlib_root(tmp_path)
    original = OSError("minute feature read failed")

    def fail_read(*_args):
        raise original

    monkeypatch.setattr(qlib_bin_1min, "_read_one", fail_read)

    with pytest.raises(qlib_bin_daily.QlibBinReadError) as caught:
        qlib_bin_1min.load_qlib_bin_1min_bars(
            {CODE},
            date(2026, 9, 1),
            date(2026, 9, 1),
            qlib_root=root,
            workers=1,
            preload_days=0,
        )

    assert caught.value.code == CODE
    assert CODE in str(caught.value)
    assert caught.value.__cause__ is original


def test_minute_non_volume_corrupt_parquet_raises(tmp_path):
    path = _partition_file(tmp_path, CODE)
    path.write_bytes(b"not a parquet")

    with pytest.raises(ashare_bars.MinuteBarReadError) as caught:
        ashare_bars.read_lake_minute_ohlc(
            CODE, tmp_path, DAY, DAY, include_volume=False
        )

    _assert_minute_read_error(caught.value, CODE, path)


def test_minute_non_volume_missing_file_returns_none(tmp_path):
    result = ashare_bars.read_lake_minute_ohlc(
        CODE, tmp_path, DAY, DAY, include_volume=False
    )

    assert result is None


def test_load_minute_from_lake_does_not_drop_corrupt_sibling(tmp_path):
    stamp = pd.Timestamp("2026-09-01 09:30:00", tz="UTC")
    pd.DataFrame(
        {
            "time": [int(stamp.timestamp() * 1000)],
            "open": [10.0],
            "high": [10.5],
            "low": [9.9],
            "close": [10.3],
        }
    ).to_parquet(_partition_file(tmp_path, CODE), index=False)
    expected = pd.DataFrame(
        {
            "open": [10.0],
            "high": [10.5],
            "low": [9.9],
            "close": [10.3],
            "ymd": [DAY],
            "hm": [570],
        },
        index=pd.DatetimeIndex([stamp.tz_localize(None)]).as_unit("ns"),
    )
    readable = ashare_bars.load_minute_from_lake(
        {CODE}, DAY, DAY, workers=1, lake_root=tmp_path, include_volume=False
    )
    # pandas 2.x patch builds vary: to_datetime(unit="ms") may keep ms or resolve to ns.
    # Compare both sides in ns so the assertion is patch-version independent.
    got = readable[CODE].copy()
    got.index = got.index.as_unit("ns")
    pd.testing.assert_frame_equal(got, expected)
    path = _partition_file(tmp_path, OTHER_CODE)
    path.write_bytes(b"not a parquet")

    with pytest.raises(ashare_bars.MinuteBarReadError) as caught:
        ashare_bars.load_minute_from_lake(
            {CODE, OTHER_CODE},
            DAY,
            DAY,
            workers=1,
            lake_root=tmp_path,
            include_volume=False,
        )

    _assert_minute_read_error(caught.value, OTHER_CODE, path)
