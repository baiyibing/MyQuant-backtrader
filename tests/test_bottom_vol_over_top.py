# -*- coding: utf-8 -*-
"""底量超顶量：无未来函数、顶底次序、主板过滤。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.research.bottom_vol_over_top import (
    MA_BARS,
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
    n: int = 360,
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
    # Default geometry stands above MA5(T): the prior four closes sit just under today's close.
    ma_start = max(0, t - (MA_BARS - 1))
    close[ma_start:t] = close_at_t * 0.98
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
    frame, day = _signal_frame(top_ago=20, bottom_ago=10)
    assert evaluate_at(frame, day, code="600000.SH", top_lead=10) is None


def test_rejects_close_not_above_ma5():
    frame, day = _signal_frame(close_at_t=5.2)
    t = frame.index.get_loc(day)
    frame.iloc[t - 4 : t, frame.columns.get_loc("close")] = 8.0
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
    assert evaluate_at(frame, day, code="600000.SH", turnover_check=True) is not None
    shares = pd.Series(60000.0, index=frame.index)
    # Bottom 8000/60000 >= 10%, but top 1000/60000 < 2%.
    assert evaluate_at(frame, day, code="600000.SH", float_shares=shares) is not None
    assert evaluate_at(
        frame, day, code="600000.SH", float_shares=shares, turnover_check=True
    ) is None


@pytest.mark.parametrize("shares_value", [60000.0, 1e9, np.nan, 0.0, -1.0])
def test_turnover_check_library_and_cli(shares_value, monkeypatch, tmp_path):
    from scripts.data import export_strategy9_pool as exporter

    frame, day = _signal_frame()
    frame["float_shares"] = 60000.0
    # A missing/non-positive value anywhere in either window skips the check.
    frame.loc[day - pd.tseries.offsets.BDay(10), "float_shares"] = shares_value
    ymd = day.strftime("%Y%m%d")
    frames = {"600000.SH": frame}
    rejects = np.isfinite(shares_value) and shares_value > 0
    for enabled in (False, True):
        hit = not (enabled and rejects)
        assert (evaluate_at(frame, day, code="600000.SH", turnover_check=enabled) is not None) is hit
        assert bool(scan_symbol(frame, ymd, ymd, code="600000.SH", turnover_check=enabled)) is hit
        assert bool(scan_ohlcv(frames, ymd, ymd, turnover_check=enabled)) is hit
        assert bool(exporter.event_study_rows(frames, ymd, ymd, turnover_check=enabled)) is hit
        monkeypatch.setattr(exporter, "resolve_period_root", lambda _: tmp_path)
        monkeypatch.setattr(exporter, "load_daily_ohlcv", lambda *a, **kw: frames)
        out = tmp_path / str(enabled)
        args = ["--start", ymd, "--end", ymd, "--codes", "600000",
                "--out-dir", str(out), "--event-study"]
        if enabled:
            args.append("--turnover-check")
        assert export_main(args) == 0
        assert (out / f"{ymd}.csv").exists() is hit
        assert bool(len(pd.read_csv(out / "event_study.csv"))) is hit


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


def test_export_help_states_live_buy_defaults(capsys):
    with pytest.raises(SystemExit) as exc:
        export_main(["--help"])
    assert exc.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "--vol-ratio {1.2,1.5,2}" in help_text
    assert "times this ratio (default: 2)" in help_text
    assert "--top-lead {10,20,30,40}" in help_text
    assert "this many trading bars (default: 40)" in help_text


@pytest.mark.parametrize("bottom_low,passes", [(9.0, True), (9.0001, False)])
def test_fixed_price_drop_boundary(bottom_low, passes):
    # HHV 15 and LLV 9 preserve the existing top/bottom geometry.
    frame, day = _signal_frame(top_high=15.0, bottom_low=bottom_low, close_at_t=9.4)
    assert (evaluate_at(frame, day, code="600000.SH") is not None) is passes


@pytest.mark.parametrize("bottom_vol,passes", [(1600.0, False), (2000.0, False), (2001.0, True)])
def test_omitted_volume_ratio_defaults_to_two(bottom_vol, passes, monkeypatch, tmp_path):
    from scripts.data import export_strategy9_pool as exporter

    frame, day = _signal_frame(bottom_vol=bottom_vol)
    ymd = day.strftime("%Y%m%d")
    assert evaluate_at(frame, day, code="600000.SH", r_min=1.5) is not None
    assert (evaluate_at(frame, day, code="600000.SH") is not None) is passes
    assert bool(scan_symbol(frame, ymd, ymd, code="600000.SH")) is passes
    assert bool(scan_ohlcv({"600000.SH": frame}, ymd, ymd)) is passes
    assert bool(exporter.event_study_rows({"600000.SH": frame}, ymd, ymd)) is passes
    monkeypatch.setattr(exporter, "resolve_period_root", lambda _: tmp_path)
    monkeypatch.setattr(exporter, "load_daily_ohlcv", lambda *a, **kw: {"600000.SH": frame})
    out = tmp_path / "pool"
    assert export_main(["--start", ymd, "--end", ymd, "--codes", "600000",
                        "--out-dir", str(out), "--event-study"]) == 0
    assert (out / f"{ymd}.csv").exists() is passes
    assert bool(len(pd.read_csv(out / "event_study.csv"))) is passes


@pytest.mark.parametrize("lead", [10, 20, 30, 40])
@pytest.mark.parametrize("extra,passes", [(0, False), (1, True)])
def test_top_lead_strict_boundaries_and_cli(lead, extra, passes, monkeypatch, tmp_path):
    from scripts.data import export_strategy9_pool as exporter

    frame, day = _signal_frame(top_ago=10 + lead + extra)
    ymd = day.strftime("%Y%m%d")
    frames = {"600000.SH": frame}
    sig = evaluate_at(frame, day, code="600000.SH", top_lead=lead)
    assert (sig is not None) is passes
    if sig is not None:
        assert (sig.top_ago, sig.bottom_ago) == (10 + lead + extra, 10)
    assert bool(scan_symbol(frame, ymd, ymd, code="600000.SH", top_lead=lead)) is passes
    assert bool(scan_ohlcv(frames, ymd, ymd, top_lead=lead)) is passes
    assert bool(exporter.event_study_rows(frames, ymd, ymd, top_lead=lead)) is passes
    monkeypatch.setattr(exporter, "resolve_period_root", lambda _: tmp_path)
    monkeypatch.setattr(exporter, "load_daily_ohlcv", lambda *a, **kw: frames)
    out = tmp_path / "pool"
    assert export_main([
        "--start", ymd, "--end", ymd, "--codes", "600000",
        "--out-dir", str(out), "--top-lead", str(lead), "--event-study",
    ]) == 0
    assert (out / f"{ymd}.csv").exists() is passes
    assert bool(len(pd.read_csv(out / "event_study.csv"))) is passes


@pytest.mark.parametrize("gap,passes", [(21, False), (40, False), (41, True)])
def test_omitted_top_lead_defaults_to_forty(gap, passes, monkeypatch, tmp_path):
    from scripts.data import export_strategy9_pool as exporter

    frame, day = _signal_frame(top_ago=10 + gap)
    ymd = day.strftime("%Y%m%d")
    frames = {"600000.SH": frame}
    assert evaluate_at(frame, day, code="600000.SH", top_lead=10) is not None
    assert (evaluate_at(frame, day, code="600000.SH") is not None) is passes
    assert bool(scan_symbol(frame, ymd, ymd, code="600000.SH")) is passes
    assert bool(scan_ohlcv(frames, ymd, ymd)) is passes
    assert bool(exporter.event_study_rows(frames, ymd, ymd)) is passes
    monkeypatch.setattr(exporter, "resolve_period_root", lambda _: tmp_path)
    monkeypatch.setattr(exporter, "load_daily_ohlcv", lambda *a, **kw: frames)
    out = tmp_path / "pool"
    assert export_main([
        "--start", ymd, "--end", ymd, "--codes", "600000",
        "--out-dir", str(out), "--event-study",
    ]) == 0
    assert (out / f"{ymd}.csv").exists() is passes
    assert bool(len(pd.read_csv(out / "event_study.csv"))) is passes


@pytest.mark.parametrize("lead", [0, 15, 25, 41, 50, -10, "abc", float("nan"), float("inf")])
def test_invalid_top_lead_rejected_before_scanning(lead):
    from scripts.data.export_strategy9_pool import event_study_rows

    with pytest.raises(ValueError, match="top lead"):
        evaluate_at(pd.DataFrame(), "20240102", code="600000.SH", top_lead=lead)
    with pytest.raises(ValueError, match="top lead"):
        scan_symbol(pd.DataFrame(), "20240102", "20240103", code="600000.SH", top_lead=lead)
    with pytest.raises(ValueError, match="top lead"):
        scan_ohlcv({}, "20240102", "20240103", top_lead=lead)
    with pytest.raises(ValueError, match="top lead"):
        event_study_rows({}, "20240102", "20240103", top_lead=lead)
    with pytest.raises(SystemExit):
        export_main(["--start", "20240102", "--end", "20240103", f"--top-lead={lead}"])


@pytest.mark.parametrize("lead", [10, 20, 30, 40])
def test_top_lead_tolerance_returns_canonical_int(lead):
    from backtest.research.bottom_vol_over_top import resolve_top_lead

    for delta in (-5e-10, 0, 5e-10):
        got = resolve_top_lead(lead + delta)
        assert got == lead
        assert type(got) is int
    with pytest.raises(ValueError):
        resolve_top_lead(lead + 2e-9)
