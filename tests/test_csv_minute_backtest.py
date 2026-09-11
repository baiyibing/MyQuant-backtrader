# -*- coding: utf-8 -*-
"""csv_minute_backtest（策略6 分钟向量化）单元测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_minute_backtest as sim


def test_scan_gap_open_stop():
    o = np.array([9.40, 9.50])
    h = np.array([9.50, 9.55])
    c = np.array([9.45, 9.50])
    idx, px, reason, peak, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
    )
    assert idx == 0
    assert reason == "stop_loss:gap_open"
    assert px == pytest.approx(9.40)


def test_scan_no_sell_when_t0():
    o = np.array([9.40])
    h = np.array([10.20])
    c = np.array([9.35])
    idx, _, reason, peak, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=0,
        can_sell=False,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
    )
    assert idx == -1
    assert reason == ""
    assert peak == pytest.approx(10.0)  # T+0 不更新峰值


def test_scan_t1_trail_on_close():
    # 峰值 10.50（+5%，锚 1% 后超额 4%），T+1 档 50% → 线 +3% → 10.30
    # 09:30 创新高，09:34 才允许止盈（间隔＞2 分钟）
    o = np.array([10.40, 10.40, 10.40, 10.36])
    h = np.array([10.50, 10.50, 10.50, 10.36])
    c = np.array([10.45, 10.45, 10.45, 10.298])
    hm = np.array([570, 571, 572, 574])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
        hm=hm,
    )
    assert idx == 3
    assert reason == "trail:T+1"
    assert px == pytest.approx(10.298)


def test_scan_tp_blocked_within_2_minutes_of_peak():
    o = np.array([10.40, 10.20])
    h = np.array([10.50, 10.20])
    c = np.array([10.45, 10.20])
    hm = np.array([570, 572])  # 间隔 2 分钟，须大于 2
    idx, _, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
        hm=hm,
    )
    assert idx == -1
    assert reason == ""


def test_scan_no_tp_until_peak_above_1pct():
    o = np.array([10.00, 10.00, 10.00, 10.00])
    h = np.array([10.005, 10.005, 10.005, 10.005])
    c = np.array([10.002, 10.002, 10.002, 10.002])
    hm = np.array([570, 571, 572, 575])
    idx, _, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
        hm=hm,
    )
    assert idx == -1
    assert reason == ""


def _day(date: str, rows: list[tuple]) -> pd.DataFrame:
    """rows: (hhmm, o, h, low, c) hhmm like 930 / 1455."""
    idx, opens, highs, lows, closes = [], [], [], [], []
    d = pd.Timestamp(date)
    for hm, oo, hh, ll, cc in rows:
        hour, minute = divmod(int(hm), 100)
        idx.append(d + pd.Timedelta(hours=hour, minutes=minute))
        opens.append(oo)
        highs.append(hh)
        lows.append(ll)
        closes.append(cc)
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=pd.DatetimeIndex(idx),
    ).astype(np.float64)
    return sim._annotate(df)


def _daily(dates: list[str], closes: list[float], prev: float = 10.0) -> pd.DataFrame:
    pre = pd.Timestamp(dates[0]) - pd.Timedelta(days=2)
    idx = pd.DatetimeIndex([pre] + [pd.Timestamp(d) for d in dates])
    px = [prev] + list(closes)
    return pd.DataFrame(
        {"open": px, "high": px, "low": px, "close": px}, index=idx
    ).astype(np.float64)


def test_simulate_limit_up_at_1455_skips_without_requeue():
    # 昨收 10 → 涨停 11；14:55 close=11.0 → 跳过；次日不在池里
    dates = ["2025-11-03", "2025-11-04"]
    m = _day(
        "2025-11-03", [(930, 10.5, 11.0, 10.5, 10.8), (1455, 11.0, 11.0, 11.0, 11.0)]
    )
    m2 = _day(
        "2025-11-04", [(930, 11.0, 11.2, 10.9, 11.1), (1455, 11.1, 11.2, 11.0, 11.2)]
    )
    minute = {"600000.SH": pd.concat([m, m2])}
    daily = {"600000.SH": _daily(dates, [11.0, 11.2])}
    st = sim.simulate(
        minute, daily, {"20251103": ["600000.SH"]}, "20251103", "20251104"
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["buys"] == 0


def test_simulate_skip_when_1455_above_computed_limit():
    # 昨收 3.75，14:55=4.13（交易所涨停 4.13；买价高于误算的 4.12 也必须跳过）
    dates = ["2025-11-03", "2025-11-04"]
    m = _day(
        "2025-11-03",
        [(930, 3.78, 3.80, 3.71, 3.76), (1455, 4.13, 4.13, 4.13, 4.13)],
    )
    m2 = _day(
        "2025-11-04",
        [(930, 4.44, 4.44, 4.44, 4.44), (1455, 4.54, 4.54, 4.54, 4.54)],
    )
    minute = {"000592.SZ": pd.concat([m, m2])}
    daily = {"000592.SZ": _daily(dates, [4.13, 4.54], prev=3.75)}
    st = sim.simulate(
        minute, daily, {"20251103": ["000592.SZ"]}, "20251103", "20251104"
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["buys"] == 0


def test_simulate_buy_at_1455_and_t1_stop_next_open():
    dates = ["2025-11-03", "2025-11-04"]
    m0 = _day(
        "2025-11-03", [(930, 10.0, 10.1, 9.9, 10.0), (1455, 10.0, 10.05, 9.98, 10.0)]
    )
    m1 = _day(
        "2025-11-04", [(930, 9.40, 9.50, 9.30, 9.45), (1455, 9.40, 9.50, 9.30, 9.42)]
    )
    minute = {"600000.SH": pd.concat([m0, m1])}
    daily = {"600000.SH": _daily(dates, [10.0, 9.42])}
    st = sim.simulate(
        minute,
        daily,
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        stop_pct=0.02,
    )
    assert st.stats["buys"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "stop_loss:gap_open"
    assert sell["date"] == "20251104"
    assert sell["price"] == pytest.approx(9.40)


def test_t0_after_buy_high_does_not_set_peak():
    # 14:55 买 10.00，随后 high=10.02；若误记 T+0 峰值，次日开盘 10.00 会 pos_trail。
    dates = ["2025-11-03", "2025-11-04"]
    m0 = _day(
        "2025-11-03",
        [
            (930, 10.0, 10.3, 9.9, 10.0),
            (1455, 10.0, 10.02, 9.99, 10.0),
            (1500, 10.01, 10.02, 10.00, 10.01),
        ],
    )
    m1 = _day(
        "2025-11-04",
        [
            (930, 10.00, 10.00, 10.00, 10.00),
            (931, 10.05, 10.20, 10.04, 10.18),
            (1455, 10.18, 10.20, 10.15, 10.16),
        ],
    )
    minute = {"600000.SH": pd.concat([m0, m1])}
    daily = {"600000.SH": _daily(dates, [10.01, 10.16])}
    st = sim.simulate(
        minute, daily, {"20251103": ["600000.SH"]}, "20251103", "20251104"
    )
    assert st.stats["buys"] == 1
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells == [] or sells[0]["reason"] != "pos_trail"
    assert not any(
        t["date"] == "20251104" and t.get("reason") == "pos_trail" for t in st.trades
    )


def test_minute_cache_roundtrip(tmp_path):
    raw = _day(
        "2025-11-03",
        [
            (930, 10.0, 10.1, 9.9, 10.0),
            (1455, 10.0, 10.05, 9.98, 10.0),
        ],
    )
    path = sim.write_minute_cache(
        {"600000.SH": raw}, "20251103", "20251104", cache_dir=tmp_path
    )
    assert path.is_file()
    got = sim.read_minute_cache(path, {"600000.SH"})
    assert "600000.SH" in got
    pd.testing.assert_series_equal(
        got["600000.SH"]["close"].reset_index(drop=True),
        raw["close"].reset_index(drop=True),
        check_names=False,
    )
    assert list(got["600000.SH"]["hm"]) == list(raw["hm"])
    hit = sim.load_minute_bars(
        {"600000.SH"},
        "20251103",
        "20251104",
        use_cache=True,
        cache_dir=tmp_path,
        workers=1,
    )
    assert "600000.SH" in hit
    assert len(hit["600000.SH"]) == len(raw)


def test_build_day_spans_two_sessions():
    m0 = _day(
        "2025-11-03", [(930, 10.0, 10.1, 9.9, 10.0), (1455, 10.0, 10.05, 9.98, 10.0)]
    )
    m1 = _day(
        "2025-11-04", [(930, 9.40, 9.50, 9.30, 9.45), (1455, 9.40, 9.50, 9.30, 9.42)]
    )
    df = pd.concat([m0, m1])
    spans = sim.build_day_spans(df)
    assert set(spans) == {"20251103", "20251104"}
    d0 = sim._slice_day(df, spans, "20251103")
    d1 = sim._slice_day(df, spans, "20251104")
    assert d0 is not None and len(d0) == 2
    assert d1 is not None and float(d1["close"].iloc[0]) == pytest.approx(9.45)
    assert sim._slice_day(df, spans, "20251105") is None


def test_simulate_uses_day_spans_same_as_loc():
    dates = ["2025-11-03", "2025-11-04"]
    m0 = _day(
        "2025-11-03", [(930, 10.0, 10.1, 9.9, 10.0), (1455, 10.0, 10.05, 9.98, 10.0)]
    )
    m1 = _day(
        "2025-11-04", [(930, 9.40, 9.50, 9.30, 9.45), (1455, 9.40, 9.50, 9.30, 9.42)]
    )
    minute = {"600000.SH": pd.concat([m0, m1])}
    daily = {"600000.SH": _daily(dates, [10.0, 9.42])}
    st = sim.simulate(
        minute,
        daily,
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        stop_pct=0.02,
    )
    assert st.stats["buys"] == 1
    assert st.stats["sell_stop"] == 1
