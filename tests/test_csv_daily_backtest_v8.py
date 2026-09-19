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


def _run(
    pool: dict, bars: dict, start: str = "20251103", end: str = "20251107", **kwargs
):
    kwargs.setdefault("strategy", "version8")
    return sim.simulate(bars, pool, start, end, **kwargs)


def test_t1_no_sell_on_entry_day():
    # 10% 线=9.00。主板 T+1 收 9.85，不到止损、峰值未到 ×1.01。
    rows = {
        "600000.SH": [
            (10.2, 10.3, 6.0, 10.0),
            (9.85, 9.90, 9.85, 9.88),
            (9.90, 9.95, 9.85, 9.90),
            (9.88, 9.92, 9.85, 9.88),
            (9.86, 9.90, 9.84, 9.86),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["buys"] == 1
    assert not [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["sell_stop"] == 0


def test_gap_open_stop_after_limit_down_defer():
    # 创业板 20% 板、止损 10%：D1/D2 贴跌停顺延；D3 开盘未跌停、仍在止损下 → gap_open。
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
    assert st.stats["defer_sell_limit_down"] == 2


def test_trail_max101_80_exits_next_open_after_t1():
    # T+1 high 10.80 close 10.64（未到 10% 板）→ line=10.64，次日开盘卖。
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.70, 10.80, 10.50, 10.64),
            (10.60, 10.66, 10.50, 10.55),
            (10.50, 10.55, 10.40, 10.45),
            (10.40, 10.45, 10.30, 10.35),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "trail:max101_80"
    assert sell["date"] == "20251105"
    assert sell["price"] == pytest.approx(10.60)
    assert st.stats["sell_trail"] == 1


def test_unarmed_below_floor_does_not_trail():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.02, 10.05, 10.00, 10.04),
            (10.03, 10.06, 10.00, 10.03),
            (10.02, 10.05, 9.98, 10.02),
            (10.01, 10.04, 9.97, 10.01),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_profit_take"] == 0
    assert st.stats["sell_trail"] == 0
    assert not [t for t in st.trades if t["side"] == "SELL"]


def test_limit_up_reserves_then_open_board():
    rows = {
        "600000.SH": [
            (10.0, 10.0, 10.0, 10.0),
            (11.0, 11.0, 11.0, 11.0),
            (10.90, 10.95, 10.80, 10.90),
            (10.80, 10.90, 10.70, 10.80),
            (10.70, 10.80, 10.60, 10.70),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "open_board"
    assert sell["date"] == "20251105"
    assert sell["price"] == pytest.approx(10.90)
    assert st.stats["sell_open_board"] == 1


def test_still_limit_up_keeps_reserve():
    rows = {
        "600000.SH": [
            (10.0, 10.0, 10.0, 10.0),
            (11.0, 11.0, 11.0, 11.0),
            (12.10, 12.10, 12.05, 12.10),
            (13.31, 13.31, 13.20, 13.31),
            (14.64, 14.64, 14.50, 14.64),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert not [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["sell_open_board"] == 0


def test_entry_day_high_does_not_take_profit():
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
    assert st.stats["sell_profit_take"] == 0
    assert not [t for t in st.trades if t["side"] == "SELL"]


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
    assert "峰差15分钟" in text
    assert "T+1起max(×1.01,买价+80%涨幅)" in text
    assert "涨停保留至开板" in text
    assert "僵持8日平仓" in text
    assert "名单全加+独立+20%台阶" in text
    assert "只做首笔" not in text
    assert "止盈 2%" not in text
    assert "峰差30分钟" not in text
    assert "≥10%保底×1.10/回撤50%" not in text
    assert "未到+6%跌10%离场" not in text
    assert "涨停顺延次日" not in text
    assert "上证下方仍开新仓" not in text
    assert "档1死区" not in text
    assert "T+1止盈豁免" not in text


def test_held_name_relist_below_cost_adds():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (9.90, 9.95, 9.85, 9.90),
            (9.88, 9.92, 9.80, 9.85),
            (9.80, 9.85, 9.70, 9.80),
            (9.70, 9.80, 9.60, 9.70),
        ]
    }
    pool = {"20251103": ["600000.SH"], "20251104": ["600000.SH"]}
    bars = _bars(DAYS, rows)
    st = _run(pool, bars)
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert [t["lot"] for t in buys] == [0, 1]
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0


def test_held_name_relist_winner_below_target_adds():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.02, 10.05, 10.00, 10.04),
            (10.03, 10.06, 10.00, 10.03),
            (10.02, 10.05, 9.98, 10.02),
            (10.01, 10.04, 9.97, 10.01),
        ]
    }
    pool = {"20251103": ["600000.SH"], "20251104": ["600000.SH"]}
    st = _run(pool, _bars(DAYS, rows))
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert [t["lot"] for t in buys] == [0, 1]
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0


def test_off_list_step_add_loses_to_trail():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.70, 10.80, 10.50, 10.64),
            (10.60, 10.66, 10.50, 10.55),
            (10.50, 10.55, 10.40, 10.45),
            (10.40, 10.45, 10.30, 10.35),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert not [t for t in st.trades if t.get("reason") == "add:step20"]
    assert st.stats["sell_trail"] == 1


def test_stop_10_exits_next_open():
    rows = {
        "300001.SZ": [
            (10.0, 10.1, 9.95, 10.0),
            (7.20, 7.30, 6.90, 6.99),
            (6.95, 7.00, 6.90, 6.96),
            (6.90, 6.95, 6.80, 6.90),
            (6.80, 6.90, 6.70, 6.80),
        ]
    }
    st = _run({"20251103": ["300001.SZ"]}, _bars(DAYS, rows))
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert str(sell["reason"]).startswith("stop_loss")
    assert sell["date"] in {"20251104", "20251105"}
    assert st.stats["sell_stop"] == 1


def test_stale_8_exits_next_open():
    days = []
    d = pd.Timestamp("2025-11-03")
    while len(days) < 10:
        if d.weekday() < 5:
            days.append(d.strftime("%Y-%m-%d"))
        d += pd.Timedelta(days=1)
    flat = [(10.02, 10.05, 9.98, 10.03)] * 10
    st = _run(
        {"20251103": ["600000.SH"]},
        _bars(days, {"600000.SH": flat}),
        start="20251103",
        end=days[-1].replace("-", ""),
    )
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "force_sell:stale"
    assert sell["date"] == days[9].replace("-", "")
    assert st.stats["sell_force"] == 1


def test_t0_does_not_take_profit():
    rows = {
        "600000.SH": [
            (12.0, 13.0, 11.8, 12.00),
            (11.0, 11.1, 10.9, 11.0),
        ]
    }
    short = DAYS[:2]
    st = _run({"20251103": ["600000.SH"]}, _bars(short, rows), end="20251103")
    assert st.stats["sell_profit_take"] == 0
    assert not [t for t in st.trades if t["side"] == "SELL"]
