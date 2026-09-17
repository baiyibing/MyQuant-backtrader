# -*- coding: utf-8 -*-
"""策略 8 走共享 csv_daily_backtest 引擎的日线近似单测。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_daily_backtest as sim


DAYS = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]


def _bars(days: list[str], rows: dict[str, list[tuple]], start_offset: int = 1) -> dict:
    out = {}
    idx = pd.to_datetime([d for d in days])
    for code, r in rows.items():
        pre = pd.Timestamp(days[0]) - pd.Timedelta(days=start_offset * 2)
        pre_idx = pd.DatetimeIndex([pre]) if pre not in idx else pd.DatetimeIndex([])
        frame = pd.DataFrame(
            {
                "open": [10.0] + [x[0] for x in r],
                "high": [10.0] + [x[1] for x in r],
                "low": [10.0] + [x[2] for x in r],
                "close": [10.0] + [x[3] for x in r],
            },
            index=pre_idx.append(idx),
        ).astype(np.float64)
        out[code] = frame
    return out


def _run(pool: dict, bars: dict, **kwargs):
    kwargs.setdefault("strategy", "version8")
    return sim.simulate(bars, pool, "20251103", "20251107", **kwargs)


def test_t1_no_sell_on_entry_day():
    rows = {
        "600000.SH": [
            (10.2, 10.3, 6.0, 10.0),
            (9.85, 9.90, 6.90, 9.60),
            (9.4, 9.5, 9.2, 9.3),
            (9.3, 9.4, 9.1, 9.2),
            (9.2, 9.3, 9.0, 9.1),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["buys"] == 1
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["defer_sell_limit_down"] >= 1
    assert sells[0]["date"] == "20251105"
    assert sells[0]["reason"] == "stop_loss:touch"
    assert sells[0]["price"] == pytest.approx(9.4)


@pytest.mark.skip(reason="Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules")

def test_gap_open_stop_30pct():
    # 创业板 20% 板：D1 未到 30% 止损；D2 跌停顺延；D3 跌破止损且未跌停。
    rows = {
        "300001.SZ": [
            (10.2, 10.3, 9.4, 10.0),
            (8.00, 8.50, 8.00, 8.00),
            (6.40, 7.00, 6.40, 6.80),
            (6.9, 7.0, 6.7, 6.8),
            (7.8, 7.9, 7.6, 7.7),
        ]
    }
    st = _run({"20251103": ["300001.SZ"]}, _bars(DAYS, rows))
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "stop_loss:gap_open"
    assert sell["date"] == "20251106"
    assert sell["price"] == pytest.approx(6.90)
    assert st.stats["defer_sell_limit_down"] == 1


@pytest.mark.skip(reason="Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules")

def test_band_tp_exits_next_open():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (12.0, 13.0, 11.8, 11.489),  # 峰值 +30%，收盘回撤到 +15% 下
            (11.80, 11.90, 11.70, 11.85),
            (11.8, 11.9, 11.6, 11.7),
            (11.7, 11.8, 11.5, 11.6),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    # T+1 不评；T+2 close 11.85 > 档3线 11.80；T+3 close 11.7 触发 → 次日开盘离场
    # facts §4b 写 20251106@11.80 与引擎推演不符，以代码为准（STOP 已记）。
    assert sell["reason"] == "trail:band:3"
    assert sell["date"] == "20251107"
    assert sell["price"] == pytest.approx(11.7)


@pytest.mark.skip(reason="Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules")

def test_small_band_tp_exits_next_open():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.8, 11.0, 10.1, 10.199),  # 峰值 +10%，收盘回撤到 +2% 下
            (10.15, 10.20, 10.10, 10.12),
            (10.1, 10.2, 10.0, 10.05),
            (10.0, 10.1, 9.9, 10.0),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "trail:band:2"
    assert sell["date"] == "20251106"
    assert sell["price"] == pytest.approx(10.10)


@pytest.mark.skip(reason="Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules")

def test_disarmed_tp_when_peak_only_1pct():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.05, 10.10, 10.00, 10.05),
            (10.04, 10.08, 10.00, 10.04),
            (10.03, 10.06, 9.99, 10.03),
            (10.02, 10.05, 9.99, 10.02),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["date"] == "20251107"
    assert sell["reason"] == "trail:band:1"
    assert sell["price"] == pytest.approx(10.02)
    assert st.stats["sell_stop"] == 0


@pytest.mark.skip(reason="Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules")

def test_no_tp_when_small_band_still_above_2pct():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (11.0, 11.50, 10.8, 11.40),
            (11.4, 11.5, 11.3, 11.4),
            (11.3, 11.4, 11.2, 11.3),
            (11.2, 11.3, 11.1, 11.2),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    # g=15% 价式落三档；T+2 起按全局底 1.15 触发
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "trail:band:3"
    assert sell["date"] == "20251106"
    assert sell["price"] == pytest.approx(11.30)
    assert st.stats["sell_stop"] == 0


def test_entry_day_high_does_not_set_peak():
    rows = {
        "600000.SH": [
            (10.0, 15.0, 9.95, 10.0),
            (10.00, 10.00, 9.99, 10.00),
            (10.00, 10.00, 9.99, 10.00),
            (10.00, 10.00, 9.99, 10.00),
            (10.00, 10.00, 9.99, 10.00),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 0


def test_limit_up_close_chases_when_close_above_open():
    rows = {
        "600000.SH": [
            (10.5, 11.0, 10.5, 11.0),
            (11.00, 11.40, 10.90, 11.20),
            (11.2, 11.3, 11.0, 11.1),
            (11.1, 11.2, 10.9, 11.0),
            (11.0, 11.1, 10.8, 10.9),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_buy"] == 1
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]
    buy = [t for t in st.trades if t["side"] == "BUY"][0]
    assert buy["date"] == "20251104"
    assert buy["reason"] == "chase:T+1"
    assert buy["price"] == pytest.approx(11.20)


def test_limit_up_close_abandons_when_close_below_open():
    rows = {
        "600000.SH": [
            (10.5, 11.0, 10.5, 11.0),
            (11.20, 11.30, 10.90, 11.05),
            (11.0, 11.2, 10.8, 10.9),
            (10.9, 11.0, 10.7, 10.8),
            (10.8, 10.9, 10.6, 10.7),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_abandon"] == 1
    assert st.stats["buys"] == 0
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


def test_summarize_v8_params():
    from backtest.research.csv_ledger import SimState
    from backtest.research.csv_artifacts import summarize
    from backtest.research.strategy8_rules import record_strategy8_params

    st = SimState()
    record_strategy8_params(st)
    st.equity_curve = [("20251103", 21_000_000.0)]
    text = summarize(st, 21_000_000.0, "20251103", "20251103", engine="csv_daily_v8")
    assert "止损 10%" in text
    assert "涨幅比例回撤阶梯" in text
    assert "arm=6%/15%/50%/100%" in text
    assert "keep=60%/70%/80%" in text
    assert "档2底+2%" in text
    assert "档3全局底+15%" in text
    assert "T+1止盈豁免" in text
    assert "T+5+" not in text
    assert "基础止盈 15%" not in text
    assert "涨幅>120%" not in text


@pytest.mark.skip(reason="Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules")

def test_held_name_adds_second_lot():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.2, 10.5, 10.1, 10.3),
            (10.8, 11.1, 10.7, 11.0),
            (10.5, 10.6, 8.50, 10.50),
            (10.0, 10.1, 9.8, 9.9),
        ]
    }
    pool = {"20251103": ["600000.SH"], "20251105": ["600000.SH"]}
    bars = _bars(DAYS, rows)
    st = _run(pool, bars)
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert [t["lot"] for t in buys] == [0, 1]
    assert buys[0]["price"] == pytest.approx(10.0)
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0
    assert not [t for t in st.trades if t["side"] == "SELL"]
    assert [p.lot_id for p in st.positions["600000.SH"]] == [0, 1]

    st6 = _run(pool, bars, strategy="version6")
    assert st6.stats["buys"] == 1
    assert st6.stats["skip_held"] == 1
    assert st6.stats["add_lots"] == 0


@pytest.mark.skip(reason="Livermore host lock on master engines: v2 behavioral fixture; covered by test_strategy8_rules")

def test_peak_cross_15pct_tightens_to_global_floor():
    """向量 #21 daily simulate：反弹抬 peak 跨 15% 后按全局底 +15% 评。"""
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),       # D0 买入
            (11.0, 11.49, 10.9, 11.45),     # T+1 peak=11.49 二档；止盈豁免
            (11.42, 11.51, 11.30, 11.40),   # T+2 peak→11.51 三档线 11.5；close 触
            (11.30, 11.40, 11.20, 11.25),   # 次日开盘离场
            (11.2, 11.3, 11.1, 11.2),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "trail:band:3"
    assert sell["date"] == "20251106"
    assert sell["price"] == pytest.approx(11.30)

