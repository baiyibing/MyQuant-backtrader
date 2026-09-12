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
    kwargs.setdefault("strategy", "version6")
    return sim.simulate(bars, pool, "20251103", "20251107", **kwargs)


def _write_daily_lake_frame(tmp_path, code: str, frame: pd.DataFrame) -> None:
    partition = tmp_path / f"symbol={sim.to_partition_key(code)}"
    partition.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(partition / "data.parquet", index=False)


def _daily_time_ms(*dates: str) -> list[int]:
    return [int(pd.Timestamp(date, tz="UTC").timestamp() * 1000) for date in dates]


def _v4_bars(prior_closes, rows):
    prior_idx = pd.bdate_range(end="2025-10-31", periods=len(prior_closes))
    trade_idx = pd.to_datetime(DAYS[: len(rows)])
    closes = list(prior_closes) + [r[3] for r in rows]
    return {"600000.SH": pd.DataFrame({
        "open": list(prior_closes) + [r[0] for r in rows],
        "high": list(prior_closes) + [r[1] for r in rows],
        "low": list(prior_closes) + [r[2] for r in rows],
        "close": closes,
    }, index=prior_idx.append(trade_idx)).astype(np.float64)}


def test_read_one_daily_drops_zero_volume_rows(tmp_path):
    _write_daily_lake_frame(
        tmp_path,
        "600000.SH",
        pd.DataFrame(
            {
                "time": _daily_time_ms("2025-11-03", "2025-11-04"),
                "open": [10.0, 0.0],
                "high": [10.1, 0.0],
                "low": [9.9, 0.0],
                "close": [10.0, 0.0],
                "volume": [1000.0, 0.0],
            }
        ),
    )

    got = sim._read_one_daily("600000.SH", tmp_path, "20251103", "20251104")

    assert got is not None
    assert list(got.index) == [pd.Timestamp("2025-11-03")]
    assert list(got.columns) == ["open", "high", "low", "close"]


def test_read_one_daily_without_volume_keeps_original_behavior(tmp_path):
    _write_daily_lake_frame(
        tmp_path,
        "600000.SH",
        pd.DataFrame(
            {
                "time": _daily_time_ms("2025-11-03", "2025-11-04"),
                "open": [10.0, 10.1],
                "high": [10.1, 10.2],
                "low": [9.9, 10.0],
                "close": [10.0, 10.1],
            }
        ),
    )

    got = sim._read_one_daily("600000.SH", tmp_path, "20251103", "20251104")

    assert got is not None
    assert list(got.index) == [
        pd.Timestamp("2025-11-03"),
        pd.Timestamp("2025-11-04"),
    ]
    assert list(got["close"]) == [10.0, 10.1]


def test_strategy4_sma10_blocks_buy_and_counts_gate():
    bars = _v4_bars([10.0] * 10, [(9.0, 9.0, 9.0, 9.0)])
    st = sim.simulate(bars, {"20251103": ["600000.SH"]}, "20251103", "20251103", strategy="version4")
    assert st.stats["buys"] == 0
    assert st.stats["skip_buy_gate"] == 1
    assert st.stats["skip_sma_warmup"] == 0


def test_strategy4_starved_sma10_counts_warmup():
    bars = _v4_bars([10.0] * 9, [(10.0, 10.0, 10.0, 10.0)])
    st = sim.simulate(bars, {"20251103": ["600000.SH"]}, "20251103", "20251103", strategy="version4")
    assert st.stats["skip_buy_gate"] == 1
    assert st.stats["skip_sma_warmup"] == 1


def test_strategy4_ma5_break_becomes_next_open_exit():
    rows = [(10, 10, 10, 10), (10, 10, 9, 9), (9.1, 9.1, 9.1, 9.1)]
    bars = _v4_bars([10.0] * 10, rows)
    st = sim.simulate(bars, {"20251103": ["600000.SH"]}, "20251103", "20251105", strategy="version4")
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert sells[0]["date"] == "20251105"
    assert sells[0]["price"] == pytest.approx(9.1)
    assert sells[0]["reason"] == "ma_signal:MA5"


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
    sell4 = [t for t in _run(pool, bars, stop_pct=0.04).trades if t["side"] == "SELL"][
        0
    ]
    assert sell4["reason"] == "stop_loss:touch"
    assert sell4["price"] == pytest.approx(9.6)
    sell2 = [t for t in _run(pool, bars, stop_pct=0.02).trades if t["side"] == "SELL"][
        0
    ]
    assert sell2["reason"] == "stop_loss:gap_open"
    assert sell2["price"] == pytest.approx(9.70)


def test_none_stop_short_circuits_even_after_price_halves(monkeypatch):
    def no_stop_hooks(_strategy, **_kwargs):
        def record(st):
            st.stats.update(
                stop_pct=None,
                sell_book="v6",
                profit_base=0.01,
                trail_t1=0.5,
                trail_t2=0.4,
                trail_t3=0.3,
                trail_t4=0.2,
                trail_t5=0.1,
            )

        return {
            "stop_pct": None,
            "take_profit": lambda *_args: None,
            "record_params": record,
            "allow_add": False,
        }

    monkeypatch.setattr(sim, "apply_csv_strategy", no_stop_hooks)
    rows = {"600000.SH": [(10, 10, 10, 10)] + [(5, 5, 5, 5)] * 4}
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert not [
        trade
        for trade in st.trades
        if trade.get("reason", "").startswith("stop_loss:")
    ]
    assert "止损 关闭" in sim.summarize(st, 21_000_000, "20251103", "20251107")


def test_strategy5_daily_target_sells_next_open_without_force_reason():
    rows = {
        "600000.SH": [
            (10.0, 10.0, 10.0, 10.0),
            (10.1, 10.3, 10.1, 10.2),
            (10.3, 10.3, 10.3, 10.3),
            (10.3, 10.3, 10.3, 10.3),
            (10.3, 10.3, 10.3, 10.3),
        ]
    }
    st = _run(
        {"20251103": ["600000.SH"]},
        _bars(DAYS, rows),
        strategy="version5",
    )
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["date"] == "20251105"
    assert sells[0]["price"] == pytest.approx(10.3)
    assert sells[0]["reason"] == "profit_take:target"
    assert not any(t["reason"].startswith("force_sell") for t in sells)


def test_strategy3_daily_limit_up_close_suppresses_twenty_percent_target():
    rows = {"300001.SZ": [
        (10.0, 10.0, 10.0, 10.0),
        (12.0, 12.0, 12.0, 12.0),
        (14.4, 14.4, 14.4, 14.4),
        (17.28, 17.28, 17.28, 17.28),
        (20.74, 20.74, 20.74, 20.74),
    ]}
    st = _run({"20251103": ["300001.SZ"]}, _bars(DAYS, rows), strategy="version3")
    assert not [trade for trade in st.trades if trade["side"] == "SELL"]
    assert st.positions["300001.SZ"][0].reserved is True
    assert st.positions["300001.SZ"][0].pending_exit == ""


def test_strategy3_daily_open_board_sells_same_close():
    rows = {"300001.SZ": [
        (10.0, 10.0, 10.0, 10.0),
        (12.0, 12.0, 10.8, 11.8),
        (11.8, 11.8, 11.8, 11.8),
        (11.8, 11.8, 11.8, 11.8),
        (11.8, 11.8, 11.8, 11.8),
    ]}
    st = _run({"20251103": ["300001.SZ"]}, _bars(DAYS, rows), strategy="version3")
    sell = [trade for trade in st.trades if trade["side"] == "SELL"][0]
    assert sell["date"] == "20251104"
    assert sell["price"] == pytest.approx(11.8)
    assert sell["reason"] == "open_board"


def test_strategy3_daily_open_board_limit_down_defers_to_next_open():
    rows = {"300001.SZ": [
        (10.0, 10.0, 10.0, 10.0),
        # Synthetic low keeps the earlier stop clock from winning this U-R20 case.
        (12.0, 12.0, 10.0, 8.0),
        (8.2, 8.2, 8.2, 8.2),
        (8.2, 8.2, 8.2, 8.2),
        (8.2, 8.2, 8.2, 8.2),
    ]}
    st = _run({"20251103": ["300001.SZ"]}, _bars(DAYS, rows), strategy="version3")
    sell = [trade for trade in st.trades if trade["side"] == "SELL"][0]
    assert sell["date"] == "20251105"
    assert sell["price"] == pytest.approx(8.2)
    assert sell["reason"] == "open_board"


@pytest.mark.parametrize(
    ("reason", "bucket"),
    [
        ("profit_take:target", "sell_profit_take"),
        ("open_board", "sell_open_board"),
        ("force_sell:time", "sell_force"),
        ("ma_signal:MA5", "sell_ma"),
    ],
)
def test_named_sell_reasons_have_dedicated_buckets(reason, bucket):
    st = sim.SimState()
    pos = sim.Position("600000.SH", 100, 10.0, 0, 10.0)
    st.positions[pos.code] = [pos]
    sim._sell(st, pos.code, pos, 10.0, pd.Timestamp("2025-11-04"), reason)
    assert st.stats[bucket] == 1
    assert st.stats["sell_trail"] == 0
    assert st.stats["sell_pos_trail"] == 0


def test_csv_strategy_arg_is_required():
    ap = argparse.ArgumentParser()
    sim.add_csv_strategy_arg(ap)
    with pytest.raises(SystemExit):
        ap.parse_args([])


def test_csv_strategy_version8_uses_shared_engine():
    ap = argparse.ArgumentParser()
    sim.add_csv_strategy_arg(ap)
    sim.add_strategy6_ratio_args(ap)
    args = ap.parse_args(["--strategy", "version8"])
    kw = sim.csv_run_kwargs_from_args(args)
    assert kw["strategy"] == "version8"
    hooks = sim.apply_csv_strategy(**kw)
    assert hooks["stop_pct"] == pytest.approx(0.20)
    assert hooks["take_profit"] is not None
    assert hooks["allow_add"] is True
    assert hooks["book"] == "v8"


def test_strategy6_ratio_args_parse():
    ap = argparse.ArgumentParser()
    sim.add_strategy6_ratio_args(ap)
    kw = sim.strategy6_kwargs_from_args(ap.parse_args([]))
    assert kw["stop_pct"] == sim.STOP_PCT
    assert kw["profit_base"] == sim.PROFIT_BASE
    assert kw["tiers"] == {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
    assert kw["tier_default"] == pytest.approx(0.70)
    kw = sim.strategy6_kwargs_from_args(
        ap.parse_args(
            ["--stop-pct", "0.03", "--profit-base", "0.02", "--trail-t1", "0.6"]
        )
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
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


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
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]
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
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


def test_chase_pending_eod_on_last_calendar_day():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (10.5, 11.0, 10.5, 11.0),
        ]
    }
    st = _run({"20251107": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_pending_eod"] == 1
    assert st.stats["chase_buy"] == 0
    assert st.stats["chase_abandon"] == 0
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


def test_chase_overwrite_same_day_duplicate_pool():
    rows = {
        "600000.SH": [
            (10.5, 11.0, 10.5, 11.0),
            (11.20, 11.30, 10.90, 11.05),
            (11.0, 11.2, 10.8, 10.9),
            (10.9, 11.0, 10.7, 10.8),
            (10.8, 10.9, 10.6, 10.7),
        ]
    }
    st = _run({"20251103": ["600000.SH", "600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["skip_limit_up"] == 2
    assert st.stats["chase_overwrite"] == 1
    assert st.stats["chase_abandon"] == 1
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


def test_chase_skip_limit_when_t1_still_limit_up():
    rows = {
        "600000.SH": [
            (10.5, 11.0, 10.5, 11.0),
            (12.00, 12.10, 11.80, 12.10),
            (12.1, 12.2, 11.9, 12.0),
            (12.0, 12.1, 11.8, 11.9),
            (11.9, 12.0, 11.7, 11.8),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows))
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_skip_limit"] == 1
    assert st.stats["buys"] == 0
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


def test_chase_no_bar_when_t1_missing():
    rows = {
        "600000.SH": [
            (10.5, 11.0, 10.5, 11.0),
            (11.20, 11.30, 10.90, 11.05),
            (11.0, 11.2, 10.8, 10.9),
            (10.9, 11.0, 10.7, 10.8),
            (10.8, 10.9, 10.6, 10.7),
        ],
        "000001.SZ": [
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
        ],
    }
    bars = _bars(DAYS, rows)
    bars["600000.SH"] = bars["600000.SH"].drop(pd.Timestamp("2025-11-04"))
    st = _run({"20251103": ["600000.SH"]}, bars)
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_no_bar"] == 0
    assert st.stats["chase_abandon"] == 1
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


def test_chase_buy_fail_when_cash_short():
    rows = {
        "600000.SH": [
            (10.5, 11.0, 10.5, 11.0),
            (11.00, 11.40, 10.90, 11.20),
            (11.2, 11.3, 11.0, 11.1),
            (11.1, 11.2, 10.9, 11.0),
            (11.0, 11.1, 10.8, 10.9),
        ]
    }
    st = _run({"20251103": ["600000.SH"]}, _bars(DAYS, rows), total_cash=50.0)
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_buy_fail"] == 1
    assert st.stats["chase_buy"] == 0
    assert st.stats["buys"] == 0
    assert sim.chase_explained(st) == st.stats["skip_limit_up"]


def test_summarize_prints_chase_breakdown():
    st = sim.SimState()
    st.equity_curve = [("20251103", 21_000_000.0)]
    st.stats["skip_limit_up"] = 10
    st.stats["chase_buy"] = 3
    st.stats["chase_abandon"] = 2
    st.stats["chase_skip_limit"] = 1
    st.stats["chase_no_bar"] = 1
    st.stats["chase_pending_eod"] = 1
    st.stats["chase_overwrite"] = 1
    st.stats["chase_buy_fail"] = 1
    text = sim.summarize(
        st, 21_000_000.0, "20251103", "20251103", engine="csv_daily_v8"
    )
    assert "涨停分解:" in text
    assert "合计 10 / 涨停跳过 10" in text


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
    got = sim.find_daily_equity_csv(
        "20251023", "20260525", output_root=tmp_path, book="v6"
    )
    assert got is not None
    assert got.parent.name.endswith("20260909")


def test_unknown_board_skips_buy():
    rows = {"159001.SZ": [(10.0, 10.1, 9.9, 10.0)] * 5}
    st = _run({"20251103": ["159001.SZ"]}, _bars(DAYS, rows))
    assert st.stats["skip_unknown_board"] == 1
    assert st.stats["buys"] == 0


def test_st_name_uses_five_percent_limit_up():
    rows = {
        "600000.SH": [
            (10.5, 10.5, 10.4, 10.5),
            (10.4, 10.5, 10.3, 10.4),
            (10.3, 10.4, 10.2, 10.3),
            (10.2, 10.3, 10.1, 10.2),
            (10.1, 10.2, 10.0, 10.1),
        ]
    }
    bars = _bars(DAYS, rows)
    pool = {"20251103": ["600000.SH"]}
    blocked = sim.simulate(
        bars, pool, "20251103", "20251107", strategy="version6",
        pool_names={"600000.SH": "*ST 宁科"},
    )
    assert blocked.stats["skip_limit_up"] == 1
    assert blocked.stats["buys"] == 0
    allowed = _run(pool, bars)
    assert allowed.stats["buys"] == 1


def test_pool_name_asof_missing_held_code_falls_back_to_yesterday():
    rows = {
        "600000.SH": [
            (10.0, 10.0, 10.0, 10.0),
            (9.39, 9.39, 9.39, 9.39),
        ]
    }
    bars = _bars(DAYS[:2], rows)

    st = sim.simulate(
        bars,
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        strategy="version6",
        pool_names_by_day={
            "20251103": {"600000.SH": "*ST 浦发"},
            "20251104": {"000001.SZ": "平安"},
        },
    )

    assert st.stats["defer_sell_limit_down"] == 1
    assert not any(trade["side"] == "SELL" for trade in st.trades)


def test_pool_name_asof_future_st_does_not_change_earlier_limit():
    rows = {
        "600000.SH": [
            (10.0, 10.0, 10.0, 10.0),
            (10.5, 10.5, 10.5, 10.5),
            (10.5, 10.5, 10.5, 10.5),
        ]
    }
    bars = _bars(DAYS[:3], rows)

    st = sim.simulate(
        bars,
        {"20251104": ["600000.SH"]},
        "20251103",
        "20251105",
        strategy="version6",
        pool_names_by_day={"20251105": {"600000.SH": "*ST 浦发"}},
    )

    assert st.stats["buys"] == 1
    assert st.stats["skip_limit_up"] == 0


def test_bj_thirty_percent_allows_close_that_would_be_ten_percent_limit():
    rows = {"920014.BJ": [(12.5, 12.5, 12.4, 12.5)] * 5}
    st = _run({"20251103": ["920014.BJ"]}, _bars(DAYS, rows))
    assert st.stats["buys"] == 1
    assert st.stats["skip_limit_up"] == 0


def test_halt_day_equity_uses_last_close_not_cost():
    rows = {
        "600000.SH": [
            (10.0, 10.1, 9.9, 10.0),
            (11.0, 11.2, 10.8, 11.0),
            (11.0, 11.1, 10.9, 11.0),
            (11.0, 11.1, 10.9, 11.0),
            (11.0, 11.1, 10.9, 11.0),
        ],
        "000001.SZ": [
            (20.0, 20.1, 19.9, 20.0),
            (20.0, 20.1, 19.9, 20.0),
            (20.0, 20.1, 19.9, 20.0),
            (20.0, 20.1, 19.9, 20.0),
            (20.0, 20.1, 19.9, 20.0),
        ],
    }
    bars = _bars(DAYS, rows)
    bars["600000.SH"] = bars["600000.SH"].drop(pd.Timestamp("2025-11-05"))
    st = _run({"20251103": ["600000.SH"]}, bars)
    cash = 21_000_000.0 - 1_001_000.0
    eq = dict(st.equity_curve)
    assert eq["20251105"] == pytest.approx(cash + 100_000 * 11.0)
    assert eq["20251105"] != pytest.approx(cash + 100_000 * 10.0)


def test_zero_volume_placeholder_day_cannot_sell_or_buy_and_marks_last_close(
    tmp_path,
):
    common_time = _daily_time_ms("2025-10-31", "2025-11-03", "2025-11-04")
    _write_daily_lake_frame(
        tmp_path,
        "600000.SH",
        pd.DataFrame(
            {
                "time": common_time,
                "open": [10.0, 10.0, 5.0],
                "high": [10.0, 10.1, 99.0],
                "low": [10.0, 9.9, 1.0],
                "close": [10.0, 10.0, 99.0],
                "volume": [1000.0, 1000.0, 0.0],
            }
        ),
    )
    _write_daily_lake_frame(
        tmp_path,
        "600001.SH",
        pd.DataFrame(
            {
                "time": common_time,
                "open": [20.0, 20.0, 18.0],
                "high": [20.0, 20.1, 18.0],
                "low": [20.0, 19.9, 18.0],
                "close": [20.0, 20.0, 18.0],
                "volume": [1000.0, 1000.0, 0.0],
            }
        ),
    )
    held = sim._read_one_daily("600000.SH", tmp_path, "20251031", "20251104")
    candidate = sim._read_one_daily(
        "600001.SH", tmp_path, "20251031", "20251104"
    )
    assert held is not None and candidate is not None
    calendar_anchor = pd.DataFrame(
        {
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
        },
        index=pd.to_datetime(["2025-11-03", "2025-11-04"]),
    )

    st = sim.simulate(
        {
            "600000.SH": held,
            "600001.SH": candidate,
            "000001.SZ": calendar_anchor,
        },
        {"20251103": ["600000.SH"], "20251104": ["600001.SH"]},
        "20251103",
        "20251104",
        strategy="version6",
        stop_pct=0.02,
    )

    assert not any(trade["side"] == "SELL" for trade in st.trades)
    assert not any(
        trade["side"] == "BUY" and trade["code"] == "600001.SH"
        for trade in st.trades
    )
    assert st.stats["skip_no_bar"] == 1
    pos = st.positions["600000.SH"][0]
    equity = dict(st.equity_curve)["20251104"]
    assert equity == pytest.approx(st.cash + pos.shares * 10.0)
    assert equity != pytest.approx(st.cash + pos.shares * 99.0)


def test_zero_volume_placeholder_chase_day_stays_pending(tmp_path):
    _write_daily_lake_frame(
        tmp_path,
        "600000.SH",
        pd.DataFrame(
            {
                "time": _daily_time_ms(
                    "2025-10-31", "2025-11-03", "2025-11-04"
                ),
                "open": [10.0, 10.5, 11.0],
                "high": [10.0, 11.0, 11.0],
                "low": [10.0, 10.5, 10.0],
                "close": [10.0, 11.0, 10.0],
                "volume": [1000.0, 1000.0, 0.0],
            }
        ),
    )
    target = sim._read_one_daily("600000.SH", tmp_path, "20251031", "20251104")
    assert target is not None
    calendar_anchor = pd.DataFrame(
        {
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
        },
        index=pd.to_datetime(["2025-11-03", "2025-11-04"]),
    )

    st = sim.simulate(
        {"600000.SH": target, "000001.SZ": calendar_anchor},
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        strategy="version6",
    )

    assert st.stats["skip_limit_up"] == 1
    assert st.stats["chase_pending_eod"] == 1
    assert st.stats["buys"] == 0


def test_pre_er1_trades_snapshot_exists():
    from pathlib import Path

    root = Path(__file__).resolve().parent / "fixtures" / "csv_engine_pre_er1"
    assert (root / "version6_trades.csv").is_file()
    assert (root / "version8_trades.csv").is_file()
