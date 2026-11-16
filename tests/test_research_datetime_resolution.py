"""The lake input contract preserves pandas 3.0.6 millisecond bars/hashes."""

import numpy as np
import pandas as pd
import pytest
from backtest.research import (
    ashare_bars,
    csv_daily_loader,
    minute_bar_scan_host,
    s11_exit_domain,
    signal_price_domain,
)
from common.infra.lake_datetime import utc_ms_index
from oskh_data.reader import StockDataReader
from scripts.data import export_strategy9_pool, export_strategy11_pool
from scripts.research.generate_off_byte_baseline import byte_skip_reason


@pytest.mark.parametrize("minute", [False, True])
def test_lake_loaders_preserve_millisecond_index_and_row_hashes(tmp_path, minute):
    dates = pd.bdate_range("20240902", periods=3).as_unit("ms")
    if minute:
        dates = (dates + pd.Timedelta(minutes=570)).as_unit("ms")
    expected = pd.DataFrame(
        {"open": [10., 11., 12.], "high": [10., 11., 12.],
         "low": [10., 11., 12.], "close": [10., 11., 12.], "volume": 100.},
        index=dates,
    )
    path = tmp_path / "symbol=600000_SH/data.parquet"
    path.parent.mkdir()
    source = expected.reset_index(drop=True)
    source.insert(0, "time", dates.asi8)
    source.to_parquet(path, index=False)
    strict, _ = signal_price_domain._read_strict(
        path, "600000.SH", "none", "20240902", "20240904", minute=minute
    )
    if minute:
        frames = [
            strict,
            ashare_bars.read_lake_minute_ohlc("600000.SH", tmp_path, "20240902", "20240904"),
            minute_bar_scan_host._load_lake_window("600000.SH", tmp_path, "20240902", "20240904"),
        ]
    else:
        _, front, _ = s11_exit_domain._read_partition(
            "600000.SH", path, domain="front", start="20240902", end="20240904"
        )
        frames = [
            strict, front,
            csv_daily_loader._read_one_daily("600000.SH", tmp_path, "20240902", "20240904"),
            export_strategy9_pool.read_one_daily_ohlcv("600000.SH", tmp_path, "20240902", "20240904"),
            export_strategy11_pool.read_front_daily("600000.SH", tmp_path, "20240902", "20240904"),
        ]
    for frame in frames:
        # Units affect pandas row hashes even when timestamps compare equal.
        actual = frame.loc[:, ["open", "high", "low", "close"]]
        reference = expected.loc[:, actual.columns]
        pd.testing.assert_frame_equal(actual, reference, check_freq=False)
        np.testing.assert_array_equal(
            pd.util.hash_pandas_object(actual), pd.util.hash_pandas_object(reference)
        )


def test_epoch_ms_handles_empty_nat_and_does_not_truncate_finer_precision():
    for values in ([], [np.nan], [1725235200000]):
        assert str(utc_ms_index(values).dtype) == "datetime64[ms, UTC]"
    finer = utc_ms_index([1725235200000.5])
    assert str(finer.dtype) == "datetime64[ns, UTC]"
    assert finer[0] == pd.Timestamp("2024-09-02 00:00:00.000500", tz="UTC")


@pytest.mark.parametrize("version", ["3.0.6", "3.1.1"])
def test_validated_pandas_versions_require_golden_csv_bytes(monkeypatch, version):
    monkeypatch.setattr(pd, "__version__", version)
    assert byte_skip_reason("3.0.6") is None


@pytest.mark.parametrize("mode", ["parquet", "duckdb"])
@pytest.mark.parametrize("entry", ["read_stock", "scan_stocks"])
def test_infra_reader_host_preserves_index_unit(tmp_path, mode, entry):
    dates = pd.DatetimeIndex(["2024-09-02", "2024-09-03"]).as_unit("ms")
    path = tmp_path / "stock/period=1d/dividend_type=none/symbol=600000_SH/data.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame({"time": dates.asi8, "open": [10., 11.], "close": [10., 11.]}).to_parquet(
        path, index=False
    )
    with StockDataReader(base_dir=str(tmp_path / "stock"), project_root=str(tmp_path), mode=mode) as reader:
        code = "600000.SH" if entry == "read_stock" else ["600000.SH"]
        frame = getattr(reader, entry)(code, adjust_type="none", columns=["open", "close"])
    pd.testing.assert_index_equal(frame.index, dates.rename("datetime"), check_names=True)
    assert frame["time"].tolist() == dates.asi8.tolist()
