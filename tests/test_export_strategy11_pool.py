"""Data-free contract-day, prefix-weekly and Rust failure boundary pins."""

from datetime import date
from math import isnan
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backtest.research import ma_infra as ma
from backtest.research.csv_pool import validate_pool_dir, load_pool_day_map
from oskh_factors.bridge.turnover_resist import circulating_capital_asof
from scripts.data import export_strategy11_pool as exporter

CODE = "600001.SH"


def _frame(n=220):
    idx = pd.bdate_range(end="2024-02-09", periods=n)
    close = np.full(n, 10.0)
    close[-2] = 11
    return pd.DataFrame({"open": 10.0, "high": close + 0.1, "low": 9.0,
                         "close": close, "volume": 1000.0}, index=idx)


def _history(code=CODE):
    return pd.DataFrame({"stock_code": [code], "m_timetag": ["20220101"],
                         "circulating_capital": [1e8]})


def _rust(close, high, low, volume, shares, *, window, start_i, step):
    assert window == 200 and start_i == 199 and step == 0.01
    assert len({len(x) for x in (close, high, low, volume, shares)}) == 1
    out = np.full(len(close), np.nan)
    for i in range(window - 1, len(close)):
        # Emulate documented window-local invalid-day propagation, not CYQ math.
        arrays = np.array([close, high, low, volume, shares])[:, i-window+1:i+1]
        if np.isfinite(arrays).all() and (arrays[4] > 0).all():
            out[i] = 0.8
    return out


def test_weekly_default_unchanged_and_explicit_optin_truncate_then_call():
    dates = [date.fromisoformat(x) for x in (
        "2023-12-28", "2023-12-29", "2024-01-02", "2024-01-04", "2024-01-15", "2024-01-17")]
    closes = [10, 12, 20, 22, 30, 32]
    assert ma.weekly_sma_series(dates, closes, 2) == [None, None, None, 17, 17, 27]
    actual = ma.weekly_sma_series(dates, closes, 2, prefix_equivalent=True)
    assert actual == [None, None, 16, 17, 26, 27]
    assert actual == [ma.weekly_sma_series(dates[:i+1], closes[:i+1], 2)[-1]
                      for i in range(len(dates))]


@pytest.mark.parametrize("n", [0, 1, 2, 20])
def test_weekly_prefix_nan_halt_and_future_perturbation(n):
    dates = pd.bdate_range("2023-08-01", periods=150).date.tolist()
    closes = [float((i * 19) % 31) for i in range(len(dates))]
    closes[5:15] = [float("nan")] * 10
    actual = ma.weekly_sma_series(dates, closes, n, prefix_equivalent=True)
    for i in range(len(dates)):
        expected = ma.weekly_sma_series(dates[:i+1], closes[:i+1], n)[-1]
        assert actual[i] == pytest.approx(expected) if expected is not None else actual[i] is None
    changed = closes[:80] + [100000] * 70
    assert ma.weekly_sma_series(dates, changed, n, prefix_equivalent=True)[:80] == actual[:80]


def test_asof_shares_change_is_daily_and_never_snapshot(monkeypatch):
    history = pd.DataFrame({"stock_code": [CODE, CODE, CODE],
                            "m_timetag": ["20240102", "20240105", "20240201"],
                            "circulating_capital": [100, 200, 999]})
    got = circulating_capital_asof(CODE, ["20240101", "20240104", "20240105"], history=history)
    assert isnan(got[0]) and got[1:].tolist() == [100, 200]
    with pytest.raises(ValueError, match="date=None"):
        circulating_capital_asof(CODE, None, history=history)
    monkeypatch.setattr("common.infra.data_root.resolve_source_parquet", lambda _: "/missing/asof.parquet")
    with pytest.raises(FileNotFoundError):
        circulating_capital_asof(CODE, ["20240101"])


@pytest.mark.parametrize("target,reason", [
    ("20240108", ""), ("20240109", ""), ("20240110", "skip_buy(stale)"),
])
def test_contract_day_strictly_after_d_four_calendar_day_boundary(target, reason):
    original = pd.Timestamp("20240105")
    actual, reject = exporter.contract_day(original, pd.to_datetime(["20240104", "20240105", target]),
                                           observed_through="20240120")
    assert actual == pd.Timestamp(target) and actual > original
    assert reject == reason


def test_tail_stale_is_aged_from_original_signal_not_export_day():
    days = pd.to_datetime(["20240105"])
    assert exporter.contract_day(days[0], days, observed_through="20240109") == (None, "awaiting_contract_bar")
    assert exporter.contract_day(days[0], days, observed_through="20240110") == (None, "skip_buy(stale)")


def test_exporter_calls_weekly_optin_and_writes_t_not_d(monkeypatch):
    seen = []
    original = ma.weekly_sma_series

    def weekly(*args, **kwargs):
        seen.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(ma, "weekly_sma_series", weekly)
    frame = _frame()
    result = exporter.ScanResult()
    assert exporter.scan_symbol(CODE, frame, _history(), "20240101", "20240209", _rust, result)
    assert dict(result.days) == {"20240209": [CODE]}
    assert seen == [{"prefix_equivalent": True}]
    # T's OHLC/shares cannot influence the row for T; D's can.
    changed = frame.copy()
    changed.loc[changed.index[-1], ["open", "high", "low", "close"]] = [30, 31, 29, 30]
    second = exporter.ScanResult()
    exporter.scan_symbol(CODE, changed, _history(), "20240101", "20240209", _rust, second)
    assert second.days == result.days
    changed.loc[changed.index[-2], "close"] = 10
    third = exporter.ScanResult()
    exporter.scan_symbol(CODE, changed, _history(), "20240101", "20240209", _rust, third)
    assert not third.days


def test_stale_rejection_preserves_original_d_and_no_pool_row():
    frame = _frame()
    frame.index = frame.index[:-1].append(pd.DatetimeIndex(["20240220"]))
    result = exporter.ScanResult()
    exporter.scan_symbol(CODE, frame, _history(), "20240101", "20240220", _rust, result)
    assert not result.days
    row = next(row for row in result.rejected if row["reason"] == "skip_buy(stale)")
    assert row["date"] == row["original_signal_day"] == "20240208"
    assert row["contract_day"] == "20240220"
    assert result.counts["skip_buy(stale)"] == 1


def test_zero_volume_does_not_supply_contract_bar_and_pre_window_edge_masked():
    frame = _frame()
    frame.iloc[-1, frame.columns.get_loc("volume")] = 0
    result = exporter.ScanResult()
    exporter.scan_symbol(CODE, frame, _history(), "20240101", "20240220", _rust, result)
    assert not result.days and result.counts["skip_zero_volume"] == 1
    assert result.counts["skip_buy(stale)"] == 1
    result = exporter.ScanResult()
    exporter.scan_symbol(CODE, _frame(), _history(), "20240209", "20240209", _rust, result)
    assert not result.days and result.counts["signals"] == 0


def test_grid_guard_excludes_only_oversized_output_windows_before_rust():
    frame = _frame(430)
    frame.iloc[210, frame.columns.get_loc("high")] = 3000
    calls = []

    def rust(*args, **kwargs):
        highs, lows = pd.Series(args[1]), pd.Series(args[2])
        assert ((highs.rolling(200).max() - lows.rolling(200).min()) / .01).dropna().max() <= 250000
        calls.append(len(args[0]))
        return _rust(*args, **kwargs)

    edges, cyqk, grid, finite = exporter.compute_signals(frame, np.full(len(frame), 1e8), rust)
    assert grid[210:410].all() and not grid[410:].any()
    assert np.isnan(cyqk[210:410]).all() and np.isfinite(cyqk[410:]).all()
    assert len(calls) == 2
    assert not any(edges[210:411])  # bad previous window cannot create an edge


def test_grid_threshold_equality_is_allowed():
    frame = _frame(200)
    frame["high"] = frame["low"] + 250000 * .01
    _, cyqk, grid, _ = exporter.compute_signals(frame, np.full(200, 1e8), _rust)
    assert not grid.any() and np.isfinite(cyqk[-1])


def test_window_nan_and_symbol_valueerror_have_distinct_counters():
    frame = _frame()
    shares = np.full(len(frame), 1e8)
    shares[2] = np.nan
    _, cyqk, _, _ = exporter.compute_signals(frame, shares, _rust)
    assert np.isnan(cyqk[199:202]).all() and np.isfinite(cyqk[202:]).all()
    broken_history = _history()
    broken_history["circulating_capital"] = 0
    result = exporter.ScanResult()
    exporter.scan_symbol(CODE, frame, broken_history, "20240101", "20240209", _rust, result)
    assert result.counts["skip_cyqk_nan"] > 0 and result.counts["skip_cyqk_error"] == 0

    def fail(*args, **kwargs):
        raise ValueError("length mismatch")

    result = exporter.ScanResult()
    assert not exporter.scan_symbol(CODE, frame, _history(), "20240101", "20240209", fail, result)
    assert result.counts["skip_cyqk_error"] == 1 and not result.days
    assert "length mismatch" in result.rejected[0]["detail"]
    assert exporter.scan_symbol(CODE, frame, _history(), "20240101", "20240209", _rust, result)
    assert result.days  # one bad symbol does not abort the scan


def test_boards_st_filter_and_archived_seed_rng():
    codes = [CODE, "000001.SZ", "300001.SZ", "688001.SH", "830001.BJ"]
    names = dict.fromkeys(codes, "ordinary")
    names[CODE] = "*ST sample"
    sample = exporter.candidates_by_board(codes, codes, names=names)
    universe = exporter.candidates_by_board(codes, codes, sample=False, names=names)
    assert sample["sh_main"] == [CODE] and universe["sh_main"] == []
    assert sum(len(g) for g in sample.values()) == 3
    with pytest.raises(ValueError, match="requires names"):
        exporter.candidates_by_board(codes, codes, sample=False)
    assert sample == exporter.candidates_by_board(reversed(codes), codes)


def test_output_pool_contract_rejects_stock_pool_and_audit_is_separate(tmp_path):
    result = exporter.ScanResult()
    result.days["20240109"] = [CODE, "000001.SZ"]
    result.reject(CODE, "20240105", "skip_buy(stale)")
    with pytest.raises(SystemExit, match="stock_pool"):
        exporter.write_strategy11_pool(result, tmp_path / "stock_pool", {}, repo=tmp_path)
    pool = exporter.write_strategy11_pool(result, tmp_path / "out", {"pyd_file": "fixture.pyd"}, repo=tmp_path)
    assert validate_pool_dir(pool) == []
    assert (pool / "20240109.csv").read_bytes() == b"000001\n600001\n"
    assert load_pool_day_map(pool, "20240101", "20240131")["20240109"] == ["000001.SZ", CODE]
    for path in (pool / "20240109.csv", pool.parent / "rejected.csv", pool.parent / "manifest.json"):
        raw = path.read_bytes()
        assert b"\0" not in raw and b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    with pytest.raises(FileExistsError):
        exporter.write_strategy11_pool(result, pool.parent, {})


def test_front_loader_and_cli_manifest(tmp_path, monkeypatch):
    root = tmp_path / "stock" / "period=1d" / "dividend_type=front"
    path = root / "symbol=600001_SH" / "data.parquet"
    path.parent.mkdir(parents=True)
    frame = _frame()
    data = frame.copy()
    data["time"] = frame.index.as_unit("ms").asi8
    data.to_parquet(path, index=False)
    floats = pd.DataFrame({"stock_code": [CODE], "name": ["ordinary"]})
    floats.to_parquet(tmp_path / "float_shares.parquet")
    _history().to_parquet(tmp_path / "free_float_shares.parquet")
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(tmp_path))
    monkeypatch.delenv("OSKH_PERIOD_1D_ROOT", raising=False)
    monkeypatch.setitem(exporter.sys.modules, "turnover_resist", SimpleNamespace(
        compute_cyqk_series=_rust, __file__="fixture.pyd", __version__="test"))
    dest = tmp_path / "export"
    assert exporter.main(["--universe", "--end", "20240209", "--out-dir", str(dest)]) == 0
    import json
    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["adjust_type"] == "front" and manifest["pyd_file"] == "fixture.pyd"
    assert manifest["weekly_prefix_equivalent"] is True
    assert manifest["counts"]["pool_rows"] == 1
    assert (dest / "pool" / "20240209.csv").exists()
