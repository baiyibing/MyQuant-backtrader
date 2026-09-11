# -*- coding: utf-8 -*-
"""策略 8 走共享 csv_minute_backtest 引擎的分钟扫描 / 追买单测。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_minute_backtest as sim
from backtest.research.strategy8_rules import take_profit_reason


def test_scan_gap_open_stop_15pct():
    o = np.array([8.40, 8.50])
    h = np.array([8.50, 8.55])
    c = np.array([8.45, 8.50])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.15,
        profit_base=0.20,
        trail_ratio=0.0,
        take_profit=take_profit_reason,
    )
    assert idx == 0
    assert reason == "stop_loss:gap_open"
    assert px == pytest.approx(8.40)


def test_scan_no_sell_when_t0():
    o = np.array([8.40])
    h = np.array([13.20])
    c = np.array([8.30])
    idx, _, reason, peak, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=0,
        can_sell=False,
        stop_pct=0.15,
        profit_base=0.20,
        trail_ratio=0.0,
        take_profit=take_profit_reason,
    )
    assert idx == -1
    assert reason == ""
    assert peak == pytest.approx(10.0)


def test_scan_band_tp_on_close():
    o = np.array([12.80, 12.00])
    h = np.array([13.00, 12.10])
    c = np.array([12.90, 11.989])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.15,
        profit_base=0.20,
        trail_ratio=0.0,
        take_profit=take_profit_reason,
    )
    assert idx == 1
    assert reason == "trail:band:20"
    assert px == pytest.approx(11.989)


def test_scan_peak_dd():
    o = np.array([29.0, 24.0])
    h = np.array([30.0, 24.2])
    c = np.array([29.5, 23.90])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.15,
        profit_base=0.20,
        trail_ratio=0.0,
        take_profit=take_profit_reason,
    )
    assert idx == 1
    assert reason == "trail:peak_dd"
    assert px == pytest.approx(23.90)


def _day(date: str, rows: list[tuple]) -> pd.DataFrame:
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


def test_simulate_limit_up_chases_when_945_above_open():
    dates = ["2025-11-03", "2025-11-04"]
    m = _day(
        "2025-11-03", [(930, 10.5, 11.0, 10.5, 10.8), (1455, 11.0, 11.0, 11.0, 11.0)]
    )
    m2 = _day(
        "2025-11-04",
        [
            (930, 11.00, 11.05, 10.98, 11.02),
            (945, 11.08, 11.12, 11.06, 11.10),
            (1455, 11.10, 11.20, 11.00, 11.15),
        ],
    )
    minute = {"600000.SH": pd.concat([m, m2])}
    daily = {"600000.SH": _daily(dates, [11.0, 11.15])}
    st = sim.simulate(
        minute,
        daily,
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        strategy="version8",
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_buy"] == 1
    buy = [t for t in st.trades if t["side"] == "BUY"][0]
    assert buy["reason"] == "chase:T+1"
    assert buy["date"] == "20251104"
    assert buy["price"] == pytest.approx(11.10)


def test_simulate_limit_up_abandons_when_945_below_open():
    dates = ["2025-11-03", "2025-11-04"]
    m = _day(
        "2025-11-03", [(930, 10.5, 11.0, 10.5, 10.8), (1455, 11.0, 11.0, 11.0, 11.0)]
    )
    m2 = _day(
        "2025-11-04",
        [
            (930, 11.20, 11.20, 11.10, 11.15),
            (945, 11.10, 11.12, 11.05, 11.08),
            (1455, 11.10, 11.20, 11.00, 11.12),
        ],
    )
    minute = {"600000.SH": pd.concat([m, m2])}
    daily = {"600000.SH": _daily(dates, [11.0, 11.12])}
    st = sim.simulate(
        minute,
        daily,
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        strategy="version8",
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_abandon"] == 1
    assert st.stats["buys"] == 0
