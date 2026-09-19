# -*- coding: utf-8 -*-
"""策略 8 走共享 csv_minute_backtest 引擎的分钟扫描 / 追买单测。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_minute_backtest as sim
from backtest.research.csv_ledger import chase_explained
from backtest.research.strategy8_rules import STOP_PCT, take_profit_reason


def test_scan_touch_stop_10pct_from_t1():
    o = np.array([9.20, 9.30])
    h = np.array([9.30, 9.40])
    c = np.array([8.99, 9.20])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=STOP_PCT,
        profit_base=0.15,
        trail_ratio=0.0,
        peak_gap_min=0,
        take_profit=take_profit_reason,
    )
    assert idx == 0
    assert reason == "stop_loss:touch"
    assert px == pytest.approx(8.99)


def test_scan_gap_open_stop_10pct():
    o = np.array([8.90, 9.00])
    h = np.array([9.00, 9.10])
    c = np.array([8.95, 9.05])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=STOP_PCT,
        profit_base=0.15,
        trail_ratio=0.0,
        peak_gap_min=0,
        take_profit=take_profit_reason,
    )
    assert idx == 0
    assert reason == "stop_loss:gap_open"
    assert px == pytest.approx(8.90)


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
        stop_pct=STOP_PCT,
        profit_base=0.15,
        trail_ratio=0.0,
        peak_gap_min=0,
        take_profit=take_profit_reason,
    )
    assert idx == -1
    assert reason == ""
    assert peak == pytest.approx(10.0)


def test_scan_unarmed_below_floor():
    o = np.array([10.02, 10.03])
    h = np.array([10.05, 10.06])
    c = np.array([10.04, 10.05])
    idx, _, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=STOP_PCT,
        profit_base=0.15,
        trail_ratio=0.0,
        peak_gap_min=0,
        take_profit=take_profit_reason,
    )
    assert idx == -1
    assert reason == ""


def test_scan_trail_keep80_on_close():
    o = np.array([11.80, 11.70])
    h = np.array([12.00, 11.75])
    c = np.array([11.80, 11.55])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=STOP_PCT,
        profit_base=0.15,
        trail_ratio=0.0,
        peak_gap_min=0,
        take_profit=take_profit_reason,
    )
    assert idx == 1
    assert reason == "trail:max101_80"
    assert px == pytest.approx(11.55)


def test_scan_peak_gap_15_blocks_then_fires():
    o = np.array([11.80, 11.50, 11.50])
    h = np.array([12.00, 11.55, 11.55])
    c = np.array([11.50, 11.50, 11.50])
    idx, px, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=STOP_PCT,
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([570, 580, 585]),
        peak_gap_min=15,
        take_profit=take_profit_reason,
    )
    assert idx == 2
    assert reason == "trail:max101_80"
    assert px == pytest.approx(11.50)


def test_scan_limit_up_reserves_then_open_board():
    hooks = sim.apply_csv_strategy("version8")
    idx, px, reason, _, _ = sim.scan_held_day(
        np.array([11.0, 10.90]),
        np.array([11.0, 10.95]),
        np.array([11.0, 10.90]),
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=hooks["stop_pct"],
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([575, 581]),
        peak_gap_min=0,
        take_profit=hooks["take_profit"],
        gate_code="600000.SH",
        reserve_limit_up=True,
        defer_limit_up=False,
        limit_up=11.0,
    )
    assert idx == 1
    assert reason == "open_board"
    assert px == pytest.approx(10.90)


def test_scan_still_limit_up_after_window_holds():
    hooks = sim.apply_csv_strategy("version8")
    idx, _, reason, _, _ = sim.scan_held_day(
        np.array([11.0, 11.0]),
        np.array([11.0, 11.0]),
        np.array([11.0, 11.0]),
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=hooks["stop_pct"],
        profit_base=0.0,
        trail_ratio=0.0,
        hm=np.array([575, 581]),
        peak_gap_min=0,
        take_profit=hooks["take_profit"],
        gate_code="600000.SH",
        reserve_limit_up=True,
        defer_limit_up=False,
        limit_up=11.0,
    )
    assert idx == -1
    assert reason == ""


def test_scan_stale_8():
    idx, px, reason, _, _ = sim.scan_held_day(
        np.array([10.02]),
        np.array([10.05]),
        np.array([10.03]),
        cost=10.0,
        peak=10.05,
        n_days=8,
        can_sell=True,
        stop_pct=STOP_PCT,
        profit_base=0.15,
        trail_ratio=0.0,
        peak_gap_min=0,
        take_profit=take_profit_reason,
    )
    assert idx == 0
    assert reason == "force_sell:stale"
    assert px == pytest.approx(10.03)


def test_scan_trail_beats_stale():
    idx, px, reason, _, _ = sim.scan_held_day(
        np.array([11.60]),
        np.array([11.70]),
        np.array([11.60]),
        cost=10.0,
        peak=12.00,
        n_days=8,
        can_sell=True,
        stop_pct=STOP_PCT,
        profit_base=0.15,
        trail_ratio=0.0,
        peak_gap_min=0,
        take_profit=take_profit_reason,
    )
    assert idx == 0
    assert reason == "trail:max101_80"
    assert px == pytest.approx(11.60)


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
    assert chase_explained(st) == st.stats["skip_limit_up"]
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
    assert chase_explained(st) == st.stats["skip_limit_up"]


def test_simulate_held_name_adds_second_lot_below_cost():
    dates = ["2025-11-03", "2025-11-04"]
    m = _day(
        "2025-11-03", [(930, 10.0, 10.1, 9.95, 10.0), (1455, 10.0, 10.05, 9.98, 10.0)]
    )
    m2 = _day(
        "2025-11-04",
        [
            (930, 9.85, 9.95, 9.82, 9.88),
            (1455, 9.90, 9.95, 9.85, 9.90),
        ],
    )
    minute = {"600000.SH": pd.concat([m, m2])}
    daily = {"600000.SH": _daily(dates, [10.0, 9.90])}
    pool = {"20251103": ["600000.SH"], "20251104": ["600000.SH"]}
    st = sim.simulate(minute, daily, pool, "20251103", "20251104", strategy="version8")
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert [t["lot"] for t in buys] == [0, 1]
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0


def test_simulate_held_name_adds_when_below_target():
    dates = ["2025-11-03", "2025-11-04"]
    m = _day(
        "2025-11-03", [(930, 10.0, 10.1, 9.95, 10.0), (1455, 10.0, 10.05, 9.98, 10.0)]
    )
    m2 = _day(
        "2025-11-04",
        [(930, 10.02, 10.05, 10.00, 10.03), (1455, 10.03, 10.06, 10.00, 10.04)],
    )
    minute = {"600000.SH": pd.concat([m, m2])}
    daily = {"600000.SH": _daily(dates, [10.0, 10.04])}
    pool = {"20251103": ["600000.SH"], "20251104": ["600000.SH"]}
    st = sim.simulate(minute, daily, pool, "20251103", "20251104", strategy="version8")
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert [t["lot"] for t in buys] == [0, 1]
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0
