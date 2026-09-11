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
            (10.2, 10.3, 8.0, 10.0),
            (9.85, 9.90, 8.20, 9.60),
            (9.4, 9.5, 9.2, 9.3),
            (9.3, 9.4, 9.1, 9.2),
            (9.2, 9.3, 9.0, 9.1),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["buys"] == 1
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells[0]["date"] == "20251104"
    assert sells[0]["reason"] == "stop_loss:touch"
    assert sells[0]["price"] == pytest.approx(8.5)


def test_gap_open_stop_15pct():
    # 创业板 20% 跌停，才能在未跌停时跳空到 15% 止损线下。
    rows = {
        "300001.SZ": [
            (10.2, 10.3, 9.4, 10.0),
            (8.40, 8.50, 8.20, 8.30),
            (8.3, 8.4, 8.1, 8.2),
            (8.2, 8.3, 8.0, 8.1),
            (8.1, 8.2, 7.9, 8.0),
        ]
    }
    st = _run({"20251103": ["300001.SZ"]}, _bars(DAYS, rows))
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "stop_loss:gap_open"
    assert sell["price"] == pytest.approx(8.40)


def test_band_tp_exits_next_open():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (12.0, 13.0, 11.8, 11.989),  # 峰值 +30%，收盘回撤到 +20% 下
            (11.80, 11.90, 11.70, 11.85),
            (11.8, 11.9, 11.6, 11.7),
            (11.7, 11.8, 11.5, 11.6),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "trail:band:20"
    assert sell["date"] == "20251105"
    assert sell["price"] == pytest.approx(11.80)


def test_no_tp_when_peak_not_above_20pct():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (11.0, 11.99, 10.8, 11.50),
            (11.4, 11.5, 11.3, 11.4),
            (11.3, 11.4, 11.2, 11.3),
            (11.2, 11.3, 11.1, 11.2),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 0
    assert st.stats["sell_stop"] == 0


def test_entry_day_high_does_not_set_peak():
    rows = {
        "600000.SH": [
            (10.0, 15.0, 9.95, 10.0),
            (10.00, 10.10, 9.99, 10.05),
            (10.00, 10.08, 9.99, 10.02),
            (10.00, 10.07, 9.99, 10.01),
            (10.00, 10.06, 9.99, 10.00),
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


def test_summarize_v8_params():
    from backtest.research.csv_daily_backtest import SimState, summarize
    from backtest.research.strategy8_rules import record_strategy8_params

    st = SimState()
    record_strategy8_params(st)
    st.equity_curve = [("20251103", 21_000_000.0)]
    text = summarize(st, 21_000_000.0, "20251103", "20251103", engine="csv_daily_v8")
    assert "止损 15%" in text
    assert "基础止盈 20%" in text
    assert "T+5+" not in text
