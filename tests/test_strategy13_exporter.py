import numpy as np
import pandas as pd
import pytest

from scripts.data.export_beidou_pool import attach_float_history, main, scan_frames, signal_mask


def frame():
    idx = pd.bdate_range("20250101", periods=130)
    c = np.linspace(9, 10, len(idx))
    c[-2:] = [10.8, 10.85]
    f = pd.DataFrame({"open": c - .01, "high": c + .01, "close": c,
                      "volume": 1e7, "amount": 1e8, "float_shares": 4e8,
                      "is_st": False}, index=idx)
    f.loc[idx[-2], "volume"] = 1.5e7
    return f


def test_prior_volume_and_next_session_filename():
    f = frame()
    mask = signal_mask(f, "600000.SH")
    assert mask.iloc[-2]
    # Including today would dilute the ratio below 1.5.
    assert f.volume.iloc[-2] / f.volume.iloc[-21:-1].mean() < 1.5
    t = f.index[-1].strftime("%Y%m%d")
    assert scan_frames({"600000.SH": f}, t, t) == {t: ["600000.SH"]}
    assert not scan_frames({"600000.SH": f.iloc[:-1]}, t, t)


@pytest.mark.parametrize("column,value", [("is_st", True), ("float_shares", 1e8),
                                           ("amount", 1), ("open", 11), ("volume", 1e7)])
def test_prefilters_fail_closed(column, value):
    f = frame()
    f[column] = value
    assert not signal_mask(f, "600000.SH").iloc[-2]


def test_board_limit_and_chip_default_off(monkeypatch):
    f = frame()
    f.loc[f.index[-2], ["close", "high"]] = [11.1, 11.11]
    assert not signal_mask(f, "600000.SH").iloc[-2]
    assert signal_mask(f, "300001.SZ").iloc[-2]
    monkeypatch.setattr("scripts.data.export_beidou_pool.chip_single_peak", lambda *a: False)
    assert signal_mask(frame(), "600000.SH").iloc[-2]
    assert not signal_mask(frame(), "600000.SH", chip=True).any()


def test_float_history_backward_only():
    f = frame()
    h = pd.DataFrame({"stock_code": ["600000.SH"] * 2,
                      "date": [f.index[-3], f.index[-1]], "FloatVolume": [4e8, 9e8]})
    result = attach_float_history(f.drop(columns="float_shares"), h, "600000.SH")
    assert pd.isna(result.float_shares.iloc[-4])
    assert result.float_shares.iloc[-2] == 4e8
    assert result.float_shares.iloc[-1] == 9e8


def test_explicit_destination_and_stock_pool_refusal():
    with pytest.raises(SystemExit):
        main(["--start", "20260101", "--end", "20260201"])
    with pytest.raises(SystemExit, match="refusing stock_pool"):
        main(["--start", "20260101", "--end", "20260201", "--pool-dir", "stock_pool"])


def test_exporter_synthetic_lake_smoke(tmp_path, monkeypatch):
    from oskh_data.symbol_format import to_partition_key
    import scripts.data.export_beidou_pool as exporter
    f = frame().drop(columns=["float_shares", "is_st"])
    f["time"] = f.index.as_unit("ms").asi8
    lake = tmp_path / "lake"
    root = lake / "daily" / "dividend_type=none"
    partition = root / f"symbol={to_partition_key('600000.SH')}"
    partition.mkdir(parents=True)
    f.to_parquet(partition / "data.parquet", index=False)
    pd.DataFrame({"stock_code": ["600000.SH"], "date": [f.index[0]],
                  "FloatVolume": [4e8]}).to_parquet(lake / "float_shares_history.parquet")
    vendor = lake / "vendor_wind_st_status"
    vendor.mkdir()
    pd.DataFrame({"trade_date": [f.index[0]], "code": ["600000"], "is_st": [False]}).to_parquet(vendor / "st_daily.parquet")
    monkeypatch.setattr(exporter, "resolve_period_root", lambda _: lake / "daily")
    monkeypatch.setattr(exporter, "resolve_parquet_container", lambda: lake)
    out = tmp_path / "exports"
    t = f.index[-1].strftime("%Y%m%d")
    assert exporter.main(["--start", t, "--end", t, "--pool-dir", str(out)]) == 0
    assert (out / f"{t}.csv").read_bytes() == b"600000\n"
    (lake / "float_shares_history.parquet").unlink()
    with pytest.raises(FileNotFoundError):
        exporter.main(["--start", t, "--end", t, "--pool-dir", str(out)])
