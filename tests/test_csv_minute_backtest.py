# -*- coding: utf-8 -*-
"""csv_minute_backtest（策略6 分钟向量化）单元测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_minute_backtest as sim
from backtest.research.csv_daily_backtest import chase_explained


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


def test_scan_none_stop_does_not_sell_after_halving():
    idx, _, reason, peak, _ = sim.scan_held_day(
        np.array([5.0]),
        np.array([5.1]),
        np.array([5.0]),
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=None,
        profit_base=0.01,
        trail_ratio=0.50,
        take_profit=lambda *_args: None,
    )
    assert idx == -1
    assert reason == ""
    assert peak == pytest.approx(10.0)


def test_strategy4_scan_uses_sell_gate_with_yesterday_closes():
    hooks = sim.apply_csv_strategy("version4")
    idx, px, reason, _, _ = sim.scan_held_day(
        np.array([9.9]), np.array([10.0]), np.array([9.9]),
        cost=10.0, peak=10.0, n_days=1, can_sell=True,
        stop_pct=None, profit_base=0.0, trail_ratio=0.0,
        take_profit=hooks["take_profit"], sell_gate=hooks["sell_gate"],
        gate_code="600000.SH", gate_day=pd.Timestamp("2025-11-04"),
        daily_closes_ending_yesterday=[10.0] * 5,
    )
    assert (idx, reason, px) == (0, "ma_signal:MA5", pytest.approx(9.9))


@pytest.mark.parametrize(
    ("n_days", "can_sell", "hm", "close", "expected_idx", "expected_reason"),
    [
        (0, False, 890, 10.0, -1, ""),
        (1, True, 571, 10.0, -1, ""),
        (1, True, 890, 10.0, 0, "force_sell:time"),
        (1, True, 890, 10.2, 0, "profit_take:target"),
    ],
)
def test_strategy5_force_sell_clock(
    n_days, can_sell, hm, close, expected_idx, expected_reason
):
    hooks = sim.apply_csv_strategy("version5")
    idx, _, reason, _, _ = sim.scan_held_day(
        np.array([close]), np.array([close]), np.array([close]),
        cost=10.0, peak=10.0, n_days=n_days, can_sell=can_sell,
        stop_pct=hooks["stop_pct"], profit_base=0.0, trail_ratio=0.0,
        hm=np.array([hm]), peak_gap_min=hooks["peak_gap_min"],
        take_profit=hooks["take_profit"], force_sell_hm=hooks["force_sell_hm"],
    )
    assert idx == expected_idx
    assert reason == expected_reason


def test_strategy5_force_sell_defers_at_limit_down_close():
    hooks = sim.apply_csv_strategy("version5")
    idx, _, reason, _, _ = sim.scan_held_day(
        np.array([9.1]), np.array([9.1]), np.array([9.0]),
        cost=10.0, peak=10.0, n_days=1, can_sell=True, stop_pct=None,
        profit_base=0.0, trail_ratio=0.0, limit_down=9.0,
        hm=np.array([890]), take_profit=hooks["take_profit"],
        force_sell_hm=hooks["force_sell_hm"],
    )
    assert idx == -1
    assert reason == ""


def test_strategy3_limit_up_reserve_then_open_board_ignores_peak_gap():
    hooks = sim.apply_csv_strategy("version3")
    state = {"reserved": False}
    idx, px, reason, _, _ = sim.scan_held_day(
        np.array([12.0, 11.9]), np.array([12.0, 12.1]), np.array([12.0, 11.9]),
        cost=10.0, peak=10.0, n_days=1, can_sell=True,
        stop_pct=hooks["stop_pct"], profit_base=0.0, trail_ratio=0.0,
        hm=np.array([575, 581]), peak_gap_min=999,
        take_profit=hooks["take_profit"], reserve_limit_up=True, limit_up=12.0,
        reserve_state=state,
    )
    assert (idx, reason, px) == (1, "open_board", pytest.approx(11.9))
    assert state["reserved"] is False


def test_strategy3_reserved_twenty_percent_board_skips_target():
    hooks = sim.apply_csv_strategy("version3")
    state = {"reserved": False}
    idx, _, reason, _, _ = sim.scan_held_day(
        np.array([12.0, 12.0]), np.array([12.0, 12.0]), np.array([12.0, 12.0]),
        cost=10.0, peak=10.0, n_days=1, can_sell=True,
        stop_pct=hooks["stop_pct"], profit_base=0.0, trail_ratio=0.0,
        hm=np.array([575, 581]), peak_gap_min=hooks["peak_gap_min"],
        take_profit=hooks["take_profit"], reserve_limit_up=True, limit_up=12.0,
        reserve_state=state,
    )
    assert idx == -1
    assert reason == ""
    assert state["reserved"] is True


def test_scan_t1_trail_on_close():
    # 峰值 10.50（+5%，锚 1% 后超额 4%），T+1 档 50% → 线 +3% → 10.30
    # 09:30 创新高，09:45 才允许止盈（间隔 15 分钟）
    o = np.array([10.40, 10.40, 10.40, 10.36])
    h = np.array([10.50, 10.50, 10.50, 10.36])
    c = np.array([10.45, 10.45, 10.45, 10.298])
    hm = np.array([570, 571, 572, 585])
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


def test_scan_tp_blocked_within_15_minutes_of_peak():
    o = np.array([10.40, 10.20])
    h = np.array([10.50, 10.20])
    c = np.array([10.45, 10.20])
    hm = np.array([570, 584])  # 间隔 14 分钟，不能 < 15
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


def test_scan_tp_allowed_at_15_minutes():
    o = np.array([10.40, 10.20])
    h = np.array([10.50, 10.20])
    c = np.array([10.45, 10.20])
    hm = np.array([570, 585])  # 间隔 15 分钟，允许
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
    assert idx == 1
    assert reason == "trail:T+1"
    assert px == pytest.approx(10.20)


def test_scan_no_tp_when_close_below_cost():
    o = np.array([10.40, 9.90])
    h = np.array([10.50, 10.00])
    c = np.array([10.45, 9.95])
    hm = np.array([570, 585])
    idx, _, reason, _, _ = sim.scan_held_day(
        o,
        h,
        c,
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.08,
        profit_base=0.01,
        trail_ratio=0.30,
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


def test_simulate_limit_up_at_1455_abandons_when_945_below_open():
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
        strategy="version6",
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_abandon"] == 1
    assert st.stats["buys"] == 0
    assert chase_explained(st) == st.stats["skip_limit_up"]


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
        strategy="version6",
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_buy"] == 1
    assert chase_explained(st) == st.stats["skip_limit_up"]
    buy = [t for t in st.trades if t["side"] == "BUY"][0]
    assert buy["reason"] == "chase:T+1"
    assert buy["date"] == "20251104"
    assert buy["price"] == pytest.approx(11.10)


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
        minute,
        daily,
        {"20251103": ["000592.SZ"]},
        "20251103",
        "20251104",
        strategy="version6",
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["buys"] == 0
    assert chase_explained(st) == st.stats["skip_limit_up"]


def test_simulate_chase_pending_eod_on_last_day():
    dates = ["2025-11-03"]
    m = _day(
        "2025-11-03", [(930, 10.5, 11.0, 10.5, 10.8), (1455, 11.0, 11.0, 11.0, 11.0)]
    )
    st = sim.simulate(
        {"600000.SH": m},
        {"600000.SH": _daily(dates, [11.0])},
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251103",
        strategy="version6",
    )
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_pending_eod"] == 1
    assert chase_explained(st) == st.stats["skip_limit_up"]


def test_simulate_chase_overwrite_same_day_duplicate_pool():
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
    st = sim.simulate(
        {"600000.SH": pd.concat([m, m2])},
        {"600000.SH": _daily(dates, [11.0, 11.12])},
        {"20251103": ["600000.SH", "600000.SH"]},
        "20251103",
        "20251104",
        strategy="version6",
    )
    assert st.stats["skip_limit_up"] == 2
    assert st.stats["chase_overwrite"] == 1
    assert st.stats["chase_abandon"] == 1
    assert chase_explained(st) == st.stats["skip_limit_up"]


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
        strategy="version6",
        stop_pct=0.02,
    )
    assert st.stats["buys"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "stop_loss:gap_open"
    assert sell["date"] == "20251104"
    assert sell["price"] == pytest.approx(9.40)


def test_t0_after_buy_high_does_not_set_peak():
    # 14:55 买 10.00，随后 high=10.50。若把 T+0 高点当峰值，T+1 close=10.10 会锚定回撤。
    dates = ["2025-11-03", "2025-11-04"]
    m0 = _day(
        "2025-11-03",
        [
            (930, 10.0, 10.3, 9.9, 10.0),
            (1455, 10.0, 10.02, 9.99, 10.0),
            (1500, 10.40, 10.50, 10.30, 10.45),
        ],
    )
    m1 = _day(
        "2025-11-04",
        [
            (930, 10.08, 10.10, 10.05, 10.10),
            (931, 10.08, 10.10, 10.05, 10.10),
            (945, 10.08, 10.10, 10.05, 10.10),
            (1455, 10.08, 10.10, 10.05, 10.10),
        ],
    )
    minute = {"600000.SH": pd.concat([m0, m1])}
    daily = {"600000.SH": _daily(dates, [10.45, 10.10])}
    st = sim.simulate(
        minute,
        daily,
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        strategy="version6",
    )
    assert st.stats["buys"] == 1
    assert st.stats["sell_trail"] == 0
    assert not any(t["side"] == "SELL" for t in st.trades)


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
        strategy="version6",
        stop_pct=0.02,
    )
    assert st.stats["buys"] == 1
    assert st.stats["sell_stop"] == 1
