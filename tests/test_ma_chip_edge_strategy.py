# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.research.ma_chip_edge_backtest import (
    MaChipEdgeStrategy,
    SignalPandasData,
    AShareCommInfo,
    affordable_size,
    board_of,
    build_signal_frame,
    is_limit_open,
    mask_pre_window_edges,
    week_ma20_asof,
)

import backtrader as bt


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
    n = 120
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
