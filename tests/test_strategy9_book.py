# -*- coding: utf-8 -*-
"""策略 9 书：止损 / 满持有 / 拒绝默认 stock_pool。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_daily_backtest as sim
from backtest.research.csv_strategy_books import (
    apply_csv_strategy,
    get_book,
    resolve_research_pool_dir,
)
from backtest.research.strategy9_rules import (
    MAX_HOLD,
    stop_range_amplitude,
    stop_mean_true_range_distance,
    record_strategy9_params,
    take_profit_reason,
)


@pytest.mark.parametrize("enabled", [False, True])
def test_version9_hooks_and_max_hold(enabled):
    hooks = apply_csv_strategy("version9", max_hold=enabled)
    assert hooks["name"] == "version9"
    assert hooks["book"] == "v9"
    assert hooks["allow_add"] is False
    assert hooks["peak_gap_min"] == 0
    assert hooks["stop_pct"] is None
    assert hooks["take_profit"](10.0, 10.0, 10.0, MAX_HOLD - 1) is None
    assert hooks["take_profit"](10.0, 10.0, 10.0, MAX_HOLD) == ("force_sell:max_hold" if enabled else None)
    assert take_profit_reason(1, 1, 1, MAX_HOLD, max_hold=enabled) == ("force_sell:max_hold" if enabled else None)
    assert hooks["take_profit"](11., 10., 11., MAX_HOLD) == "profit_take:target"
    assert get_book("9").tag == "v9"
    assert get_book("v9").name == "version9"


def test_version9_take_profit_target_and_params():
    take_profit = apply_csv_strategy("version9")["take_profit"]
    assert take_profit(11.0, 10.0, 99.0, 1) == "profit_take:target"
    assert take_profit(10.99, 10.0, 99.0, MAX_HOLD - 1) is None
    assert take_profit(11.0, 10.0, 99.0, 0) is None
    assert take_profit(11.0, 10.0, 99.0, MAX_HOLD) == "profit_take:target"
    st = SimpleNamespace(stats={})
    record_strategy9_params(st)
    assert st.stats == {
        "sell_book": "v9",
        "stop_pct": None,
        "stop_mode": "atr20_daily_initial_2atr_arm_1atr_trail_2atr",
        "range_bars": 20,
        "profit_target": 0.10,
        "max_hold": None,
    }


def test_version9_refuses_default_and_repo_stock_pool(tmp_path):
    repo = tmp_path / "repo"
    (repo / "stock_pool").mkdir(parents=True)
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version9", None, repo=repo)
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version9", repo / "stock_pool", repo=repo)
    dest = repo / "exports" / "s9"
    dest.mkdir(parents=True)
    assert resolve_research_pool_dir("version9", dest, repo=repo) == dest
    default = resolve_research_pool_dir("version6", None, repo=repo)
    assert default == repo / "stock_pool"


def test_daily_cli_version9_refuses_stock_pool(monkeypatch):
    monkeypatch.setattr(
        sim, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("run"))
    )
    with pytest.raises(SystemExit, match="stock_pool"):
        sim.main(["--strategy", "version9", "--start", "20260303", "--end", "20260323"])


@pytest.mark.parametrize("host", ["daily", "minute"])
@pytest.mark.parametrize("enabled", [False, True])
def test_cli_version9_accepts_explicit_pool(tmp_path, monkeypatch, enabled, host):
    import backtest.research.csv_minute_backtest as minute
    cli = sim if host == "daily" else minute
    seen = {}

    def _run(*_a, **kwargs):
        seen.update(kwargs)
        st = sim.SimState(cash=21_000_000.0)
        st.equity_curve = [("20260303", 21_000_000.0)]
        st.stats["sell_book"] = "v9"
        st.stats["stop_pct"] = None
        return st

    monkeypatch.setattr(cli, "run", _run)
    dest = tmp_path / "s9"
    dest.mkdir()
    (dest / "20260303.csv").write_text("600000\n", encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    rc = cli.main(
        [
            "--strategy",
            "version9",
            "--start",
            "20260303",
            "--end",
            "20260323",
            "--pool-dir",
            str(dest),
            "--out-dir",
            str(out),
        ] + (["--max-hold"] if enabled else [])
    )
    assert seen["max_hold"] is enabled
    assert rc == 0
    assert Path(seen["pool_dir"]) == dest
    assert (out / "summary.txt").is_file()


@pytest.mark.parametrize("enabled", [False, True])
def test_version9_force_sells_after_max_hold(enabled):
    idx = pd.bdate_range("2025-11-03", periods=26)
    pre = pd.bdate_range(end=idx[0] - pd.Timedelta(days=1), periods=21)
    full = pre.append(idx)
    px = {
        "open": np.full(len(full), 10.0),
        "high": np.full(len(full), 10.1),
        "low": np.full(len(full), 9.9),
        "close": np.full(len(full), 10.0),
    }
    bars = {"600000.SH": pd.DataFrame(px, index=full).astype(np.float64)}
    start = idx[0].strftime("%Y%m%d")
    end = idx[-1].strftime("%Y%m%d")
    st = sim.simulate(
        bars,
        {start: ["600000.SH"]},
        start,
        end,
        strategy="version9",
        max_hold=enabled,
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["buys"] == 1
    assert st.stats["max_hold"] == (20 if enabled else None)
    if not enabled:
        assert sells == []
        return
    assert st.stats["sell_force"] == 1
    assert sells[0]["reason"] == "force_sell:max_hold"
    assert sells[0]["date"] == idx[MAX_HOLD + 1].strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(10.0)


def test_version9_take_profit_sells_next_open():
    idx = pd.bdate_range("2025-11-03", periods=8)
    pre = pd.bdate_range(end=idx[0] - pd.Timedelta(days=1), periods=21)
    full = pre.append(idx)
    px = {
        "open": np.full(len(full), 10.0),
        "high": np.full(len(full), 10.1),
        "low": np.full(len(full), 9.9),
        "close": np.full(len(full), 10.0),
    }
    bars = {"600000.SH": pd.DataFrame(px, index=full).astype(np.float64)}
    bars["600000.SH"].loc[idx[3], ["high", "close"]] = 11.0
    bars["600000.SH"].loc[idx[4], ["open", "high", "low", "close"]] = 10.5
    start = idx[0].strftime("%Y%m%d")
    end = idx[-1].strftime("%Y%m%d")
    st = sim.simulate(
        bars,
        {start: ["600000.SH"]},
        start,
        end,
        strategy="version9",
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["buys"] == 1
    assert st.stats["profit_target"] == pytest.approx(0.10)
    assert len(sells) == 1
    assert sells[0]["reason"] == "profit_take:target"
    assert sells[0]["date"] == idx[4].strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(10.5)


def range_frame():
    days = pd.bdate_range("2025-09-01", periods=24)
    frame = pd.DataFrame({"open": 10., "high": 10.1, "low": 9.9, "close": 10.}, index=days)
    frame.loc[days[1], "high"] = 12.
    return days, frame


def test_range_rolls_and_excludes_today():
    days, frame = range_frame()
    # On day 21: base day 0, window days 1..20. On day 22: base day 1, days 2..21.
    frame.loc[days[22], "high"] = 100.
    assert stop_mean_true_range_distance(frame, days[21]) == pytest.approx(2 * (2.1 + 19 * .2) / 20)
    assert stop_mean_true_range_distance(frame, days[22]) == pytest.approx(.4)


@pytest.mark.parametrize("engine", ["daily", "minute"])
def test_hosts_use_rolled_range(engine):
    from backtest.research.csv_minute_backtest import simulate as minute
    days, frame = range_frame()
    frame.loc[days[21], ["open", "high", "low", "close"]] = [10., 10.1, 9.7, 10.]
    frame.loc[days[22], ["open", "high", "low", "close"]] = [10., 10.1, 9.5, 10.]
    # Day 21 distance .59; day 22 distance .42 after day 21 range .4.
    start, end = days[20].strftime("%Y%m%d"), days[22].strftime("%Y%m%d")
    pool = {start: ["600000.SH"]}
    if engine == "daily":
        st = sim.simulate({"600000.SH": frame}, pool, start, end, strategy="version9")
    else:
        rows = []
        for day, row in frame.iterrows():
            for hm in (570, 895, 900):
                rows.append(dict(row, time=day + pd.Timedelta(minutes=hm), hm=hm, ymd=day.strftime("%Y%m%d")))
        minutes = pd.DataFrame(rows).set_index("time")
        st = minute({"600000.SH": minutes}, {"600000.SH": frame}, pool, start, end,
                    strategy="version9", minute_stop_trigger="hl")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["buys"] == 1
    assert len(sells) == 1
    assert sells[0]["date"] == end
    assert sells[0]["reason"] == "stop_loss:touch"
    assert sells[0]["price"] == pytest.approx(9.58)


@pytest.mark.parametrize("missing", ["short_history", "invalid_ohlc", "invalid_close"])
def test_missing_range_does_not_fallback(missing):
    days, frame = range_frame()
    frame.loc[days[21], ["open", "high", "low", "close"]] = [10., 10., 9.1, 9.3]
    if missing == "short_history":
        frame = frame.iloc[19:]
    elif missing == "invalid_ohlc":
        frame.loc[days[2], "high"] = float("nan")
    else:
        frame.loc[days[0], "close"] = float("inf")
        missing = "invalid_ohlc"
    start, end = days[20].strftime("%Y%m%d"), days[21].strftime("%Y%m%d")
    st = sim.simulate({"600000.SH": frame}, {start: ["600000.SH"]}, start, end, strategy="version9")
    assert st.stats["buys"] == 1
    assert not [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats[f"skip_stop_range:{missing}"] == 1


@pytest.mark.parametrize("ratio", [0., 1.2])
def test_unclamped_range(ratio):
    days, frame = range_frame()
    frame.loc[:, "high"] = 10. + ratio * 10.
    frame.loc[:, "low"] = 10.
    assert stop_mean_true_range_distance(frame, days[21]) == pytest.approx(2 * ratio * 10)
    start, end = days[20].strftime("%Y%m%d"), days[21].strftime("%Y%m%d")
    st = sim.simulate({"600000.SH": frame}, {start: ["600000.SH"]}, start, end, strategy="version9")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert bool(sells) == (ratio == 0.)


def test_other_book_keeps_stop():
    days, frame = range_frame()
    frame.loc[days[21], "low"] = 9.1
    start, end = days[20].strftime("%Y%m%d"), days[21].strftime("%Y%m%d")
    st = sim.simulate({"600000.SH": frame}, {start: ["600000.SH"]}, start, end,
                      strategy="version6", stop_pct=.08)
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells[0]["reason"] == "stop_loss:touch"
    assert sells[0]["price"] == pytest.approx(9.2)


@pytest.mark.parametrize("host", ["daily", "minute"])
def test_cli_refuses_stop_override(host, tmp_path):
    from backtest.research.csv_minute_backtest import main as minute_main
    with pytest.raises(SystemExit, match="stop-pct"):
        (sim.main if host == "daily" else minute_main)([
            "--strategy", "version9", "--start", "20260303", "--end", "20260323",
            "--pool-dir", str(tmp_path), "--stop-pct", "0.08"])


@pytest.mark.parametrize("host", ["daily", "minute"])
def test_cli_max_hold_help_and_refuse(host, capsys):
    from backtest.research.csv_minute_backtest import main as minute_main
    main = sim.main if host == "daily" else minute_main
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "--max-hold" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="--max-hold.*version9"):
        main(["--strategy", "version6", "--max-hold"])


@pytest.mark.parametrize("engine", ["daily", "minute", "wire"])
@pytest.mark.parametrize("low,stops", [(9.6, True), (9.8, False), (9.7, False)])
def test_twice_mean_touch_and_one_mean_survives(engine, low, stops):
    from backtest.research.csv_minute_backtest import simulate as minute
    from backtest.research.minute_true_core_wire import invoke_minute_strategy, OhlcBar
    days, frame = range_frame()
    frame["high"] = 10.1
    frame.loc[days[21], "low"] = low
    assert stop_mean_true_range_distance(frame, days[21]) == pytest.approx(.4)
    if engine == "wire":
        hit = invoke_minute_strategy("version9", OhlcBar(10., 10.1, low, 10.),
                                     cost=10., peak=10., daily_bars=frame, as_of=days[21])
        assert (hit.decision == "fill") is stops
        if stops:
            assert hit.fill_price == pytest.approx(9.6)
            assert hit.reason == "stop_loss:touch"
        return
    start, end = (days[i].strftime("%Y%m%d") for i in (20, 21))
    pool = {start: ["600000.SH"]}
    if engine == "daily":
        st = sim.simulate({"600000.SH": frame}, pool, start, end, strategy="version9")
    else:
        rows = [dict(row, time=day + pd.Timedelta(minutes=hm), hm=hm, ymd=day.strftime("%Y%m%d"))
                for day, row in frame.iterrows() for hm in (570, 895, 900)]
        st = minute({"600000.SH": pd.DataFrame(rows).set_index("time")},
                    {"600000.SH": frame}, pool, start, end, strategy="version9", minute_stop_trigger="hl")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert bool(sells) is stops
    if stops:
        assert sells[0]["price"] == pytest.approx(9.6)
        assert sells[0]["reason"] == "stop_loss:touch"


def test_version9_2_retains_amplitude_stop():
    from backtest.research.strategy9_2_rules import chosen_stop
    days, frame = range_frame()
    old_line = max(10 * .90, 10 * (1 - stop_range_amplitude(frame, days[21])))
    assert chosen_stop(10, frame, days[21]) == pytest.approx(old_line)
    assert chosen_stop(10, frame, days[21]) != pytest.approx(10 - stop_mean_true_range_distance(frame, days[21]))


def test_true_range_uses_previous_close_and_simple_mean():
    days, frame = range_frame()
    frame["high"] = 10.1
    frame.loc[days[1], ["open", "high", "low", "close"]] = [12., 12.2, 11.8, 12.]
    # Gap up TR=2.2, gap down TR=2.1, remaining 18 TRs=.2.
    assert stop_mean_true_range_distance(frame, days[21]) == pytest.approx(2 * (2.2 + 2.1 + 18 * .2) / 20)


@pytest.mark.parametrize("column,value", [("open", float("nan")), ("high", float("inf")),
                                         ("low", 11.), ("close", float("nan"))])
def test_invalid_prior_ohlc_disables_stop(column, value):
    days, frame = range_frame()
    frame.loc[days[3], column] = value
    assert stop_mean_true_range_distance(frame, days[21]) is None


def test_wire_distance_above_cost_is_not_a_ratio():
    from backtest.research.minute_true_core_wire import invoke_minute_strategy, OhlcBar
    days, frame = range_frame()
    frame["high"], frame["low"] = 16., 10.
    assert stop_mean_true_range_distance(frame, days[21]) == 12.
    hit = invoke_minute_strategy("version9", OhlcBar(10., 10., 1., 10.), cost=10., peak=10.,
                                 daily_bars=frame, as_of=days[21])
    assert hit.decision == "skip"


def flat_atr_history():
    days = pd.bdate_range("2025-09-01", periods=24)
    frame = pd.DataFrame({"open": 10., "high": 10.1, "low": 9.9, "close": 10.}, index=days)
    assert stop_mean_true_range_distance(frame, days[21]) == pytest.approx(.4)
    return days, frame


@pytest.mark.parametrize("engine", ["minute", "wire"])
@pytest.mark.parametrize("peak,bar,reason,price", [
    (10., (10., 10.15, 9.75, 10.), "", None),
    (10.15, (10., 10.15, 9.6, 10.), "stop_loss:touch", 9.6),
    (10., (10., 10.2, 9.9, 10.), "", None),
    (10.2, (10.1, 10.2, 10., 10.1), "trail:atr", 10.),
    (10.4, (10.1, 10.4, 10., 10.1), "trail:atr", 10.),
    (10.7, (10.5, 10.7, 10.2, 10.5), "trail:atr", 10.3),
    (10.7, (10.5, 11., 10.4, 11.), "profit_take:target", 11.),
    (10.7, (10.5, 11., 10.2, 10.5), "trail:atr", 10.3),
    (10., (10., 11., 9.5, 10.), "stop_loss:touch", 9.6),
    (11.7, (11.1, 11.8, 11., 11.2), "trail:atr", 11.1),
])
def test_flat_atr_protective_line_hosts(engine, peak, bar, reason, price):
    from backtest.research.csv_minute_backtest import scan_held_day_python
    from backtest.research.minute_true_core_wire import invoke_minute_strategy, OhlcBar
    days, frame = flat_atr_history()
    if engine == "wire":
        hit = invoke_minute_strategy("version9", OhlcBar(*bar), cost=10., peak=peak,
                                     daily_bars=frame, as_of=days[21])
        assert hit.reason == reason
        assert hit.decision == ("fill" if reason else "skip")
        fill = hit.fill_price
        returned_peak = hit.peak
    else:
        o, h, l, c = (np.array([v]) for v in bar)
        idx, fill, got_reason, returned_peak, _ = scan_held_day_python(
            o, h, c, cost=10., peak=peak, peak_hm=-1, n_days=1, can_sell=True,
            stop_pct=None, profit_base=0., trail_ratio=0.,
            peak_gap_min=0, limit_down=0., l=l,
            stop_range_distance=stop_mean_true_range_distance(frame, days[21]),
            minute_stop_trigger="hl", take_profit=take_profit_reason,
            take_profit_pct=.10)
        assert got_reason == reason
        assert (idx >= 0) is bool(reason)
    assert returned_peak == max(peak, bar[1])
    if reason:
        assert fill == pytest.approx(price)


@pytest.mark.parametrize("engine", ["daily", "minute"])
@pytest.mark.parametrize("scenario", ["unarmed", "initial_touch", "breakeven", "chandelier", "precedence", "target"])
def test_flat_atr_simulation(engine, scenario):
    from backtest.research.csv_minute_backtest import simulate as minute
    days, frame = flat_atr_history()
    # Entry day stays flat; the first sellable high must not protect that same bar.
    first = [10., 10.2, 10., 10.1]
    second = [10.1, 10.2, 10., 10.1]
    reason, expected = "trail:atr", 10.
    if scenario in ("unarmed", "initial_touch"):
        first = [10., 10.15, 9.75 if scenario == "unarmed" else 9.6, 10.]
        second = [10., 10.15, 9.75, 10.]
        reason = "" if scenario == "unarmed" else "stop_loss:touch"
        expected = 9.6
    elif scenario in ("chandelier", "precedence", "target"):
        first = [10., 10.7, 10., 10.6]
        # The next daily ATR rolls in the first sellable day's TR=.7.
        distance = 2 * (19 * .2 + .7) / 20
        expected = 10.7 - distance
        second = [10.5, 11. if scenario != "chandelier" else 10.7,
                  10.4 if scenario == "target" else 10.2,
                  11. if scenario == "target" else 10.5]
        if scenario == "target":
            reason, expected = "profit_take:target", (10.5 if engine == "daily" else 11.)
    frame.loc[days[21], ["open", "high", "low", "close"]] = first
    frame.loc[days[22], ["open", "high", "low", "close"]] = second
    frame.loc[days[23], ["open", "high", "low", "close"]] = [10.5, 10.6, 10.4, 10.5]
    start, end = (days[i].strftime("%Y%m%d") for i in (20, 23))
    pool = {start: ["600000.SH"]}
    if engine == "daily":
        st = sim.simulate({"600000.SH": frame}, pool, start, end, strategy="version9")
    else:
        # One sellable bar per day keeps the daily/minute path directly comparable.
        rows = [dict(row, time=day + pd.Timedelta(minutes=895), hm=895, ymd=day.strftime("%Y%m%d"))
                for day, row in frame.iterrows()]
        st = minute({"600000.SH": pd.DataFrame(rows).set_index("time")},
                    {"600000.SH": frame}, pool, start, end, strategy="version9", minute_stop_trigger="hl")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert st.stats["buys"] == 1
    assert len(sells) == (1 if reason else 0)
    if reason:
        assert sells[0]["reason"] == reason
        assert sells[0]["price"] == pytest.approx(expected)
        exit_day = 21 if scenario == "initial_touch" else (23 if scenario == "target" and engine == "daily" else 22)
        assert sells[0]["date"] == days[exit_day].strftime("%Y%m%d")


def test_minute_next_bar_uses_stored_high_and_wider_atr_disarms():
    from backtest.research.csv_minute_backtest import scan_held_day_python
    from backtest.research.strategy9_rules import protective_line
    common = dict(cost=10., peak=10., peak_hm=-1, n_days=1, can_sell=True,
                  stop_pct=None, profit_base=0., trail_ratio=0.,
                  peak_gap_min=0, limit_down=0.,
                  minute_stop_trigger="hl", take_profit=take_profit_reason, take_profit_pct=.10)
    hit = scan_held_day_python(np.array([10., 10.1]), np.array([10.2, 10.2]),
                              np.array([10.1, 10.1]), l=np.array([9.9, 10.]),
                              stop_range_distance=.4, **common)
    assert hit[0] == 1
    assert hit[1] == pytest.approx(10.)
    assert hit[2] == "trail:atr"
    assert protective_line(10., 10.2, .4) == (10., "trail")
    assert protective_line(10., 10.2, .6) == (9.4, "stop_loss")


@pytest.mark.parametrize("price", ["stop", "close"])
def test_wire_trail_close_fill_and_missing_window(price):
    from backtest.research.minute_true_core_wire import invoke_minute_strategy, OhlcBar
    days, frame = flat_atr_history()
    hit = invoke_minute_strategy("version9", OhlcBar(10.5, 10.7, 10.2, 10.5),
                                 cost=10., peak=10.7, daily_bars=frame, as_of=days[21], price=price)
    assert hit.reason == "trail:atr"
    assert hit.fill_price == pytest.approx(10.5 if price == "close" else 10.3)
    hit = invoke_minute_strategy("version9", OhlcBar(10., 10., 9., 9.5),
                                 cost=10., peak=10.7, daily_bars=frame.iloc[19:], as_of=days[21], price=price)
    assert hit.decision == "skip"


@pytest.mark.parametrize("peak,bar,reason,expected", [
    (10.7, [10.5, 10.7, 10.2, 10.5], "trail:atr", 10.3),
    (10.7, [10.5, 11., 10.2, 10.5], "trail:atr", 10.3),
    (11.7, [11.1, 11.8, 11., 11.2], "trail:atr", 11.1),
])
def test_daily_existing_peak_with_flat_atr(monkeypatch, peak, bar, reason, expected):
    days, frame = flat_atr_history()
    frame.loc[days[21], ["open", "high", "low", "close"]] = bar
    original = sim.exit_positions

    def held_with_peak(*args, **kwargs):
        positions = original(*args, **kwargs)
        # Supply an existing held peak without introducing a spike into the ATR window.
        for pos in positions:
            if kwargs.get("day") == days[21]:
                pos.peak = peak
            yield pos

    monkeypatch.setattr(sim, "exit_positions", held_with_peak)
    start, end = (days[i].strftime("%Y%m%d") for i in (20, 21))
    st = sim.simulate({"600000.SH": frame}, {start: ["600000.SH"]}, start, end, strategy="version9")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == reason
    assert sells[0]["price"] == pytest.approx(expected)
