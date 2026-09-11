# -*- coding: utf-8 -*-
"""csv_daily_backtest（策略6 日线近似）单元测试。

合成日线注入 simulate()，锁定成交约定：
跳空止损按开盘价、触价止损按触发价、T+1、分档回撤、涨停等值跳过、正利润回撤、
T+0 峰值不前瞻、每日额度重置。边界用跨线价，避浮点 epsilon。
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_daily_backtest as sim


DAYS = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]


def _bars(days: list[str], rows: dict[str, list[tuple]], start_offset: int = 1) -> dict:
    """rows: code -> [(open, high, low, close)]，首个交易日再垫 start_offset 根预热。"""
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
    return sim.simulate(bars, pool, "20251103", "20251107", **kwargs)


def test_t1_no_sell_on_entry_day():
    # 买入日（D0 收盘 10.0 买入）当日即使 low 砸到 -5% 也不卖（T+1）
    rows = {
        "600000.SH": [
            (10.2, 10.3, 9.4, 10.0),
            (9.85, 9.90, 9.50, 9.60),  # 开盘 9.85 > 触发价 9.80，low 触价
            (9.4, 9.5, 9.2, 9.3),
            (9.3, 9.4, 9.1, 9.2),
            (9.2, 9.3, 9.0, 9.1),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows), stop_pct=0.02)
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["buys"] == 1
    assert st.stats["sell_stop"] == 1
    assert sells[0]["date"] == "20251104"
    assert sells[0]["reason"] == "stop_loss:touch"
    assert sells[0]["price"] == pytest.approx(9.8)


def test_stop_pct_override_changes_fill():
    # 同一根日线：2% 线=9.80（开盘 9.70 已跳空）；4% 线=9.60（开盘未破、盘中触价）
    rows = {
        "600000.SH": [
            (10.2, 10.3, 9.4, 10.0),
            (9.70, 9.80, 9.30, 9.45),
            (9.4, 9.5, 9.2, 9.3),
            (9.3, 9.4, 9.1, 9.2),
            (9.2, 9.3, 9.0, 9.1),
        ]
    }
    bars = _bars(DAYS, rows)
    pool = {"20251103": ["600000.SH"]}
    sell4 = [t for t in _run(pool, bars, stop_pct=0.04).trades if t["side"] == "SELL"][0]
    assert sell4["reason"] == "stop_loss:touch"
    assert sell4["price"] == pytest.approx(9.6)
    sell2 = [t for t in _run(pool, bars, stop_pct=0.02).trades if t["side"] == "SELL"][0]
    assert sell2["reason"] == "stop_loss:gap_open"
    assert sell2["price"] == pytest.approx(9.70)


def test_csv_strategy_version8_uses_shared_engine():
    ap = argparse.ArgumentParser()
    sim.add_csv_strategy_arg(ap)
    sim.add_strategy6_ratio_args(ap)
    args = ap.parse_args(["--strategy", "version8"])
    kw = sim.csv_run_kwargs_from_args(args)
    assert kw["strategy"] == "version8"
    hooks = sim.apply_csv_strategy(**kw)
    assert hooks["stop_pct"] == pytest.approx(0.15)
    assert hooks["take_profit"] is not None


def test_strategy6_ratio_args_parse():
    ap = argparse.ArgumentParser()
    sim.add_strategy6_ratio_args(ap)
    kw = sim.strategy6_kwargs_from_args(ap.parse_args([]))
    assert kw["stop_pct"] == sim.STOP_PCT
    assert kw["profit_base"] == sim.PROFIT_BASE
    assert kw["tiers"] == {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
    assert kw["tier_default"] == pytest.approx(0.70)
    kw = sim.strategy6_kwargs_from_args(
        ap.parse_args(["--stop-pct", "0.03", "--profit-base", "0.02", "--trail-t1", "0.6"])
    )
    assert kw["stop_pct"] == pytest.approx(0.03)
    assert kw["profit_base"] == pytest.approx(0.02)
    assert kw["tiers"][1] == pytest.approx(0.6)


def test_gap_open_stop_fills_at_open():
    rows = {
        "600000.SH": [
            (10.0, 10.0, 10.0, 10.0),
            (9.4, 9.5, 9.3, 9.35),
            (9.3, 9.4, 9.2, 9.3),
            (9.3, 9.3, 9.2, 9.25),
            (9.2, 9.3, 9.1, 9.2),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows), stop_pct=0.04)
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "stop_loss:gap_open"
    assert sell["price"] == pytest.approx(9.4)


def test_trail_t1_fires_and_exits_next_open():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.05, 10.50, 10.0, 10.218),  # 锚 1% 后超额 1.18% <= T+1 档 1.20% → 触发
            (10.33, 10.35, 10.2, 10.25),
            (10.2, 10.3, 10.1, 10.2),
            (10.2, 10.25, 10.1, 10.15),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "trail:T+1"
    assert sell["date"] == "20251105"
    assert sell["price"] == pytest.approx(10.33)


def test_trail_t2_fires_when_above_t1_threshold():
    # 峰值 10.50（锚 1% 后超额 4%）：T+1 线超额 2%→10.30；T+2 线超额 1.6%→10.26
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.05, 10.50, 10.0, 10.302),  # T+1 超额 2.02% > 2.00% → 不触发
            (10.34, 10.40, 10.30, 10.258),  # T+2 超额 1.58% <= 1.60% → 触发
            (10.30, 10.32, 10.20, 10.22),
            (10.20, 10.25, 10.10, 10.15),
        ]
    }
    st = _run(
        {"20251103": ["600000.SH"]},
        _bars(DAYS, rows),
        tiers={1: 0.50, 2: 0.40},
        tier_default=0.30,
    )
    assert st.stats["sell_trail"] == 1
    sell = [t for t in st.trades if t["side"] == "SELL"][0]
    assert sell["reason"] == "trail:T+2"
    assert sell["date"] == "20251106"
    assert sell["price"] == pytest.approx(10.30)


def test_no_trail_when_close_below_cost():
    # 峰值已过锚，公式会火，但收盘 < 成本 → 不止盈
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.95, 10.0),
            (10.05, 10.50, 9.80, 9.95),  # T+1 收盘 < 成本，公式会火但不止盈
            (10.40, 10.45, 10.30, 10.40),  # 之后站上各档线
            (10.40, 10.45, 10.30, 10.40),
            (10.40, 10.45, 10.30, 10.40),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 0
    assert st.stats["sell_stop"] == 0


def test_trail_hits_helper():
    assert not sim.trail_hits(9.95, 10.0, 10.50, 0.01, 0.30)
    assert sim.trail_hits(10.00, 10.0, 10.50, 0.01, 0.30)
    assert sim.trail_hits(10.218, 10.0, 10.50, 0.01, 0.30)
    assert not sim.trail_hits(10.222, 10.0, 10.50, 0.01, 0.30)
    assert sim.peak_gap_blocks(14)
    assert not sim.peak_gap_blocks(15)
    assert not sim.peak_gap_blocks(-90)


def test_no_trail_when_peak_not_above_1pct_anchor():
    rows = {
        "600000.SH": [
            (10.0, 10.05, 9.98, 10.0),
            (10.02, 10.009, 10.0, 10.005),  # 峰值未过 +1%
            (10.03, 10.006, 9.9, 9.95),
            (9.95, 10.0, 9.85, 9.9),
            (9.9, 9.95, 9.81, 9.85),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 0
    assert st.stats["sell_pos_trail"] == 0


def test_entry_day_high_does_not_set_peak():
    # D0 high=10.50 发生在收盘买入之前，不得计入峰值。
    # 若误用 D0 high：D1 close=10.005 相对 10.50 会立刻触发锚定回撤。
    # 正确：峰值从 10.0 起，后续 high 未过 +1% 锚 → 不止盈。
    rows = {
        "600000.SH": [
            (10.0, 10.50, 9.95, 10.0),
            (10.00, 10.009, 9.99, 10.005),
            (10.00, 10.008, 9.99, 10.002),
            (10.00, 10.007, 9.99, 10.001),
            (10.00, 10.006, 9.99, 10.000),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["sell_trail"] == 0
    assert st.stats["sell_pos_trail"] == 0
    assert any(t["side"] == "EOD_MARK" for t in st.trades)


def test_limit_up_close_skips_then_abandons_when_close_below_open():
    # D0 收盘涨停跳过；D1 收盘 11.05 < 开盘 11.20 → 弃买（日线近似 09:45）。
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


def test_later_pool_day_still_buys_after_chase_abandon():
    rows = {
        "600000.SH": [
            (10.5, 11.0, 10.5, 11.0),
            (11.30, 11.40, 10.90, 11.10),  # 收盘<开盘 → 弃买
            (11.2, 11.4, 11.0, 11.1),
            (11.1, 11.3, 10.9, 11.0),
            (11.0, 11.2, 10.8, 10.9),
        ]
    }
    pool = {"20251103": ["600000.SH"], "20251104": ["600000.SH"]}
    st = _run(pool, _bars(DAYS, rows))
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_abandon"] == 1
    assert st.stats["buys"] == 1
    buy = [t for t in st.trades if t["side"] == "BUY"][0]
    assert buy["date"] == "20251104"
    assert buy["reason"] == "pool"
    assert buy["price"] == pytest.approx(11.1)


def test_quota_split_evenly_across_pool_names():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.05, 9.9, 9.95),
            (9.95, 10.0, 9.8, 9.85),
            (9.8, 9.9, 9.7, 9.8),
            (9.8, 9.85, 9.6, 9.7),
        ],
        "000001.SZ": [
            (60.0, 60.5, 59.5, 60.0),
            (60.0, 61.0, 59.8, 60.5),
            (60.5, 61.0, 59.5, 59.8),
            (59.8, 60.0, 59.0, 59.5),
            (59.5, 60.0, 59.0, 59.2),
        ],
    }
    bars = _bars(DAYS, rows)
    pre = bars["000001.SZ"].index[0]
    bars["000001.SZ"].loc[pre] = 60.0  # 昨收须与股价同量级，否则 ≥涨停 会误拦
    st = _run(
        {"20251103": ["600000.SH", "000001.SZ"]},
        bars,
        daily_quota=1_000_000.0,
    )
    buys = {t["code"]: t for t in st.trades if t["side"] == "BUY"}
    assert set(buys) == {"600000.SH", "000001.SZ"}
    assert buys["600000.SH"]["shares"] == 50000
    assert buys["000001.SZ"]["shares"] == 8300


def test_quota_resets_every_trading_day():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.05, 9.95, 10.0),
            (10.0, 10.05, 9.9, 9.95),
            (9.95, 10.0, 9.8, 9.9),
            (9.9, 9.95, 9.7, 9.8),
        ],
        "000001.SZ": [
            (20.0, 20.2, 19.8, 20.0),
            (20.0, 20.1, 19.9, 20.0),
            (20.0, 20.1, 19.8, 19.9),
            (19.9, 20.0, 19.6, 19.7),
            (19.7, 19.8, 19.5, 19.6),
        ],
    }
    pool = {"20251103": ["600000.SH"], "20251104": ["000001.SZ"]}
    st = _run(pool, _bars(DAYS, rows), daily_quota=1_000_000.0)
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert {t["code"] for t in buys} == {"600000.SH", "000001.SZ"}
    assert {t["date"] for t in buys} == {"20251103", "20251104"}


def test_at_limit_is_equality_not_below():
    assert sim._at_limit(11.0, 11.0)
    assert not sim._at_limit(10.5, 11.0)
    assert sim._at_limit(9.0, 9.0)
    assert not sim._at_limit(10.99, 11.0)


def test_round_fen_half_up_not_banker():
    # 昨收 3.75 × 1.1 = 4.125 → 交易所 4.13；Python round 会得到 4.12
    up, down = sim._limit_prices("000592.SZ", 3.75)
    assert up == pytest.approx(4.13)
    assert down == pytest.approx(3.38)
    assert sim.round_fen(4.125) == pytest.approx(4.13)


def test_hit_limit_up_at_or_above():
    assert sim.hit_limit_up(4.13, 4.13)
    assert sim.hit_limit_up(4.13, 4.12)  # 买价高于算出的涨停，更不能买
    assert not sim.hit_limit_up(4.11, 4.13)
    assert sim.hit_limit_down(3.38, 3.38)
    assert sim.hit_limit_down(3.37, 3.38)
    assert not sim.hit_limit_down(3.39, 3.38)


def test_limit_up_skip_when_close_above_computed_limit():
    # 000592 形态：昨收 3.75，当日收 4.13。即使涨停价被算成 4.12 也必须跳过。
    rows = {
        "000592.SZ": [
            (3.78, 4.13, 3.71, 4.13),
            (4.60, 4.62, 4.40, 4.50),  # 收盘<开盘 → 弃买，本用例只锁 T+0 涨停跳过
            (4.54, 4.55, 4.40, 4.50),
            (4.50, 4.52, 4.40, 4.45),
            (4.45, 4.48, 4.30, 4.40),
        ]
    }
    bars = _bars(DAYS, rows)
    # 预热日 close 默认 10.0，改成昨收 3.75
    pre = bars["000592.SZ"].index[0]
    bars["000592.SZ"].loc[pre, "close"] = 3.75
    st = _run({"20251103": ["000592.SZ"]}, bars)
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["buys"] == 0


def test_load_pool_days_reads_utf8_without_qmt_logger(tmp_path):
    p = tmp_path / "20251103.csv"
    p.write_text("000001,平安银行\n600000,浦发银行\n", encoding="utf-8", newline="\n")
    days = sim.load_pool_days("20251103", "20251103", pool_dir=tmp_path)
    assert days["20251103"] == ["000001.SZ", "600000.SH"]


def test_summarize_engine_tag_and_timings():
    st = sim.SimState()
    st.equity_curve = [("20251103", 21_000_000.0)]
    st.stats["t_sim_s"] = 1.25
    st.stats["cache"] = "hit"
    text = sim.summarize(
        st, 21_000_000.0, "20251103", "20251103", engine="csv_minute_v6"
    )
    assert text.startswith("csv_minute_v6 20251103..20251103")
    assert "参数:" not in text
    st.stats["stop_pct"] = 0.02
    st.stats["profit_base"] = 0.01
    st.stats["trail_t1"] = 0.30
    st.stats["trail_t2"] = 0.40
    st.stats["trail_t3"] = 0.50
    st.stats["trail_t4"] = 0.60
    st.stats["trail_t5"] = 0.70
    text = sim.summarize(
        st, 21_000_000.0, "20251103", "20251103", engine="csv_minute_v6"
    )
    assert "参数: 止损 2%" in text
    assert "T+5+ 70%" in text
    assert "缓存 hit" in text
    assert "模拟 1.3s" in text or "模拟 1.2s" in text


def test_write_run_artifacts_three_files(tmp_path):
    st = sim.SimState()
    st.equity_curve = [("20251103", 21_000_000.0)]
    st.trades.append(
        {
            "date": "20251103",
            "code": "600000.SH",
            "side": "BUY",
            "price": 10.0,
            "shares": 100,
            "notional": 1000.0,
            "commission": 1.0,
        }
    )
    out = sim.write_run_artifacts(tmp_path / "run", st, "hello", "lock\n")
    assert (out / "summary.txt").read_text(encoding="utf-8").startswith("hello")
    assert (out / "daily_equity.csv").is_file()
    assert (out / "trades.csv").is_file()


def test_format_equity_compare_overlap(tmp_path):
    peer = tmp_path / "daily_equity.csv"
    peer.write_text(
        "date,equity\n20251103,21000000\n20251104,21100000\n",
        encoding="utf-8",
        newline="\n",
    )
    curve = [("20251103", 20_900_000.0), ("20251104", 20_950_000.0)]
    text = sim.format_equity_compare(curve, peer, this_label="csv_minute_v6")
    assert "重叠 2 日" in text
    assert "20251104" in text
    assert "none 成交价" in text


def test_find_daily_equity_prefers_covering_end(tmp_path):
    a = tmp_path / "csv_daily_v6_20251023_20251104"
    b = tmp_path / "csv_daily_v6_20251023_20260909"
    a.mkdir()
    b.mkdir()
    (a / "daily_equity.csv").write_text("date,equity\n20251104,1\n", encoding="utf-8")
    (b / "daily_equity.csv").write_text("date,equity\n20260525,1\n", encoding="utf-8")
    got = sim.find_daily_equity_csv("20251023", "20260525", output_root=tmp_path)
    assert got is not None
    assert got.parent.name.endswith("20260909")
