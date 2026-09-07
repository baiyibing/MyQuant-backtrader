# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.research.ma_chip_edge_backtest import (
    CHIP_WINDOW,
    MaChipEdgeStrategy,
    SignalPandasData,
    AShareCommInfo,
    _cyqk_series_python,
    _try_cyqk_series_rust,
    affordable_size,
    bb_upper_series,
    board_of,
    build_signal_frame,
    cyqk_series,
    format_trades_by_stock,
    is_limit_open,
    mask_pre_window_edges,
    pair_round_trips,
    turnover_from_daily_shares,
    week_ma20_asof,
)

import backtrader as bt


def test_chip_window_is_200_bars_including_d():
    assert CHIP_WINDOW == 200


def test_turnover_uses_each_day_asof_shares():
    vol = np.array([1.0e6, 1.0e6, 1.0e6])
    sh = np.array([1.0e8, 2.0e8, 2.0e8])
    tr = turnover_from_daily_shares(vol, sh)
    assert tr[0] == pytest.approx(1.0)
    assert tr[1] == pytest.approx(0.5)
    assert tr[2] == pytest.approx(0.5)
    bad = turnover_from_daily_shares(vol, np.array([1.0e8, np.nan, 2.0e8]))
    assert np.isfinite(bad[0])
    assert not np.isfinite(bad[1])
    assert np.isfinite(bad[2])


def test_cyqk_series_skips_window_with_missing_day_shares(monkeypatch):
    n = 6
    idx = pd.bdate_range("2024-01-02", periods=n)
    df = pd.DataFrame(
        {
            "open": np.full(n, 10.0),
            "high": np.full(n, 10.1),
            "low": np.full(n, 9.9),
            "close": np.full(n, 10.0),
            "volume": np.full(n, 1e6),
        },
        index=idx,
    )
    sh = np.full(n, 1.0e8)
    sh[2] = np.nan
    monkeypatch.setattr(
        "backtest.research.ma_chip_edge_backtest.shares_asof_series",
        lambda *args, **kwargs: sh,
    )
    out = cyqk_series(df, "000001.SZ", window=4)
    # last index can form a 4-bar window only if all 4 shares finite; sh[2] poisons i>=2
    assert not np.isfinite(out.to_numpy()).any()


def test_cyqk_rust_matches_python_when_available(monkeypatch):
    n = 30
    window = 20
    idx = pd.bdate_range("2024-01-02", periods=n)
    close = np.linspace(10.0, 12.0, n)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.15,
            "low": close - 0.15,
            "close": close,
            "volume": np.full(n, 5.0e5),
        },
        index=idx,
    )
    sh = np.full(n, 1.0e9)
    sh[18:] = 2.0e9
    monkeypatch.setattr(
        "backtest.research.ma_chip_edge_backtest.shares_asof_series",
        lambda *args, **kwargs: sh,
    )
    rust = _try_cyqk_series_rust(df, sh, window, window - 1)
    if rust is None:
        pytest.skip("turnover_resist.compute_cyqk_series not installed")
    py = _cyqk_series_python(df, "000001.SZ", sh, window, window - 1)
    r = rust.to_numpy()
    p = py.to_numpy()
    mask = np.isfinite(p)
    assert mask.any()
    assert np.isfinite(r[mask]).all()
    assert float(np.max(np.abs(r[mask] - p[mask]))) < 1e-6


def test_board_of_excludes_star():
    assert board_of("600000.SH") == "sh_main"
    assert board_of("688001.SH") is None
    assert board_of("000001.SZ") == "sz_main"
    assert board_of("300001.SZ") == "chinext"
    assert board_of("301001.SZ") == "chinext"
    assert board_of("003001.SZ") == "sz_main"


def test_week_ma_asof_does_not_use_unfinished_week():
    # 25 Fridays of rising close; insert a Wednesday after week 21.
    fridays = pd.bdate_range("2020-01-03", periods=25, freq="W-FRI")
    close = pd.Series(np.arange(1.0, 26.0), index=fridays)
    # Wednesday in week 22 (after 21 completed Fridays)
    wed = fridays[21] - pd.Timedelta(days=2)
    close[wed] = 100.0  # dummy mid-week print
    close = close.sort_index()
    ma = week_ma20_asof(close)
    # Wednesday must equal Friday[20] completed 20-week MA (weeks 2..21),
    # not a MA that includes later Friday[21].
    completed = close.loc[fridays[:21]]
    weekly = completed.resample("W-FRI").last().dropna()
    expect = float(weekly.iloc[-20:].mean())
    assert ma.loc[wed] == pytest.approx(expect)


def test_edge_requires_finite_prev_and_false_prev():
    n = CHIP_WINDOW + 40
    idx = pd.bdate_range("2022-01-03", periods=n)
    close = np.linspace(10.0, 20.0, n)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": np.full(n, 1e6),
        },
        index=idx,
    )
    sig = build_signal_frame(df, "000001.SZ")
    # First finite cond day cannot be edge (prev not finite)
    finite_i = np.flatnonzero(sig["finite"].to_numpy())
    if len(finite_i) < 2:
        pytest.skip("synthetic chip window produced no finite cyqk")
    first = int(finite_i[0])
    assert bool(sig["edge"].iloc[first]) is False


def test_no_cyqk_cond_is_ma_only():
    n = 160
    idx = pd.bdate_range("2022-01-03", periods=n)
    close = np.concatenate(
        [np.linspace(10.0, 12.0, 120), np.linspace(12.0, 9.0, 20), np.linspace(9.0, 14.0, 20)]
    )
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": np.full(n, 1e6),
        },
        index=idx,
    )
    off = build_signal_frame(df, "000001.SZ", use_cyqk=False)
    assert off["cyqk"].isna().all()
    close_v = off["close"].to_numpy(dtype=np.float64)
    high_v = off["high"].to_numpy(dtype=np.float64)
    ma_bb = (
        off["finite"].to_numpy()
        & (close_v > off["sma20"].to_numpy(dtype=np.float64))
        & (close_v > off["sma60"].to_numpy(dtype=np.float64))
        & (close_v > off["week_ma20"].to_numpy(dtype=np.float64))
        & (high_v > off["bb_upper"].to_numpy(dtype=np.float64))
    )
    assert np.array_equal(off["cond"].to_numpy(), ma_bb)
    assert bool(off["edge"].any())


def test_cyqk_th_080_rejects_075(monkeypatch):
    n = 160
    idx = pd.bdate_range("2022-01-03", periods=n)
    close = np.concatenate(
        [np.linspace(10.0, 12.0, 120), np.linspace(12.0, 9.0, 20), np.linspace(9.0, 14.0, 20)]
    )
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": np.full(n, 1e6),
        },
        index=idx,
    )
    fake = pd.Series(np.full(n, 0.75), index=idx)
    monkeypatch.setattr(
        "backtest.research.ma_chip_edge_backtest.cyqk_series",
        lambda *args, **kwargs: fake,
    )
    lo = build_signal_frame(df, "000001.SZ", use_cyqk=True, cyqk_th=0.70)
    hi = build_signal_frame(df, "000001.SZ", use_cyqk=True, cyqk_th=0.80)
    assert bool(lo["cond"].any())
    assert not bool(hi["cond"].any())


def test_bb_upper_blocks_when_high_inside_band():
    n = 160
    idx = pd.bdate_range("2022-01-03", periods=n)
    tail = np.linspace(9.5, 11.0, 20)
    close = np.concatenate([np.full(140, 10.0), tail])
    high_in = close.copy()
    high_in[-1] = close[-1] + 0.02
    df = pd.DataFrame(
        {
            "open": close,
            "high": high_in,
            "low": close - 0.05,
            "close": close,
            "volume": np.full(n, 1e6),
        },
        index=idx,
    )
    upper = float(bb_upper_series(pd.Series(close, index=idx)).iloc[-1])
    assert high_in[-1] < upper
    blocked = build_signal_frame(df, "000001.SZ", use_cyqk=False)
    assert bool(blocked["finite"].iloc[-1])
    assert bool(blocked["cond"].iloc[-1]) is False

    df2 = df.copy()
    df2.loc[df2.index[-1], "high"] = upper + 0.05
    opened = build_signal_frame(df2, "000001.SZ", use_cyqk=False)
    assert bool(opened["cond"].iloc[-1]) is True


def _run_edge_feed(df: pd.DataFrame, code: str = "000001.SZ") -> MaChipEdgeStrategy:
    df = df.copy()
    df["sma5"] = df["close"].rolling(5, min_periods=1).mean()
    df["edge"] = df["edge"].astype(float)
    cerebro = bt.Cerebro(stdstats=False, cheat_on_open=True, runonce=False)
    cerebro.broker.setcash(1_000_000)
    cerebro.broker.set_coo(True)
    cerebro.broker.addcommissioninfo(AShareCommInfo())
    cerebro.adddata(SignalPandasData(dataname=df), name=code)
    cerebro.addstrategy(MaChipEdgeStrategy, stock_code=code)
    return cerebro.run()[0]


def test_edge_buys_next_open_and_first_day_down_sells_next_open():
    idx = pd.bdate_range("2024-01-02", periods=6)
    # bars: 0 warmup, 1 edge, 2 buy open=10.5, close=9 (down vs prev 10), 3 sell open=8.5
    close = [10.0, 10.0, 9.0, 8.0, 8.0, 8.0]
    open_ = [10.0, 10.0, 10.5, 8.5, 8.0, 8.0]
    edge = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    df = pd.DataFrame(
        {
            "open": open_,
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1e6] * 6,
            "edge": edge,
        },
        index=idx,
    )
    strat = _run_edge_feed(df)
    sides = [(t["date"], t["side"], t["price"]) for t in strat.trades]
    assert ("2024-01-04", "BUY", 10.5) in sides
    assert ("2024-01-05", "SELL", 8.5) in sides
    # buy day must not also sell
    buy_dates = {t["date"] for t in strat.trades if t["side"] == "BUY"}
    sell_dates = {t["date"] for t in strat.trades if t["side"] == "SELL"}
    assert buy_dates.isdisjoint(sell_dates)


def test_no_buy_when_edge_false():
    idx = pd.bdate_range("2024-01-02", periods=4)
    df = pd.DataFrame(
        {
            "open": [10, 10, 10, 10],
            "high": [10.2] * 4,
            "low": [9.8] * 4,
            "close": [10, 10, 10, 10],
            "volume": [1e6] * 4,
            "edge": [0, 0, 0, 0],
        },
        index=idx,
    )
    strat = _run_edge_feed(df)
    assert strat.trades == []


def test_mask_pre_window_edges_keeps_last_pre_day():
    idx = pd.bdate_range("2023-12-25", periods=8)
    df = pd.DataFrame({"edge": [True] * 8}, index=idx)
    out = mask_pre_window_edges(df, pd.Timestamp("2024-01-01"))
    pre = idx[idx < pd.Timestamp("2024-01-01")]
    last_pre = pre[-1]
    assert bool(out.loc[last_pre, "edge"]) is True
    assert not bool(out.loc[pre[0], "edge"])


def test_skip_sell_retries_next_session():
    assert is_limit_open("000001.SZ", 8.10, 9.0, up=False)
    idx = pd.bdate_range("2024-01-02", periods=6)
    # 0 warmup, 1 edge, 2 buy 10.5 close 9, 3 limit-down skip, 4 sell 8.5
    close = [10.0, 10.0, 9.0, 8.5, 8.0, 8.0]
    open_ = [10.0, 10.0, 10.5, 8.10, 8.5, 8.0]
    edge = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    df = pd.DataFrame(
        {
            "open": open_,
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1e6] * 6,
            "edge": edge,
        },
        index=idx,
    )
    strat = _run_edge_feed(df)
    sides = [(t["date"], t["side"], t["price"]) for t in strat.trades]
    assert ("2024-01-04", "BUY", 10.5) in sides
    assert ("2024-01-05", "SELL", 8.10) not in sides
    assert ("2024-01-08", "SELL", 8.5) in sides
    assert any(e["event"] == "skip_sell" and e["date"] == "2024-01-05" for e in strat.events)


def test_affordable_size_leaves_commission():
    size = affordable_size(1_000_000.0, 31.05)
    assert size >= 100
    assert size * 31.05 + max(size * 31.05 * 0.00005, 5.0) <= 1_000_000.0 - 1.0


def test_pending_buy_stale_across_halt_gap():
    idx = list(pd.bdate_range("2024-01-01", periods=3)) + list(pd.bdate_range("2024-01-24", periods=3))
    n = len(idx)
    close = [10.0, 10.0, 10.0, 15.0, 15.0, 15.0]
    df = pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0, 15.0, 15.0, 15.0],
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1e6] * n,
            "edge": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        },
        index=pd.DatetimeIndex(idx),
    )
    strat = _run_edge_feed(df)
    assert not any(t["side"] == "BUY" for t in strat.trades)
    assert any(e.get("reason") == "stale" for e in strat.events)


def test_first_day_up_but_below_sma5_sells_next_open():
    idx = pd.bdate_range("2024-01-02", periods=6)
    # SMA5 on buy bar uses closes 12,11.5,11.2,10.9,11.1 → 11.34; close 11.1 > prev 10.9
    close = [12.0, 11.5, 11.2, 10.9, 11.1, 10.8]
    open_ = [12.0, 11.5, 11.2, 10.9, 11.0, 10.7]
    edge = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    df = pd.DataFrame(
        {
            "open": open_,
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1e6] * 6,
            "edge": edge,
        },
        index=idx,
    )
    strat = _run_edge_feed(df)
    sides = [(t["date"], t["side"], t["price"]) for t in strat.trades]
    assert ("2024-01-08", "BUY", 11.0) in sides
    assert ("2024-01-09", "SELL", 10.7) in sides


def test_pair_round_trips_fifo_open_and_unmatched():
    trades = [
        {"date": "2024-01-10", "code": "000001.SZ", "side": "BUY", "price": 10.0, "size": 32200},
        {"date": "2024-01-12", "code": "000001.SZ", "side": "SELL", "price": 11.0, "size": 32200},
        {"date": "2024-02-01", "code": "000001.SZ", "side": "BUY", "price": 12.0, "size": 20000},
        {"date": "2024-03-01", "code": "600000.SH", "side": "SELL", "price": 8.0, "size": 1000},
    ]
    pairs = pair_round_trips(trades)
    assert [p["status"] for p in pairs] == ["closed", "open", "unmatched_sell"]
    closed = pairs[0]
    assert closed["buy_size"] == 32200
    assert closed["sell_size"] == 32200
    assert closed["hold_days"] == 2
    assert closed["ret_pct"] == pytest.approx(0.1)
    assert pairs[1]["status"] == "open"
    assert pairs[1]["buy_size"] == 20000
    assert pairs[2]["code"] == "600000.SH"


def test_format_trades_by_stock_uses_share_count_not_series_size():
    pairs = pair_round_trips(
        [
            {"date": "2024-01-10", "code": "000001.SZ", "side": "BUY", "price": 10.5, "size": 32200},
            {"date": "2024-01-11", "code": "000001.SZ", "side": "SELL", "price": 10.0, "size": 32200},
        ]
    )
    stats = pd.DataFrame(
        [{"code": "000001.SZ", "board": "sz_main", "n_buys": 1, "ret": -0.05, "max_dd": -0.1}]
    )
    universe = pd.DataFrame([{"code": "000001.SZ", "board": "sz_main", "replaced": False}])
    text = format_trades_by_stock(
        pairs,
        stats,
        universe,
        [
            {"date": "2024-01-09", "code": "000001.SZ", "event": "skip_buy", "open": 10.1, "reason": "stale"},
            {"date": "2024-01-08", "code": "000001.SZ", "event": "skip_buy", "open": 10.2, "reason": float("nan")},
        ],
        title="unit",
        cash=1_000_000,
    )
    assert "32200" in text
    assert "size=5" not in text
    assert "skip_buy  2024-01-09  open=10.1000  reason=stale" in text
    assert "skip_buy  2024-01-08  open=10.2000" in text
    assert "reason=nan" not in text
    assert "-4.76%" in text


def test_no_second_buy_while_still_long():
    idx = pd.bdate_range("2024-01-02", periods=8)
    close = [10.0, 10.5, 11.0, 11.2, 11.4, 11.6, 11.8, 12.0]
    open_ = [10.0, 10.0, 10.5, 11.0, 11.2, 11.4, 11.6, 11.8]
    # edge on bar1 (buy bar2) and again on bar3/bar4 while still long
    edge = [0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    df = pd.DataFrame(
        {
            "open": open_,
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1e6] * 8,
            "edge": edge,
        },
        index=idx,
    )
    strat = _run_edge_feed(df)
    buys = [t for t in strat.trades if t["side"] == "BUY"]
    assert len(buys) == 1
    assert buys[0]["date"] == "2024-01-04"
