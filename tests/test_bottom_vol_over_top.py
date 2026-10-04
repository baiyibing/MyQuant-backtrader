# -*- coding: utf-8 -*-
"""底量超顶量：无未来函数、顶底次序、主板过滤。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.research.bottom_vol_over_top import (
    CLOSE_CAP,
    evaluate_at,
    forward_close_returns,
    is_main_board_code,
    scan_ohlcv,
    scan_symbol,
)
from backtest.research.csv_pool import is_repo_stock_pool, validate_pool_dir
from scripts.data.export_strategy9_pool import (
    REPO_ROOT,
    main as export_main,
    write_strategy9_pool,
)


def _signal_frame(
    *,
    n: int = 280,
    top_ago: int = 80,
    bottom_ago: int = 10,
    top_high: float = 20.0,
    bottom_low: float = 5.0,
    top_vol: float = 1000.0,
    bottom_vol: float = 8000.0,
    base_vol: float = 800.0,
    close_at_t: float = 5.2,
    extra_future: int = 5,
    future_vol: float = 1e9,
    new_low_today: bool = False,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    idx = pd.bdate_range("2024-01-02", periods=n + extra_future)
    high = np.full(n + extra_future, 10.2, dtype=np.float64)
    low = np.full(n + extra_future, 9.8, dtype=np.float64)
    close = np.full(n + extra_future, 10.0, dtype=np.float64)
    open_ = np.full(n + extra_future, 10.0, dtype=np.float64)
    volume = np.full(n + extra_future, base_vol, dtype=np.float64)
    t = n - 1
    top_i = t - top_ago
    bot_i = t - bottom_ago
    high[top_i] = top_high
    low[bot_i] = bottom_low
    if bot_i + 1 <= t:
        low[bot_i + 1 : t + 1] = bottom_low + 0.3
    if new_low_today:
        low[t] = bottom_low - 0.2
    close[t] = close_at_t
    open_[t] = close_at_t
    high[t] = max(close_at_t + 0.1, float(low[t]) + 0.1)
    volume[max(0, top_i - 3) : top_i + 4] = top_vol
    volume[max(0, bot_i - 3) : bot_i + 4] = bottom_vol
    if extra_future:
        volume[t + 1 : t + 4] = future_vol
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )
    return frame, idx[t]


def test_is_main_board_includes_sme_excludes_chinext_and_bj():
    assert is_main_board_code("600000.SH") is True
    assert is_main_board_code("000001.SZ") is True
    assert is_main_board_code("002001.SZ") is True
    assert is_main_board_code("300001.SZ") is False
    assert is_main_board_code("688001.SH") is False
    assert is_main_board_code("920001.BJ") is False


def test_valid_geometry_fires_on_main_board():
    frame, day = _signal_frame()
    sig = evaluate_at(frame, day, code="600000.SH")
    assert sig is not None
    assert sig.ymd == day.strftime("%Y%m%d")
    assert sig.top_ago == 80
    assert sig.bottom_ago == 10
    assert sig.ratio > 1.2


def test_future_volume_after_t_does_not_create_a_hit():
    frame, day = _signal_frame(bottom_ago=1, bottom_vol=1000.0, top_vol=5000.0)
    assert evaluate_at(frame, day, code="600000.SH") is None
    # Unclipped [center-3, center+3] would include T+1..T+3 at 1e9.


def test_does_not_fire_on_the_bottom_bar():
    frame, day = _signal_frame(bottom_ago=0, close_at_t=5.2)
    assert evaluate_at(frame, day, code="600000.SH") is None


def test_top_must_lead_bottom_by_more_than_ten_bars():
    frame, day = _signal_frame(top_ago=15, bottom_ago=10)
    assert evaluate_at(frame, day, code="600000.SH") is None


def test_rejects_close_above_bottom_cap():
    frame, day = _signal_frame(close_at_t=5.0 * CLOSE_CAP + 0.05)
    assert evaluate_at(frame, day, code="600000.SH") is None


def test_rejects_new_low_after_bottom():
    frame, day = _signal_frame(new_low_today=True)
    assert evaluate_at(frame, day, code="600000.SH") is None


def test_rejects_chinext_and_st_name():
    frame, day = _signal_frame()
    assert evaluate_at(frame, day, code="300001.SZ") is None
    assert evaluate_at(frame, day, code="600000.SH", name="*ST 示例") is None


def test_rejects_short_listing():
    frame, day = _signal_frame(n=200)
    assert evaluate_at(frame, day, code="600000.SH") is None


def test_tiny_top_turnover_rejected_only_when_float_is_complete():
    frame, day = _signal_frame()
    assert evaluate_at(frame, day, code="600000.SH") is not None
    shares = pd.Series(1.0e9, index=frame.index)
    # bottom window 8000/1e9 = 0.0008 < 10% → reject
    assert evaluate_at(frame, day, code="600000.SH", float_shares=shares) is None
    # hole in the bottom window → skip enhancement, keep base hit
    loc = frame.index.get_loc(day)
    t = int(loc.stop - 1) if isinstance(loc, slice) else int(loc)
    shares.iloc[t - 10] = np.nan
    assert evaluate_at(frame, day, code="600000.SH", float_shares=shares) is not None


def test_scan_skips_empty_days_and_writes_contract_bytes(tmp_path):
    frame, day = _signal_frame()
    ymd = day.strftime("%Y%m%d")
    quiet = day - pd.tseries.offsets.BDay(3)
    days = scan_ohlcv({"600000.SH": frame}, "20240102", ymd)
    assert ymd in days
    assert "600000.SH" in days[ymd]
    assert quiet.strftime("%Y%m%d") not in days
    written = write_strategy9_pool(days, tmp_path / "s9")
    dest = tmp_path / "s9" / f"{ymd}.csv"
    assert dest in written
    raw = dest.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.decode("utf-8").splitlines() == ["600000"]
    assert validate_pool_dir(tmp_path / "s9") == []


def test_write_refuses_stock_pool(tmp_path):
    stock = tmp_path / "stock_pool"
    stock.mkdir()
    with pytest.raises(SystemExit, match="stock_pool"):
        write_strategy9_pool({"20260303": ["600000.SH"]}, stock, repo=tmp_path)
    assert is_repo_stock_pool(stock / "nested", repo=tmp_path)
    assert not is_repo_stock_pool(tmp_path / "exports", repo=tmp_path)


def test_export_cli_refuses_repo_stock_pool():
    with pytest.raises(SystemExit, match="stock_pool"):
        export_main(
            [
                "--start",
                "20260303",
                "--end",
                "20260323",
                "--out-dir",
                str(REPO_ROOT / "stock_pool"),
            ]
        )


def test_forward_returns_are_measurement_only():
    close = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    got = forward_close_returns(close, 0, horizons=(1, 2, 5))
    assert got[1] == pytest.approx(0.10)
    assert got[2] == pytest.approx(0.20)
    assert got[5] is None


def test_scan_symbol_returns_only_hits():
    frame, day = _signal_frame()
    hits = scan_symbol(
        frame, day.strftime("%Y%m%d"), day.strftime("%Y%m%d"), code="600000.SH"
    )
    assert len(hits) == 1
    assert hits[0].ymd == day.strftime("%Y%m%d")


@pytest.mark.parametrize("ratio,next_ratio", [(1.2, 1.5), (1.5, 2.0), (2.0, None)])
def test_volume_ratio_thresholds_and_cli(ratio, next_ratio, monkeypatch, tmp_path):
    from scripts.data import export_strategy9_pool as exporter

    frame, day = _signal_frame(bottom_vol=1000.0 * (ratio + 0.001))
    ymd = day.strftime("%Y%m%d")
    assert evaluate_at(frame, day, code="600000.SH", r_min=ratio) is not None
    assert len(scan_symbol(frame, ymd, ymd, code="600000.SH", r_min=ratio)) == 1
    assert scan_ohlcv({"600000.SH": frame}, ymd, ymd, r_min=ratio) == {
        ymd: ["600000.SH"]
    }
    if next_ratio is not None:
        assert evaluate_at(frame, day, code="600000.SH", r_min=next_ratio) is None
        assert scan_ohlcv({"600000.SH": frame}, ymd, ymd, r_min=next_ratio) == {}
    equal_frame, equal_day = _signal_frame(bottom_vol=1000.0 * ratio)
    assert evaluate_at(equal_frame, equal_day, code="600000.SH", r_min=ratio) is None
    monkeypatch.setattr(exporter, "resolve_period_root", lambda _: tmp_path)
    monkeypatch.setattr(exporter, "load_daily_ohlcv", lambda *a, **kw: {"600000.SH": frame})
    out = tmp_path / "pool"
    assert export_main([
        "--start", ymd, "--end", ymd, "--codes", "600000",
        "--out-dir", str(out), "--vol-ratio", str(ratio), "--event-study",
    ]) == 0
    assert (out / f"{ymd}.csv").read_text() == "600000\n"
    assert len(pd.read_csv(out / "event_study.csv")) == 1


@pytest.mark.parametrize("ratio", [1, 1.3, 1.8, 3, -1, "abc", float("nan"), float("inf")])
def test_invalid_volume_ratio_rejected_before_scanning(ratio):
    frame, day = _signal_frame()
    with pytest.raises(ValueError, match="volume ratio"):
        evaluate_at(frame, day, code="600000.SH", r_min=ratio)
    with pytest.raises(ValueError, match="volume ratio"):
        scan_symbol(frame.iloc[:0], "20240102", "20240103", code="600000.SH", r_min=ratio)
    with pytest.raises(ValueError, match="volume ratio"):
        scan_ohlcv({}, "20240102", "20240103", r_min=ratio)
    with pytest.raises(SystemExit):
        export_main(["--start", "20240102", "--end", "20240103", f"--vol-ratio={ratio}"])


@pytest.mark.parametrize("ratio", [1.2, 1.5, 2.0])
def test_volume_ratio_tolerance_returns_canonical_float(ratio):
    from backtest.research.bottom_vol_over_top import resolve_vol_ratio

    assert resolve_vol_ratio(ratio + 5e-10) == ratio
    assert resolve_vol_ratio(ratio - 5e-10) == ratio
    with pytest.raises(ValueError):
        resolve_vol_ratio(ratio + 2e-9)


@pytest.mark.parametrize("bottom_low,passes", [(9.0, True), (9.0001, False)])
def test_fixed_price_drop_boundary(bottom_low, passes):
    # HHV 15 and LLV 9 preserve the existing top/bottom geometry.
    frame, day = _signal_frame(top_high=15.0, bottom_low=bottom_low, close_at_t=9.4)
    assert (evaluate_at(frame, day, code="600000.SH") is not None) is passes


def test_omitted_volume_ratio_defaults_to_one_point_five(monkeypatch, tmp_path):
    from scripts.data import export_strategy9_pool as exporter

    frame, day = _signal_frame(bottom_vol=1300.0)
    ymd = day.strftime("%Y%m%d")
    assert evaluate_at(frame, day, code="600000.SH", r_min=1.2) is not None
    assert evaluate_at(frame, day, code="600000.SH") is None
    assert scan_symbol(frame, ymd, ymd, code="600000.SH") == []
    assert scan_ohlcv({"600000.SH": frame}, ymd, ymd) == {}
    monkeypatch.setattr(exporter, "resolve_period_root", lambda _: tmp_path)
    monkeypatch.setattr(exporter, "load_daily_ohlcv", lambda *a, **kw: {"600000.SH": frame})
    out = tmp_path / "pool"
    assert export_main(["--start", ymd, "--end", ymd, "--codes", "600000", "--out-dir", str(out)]) == 0
    assert not (out / f"{ymd}.csv").exists()
