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
    mean_true_range,
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
        "stop_mode": "cost_minus_mean_true_range_20_trailing",
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
    summary = (out / "summary.txt").read_text(encoding="utf-8")
    assert "rolling range" in summary and "0.90" in summary
    assert "止损 关闭" not in summary


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
    assert mean_true_range(frame, days[21]) == pytest.approx((2.1 + 19 * .2) / 20)
    assert mean_true_range(frame, days[22]) == pytest.approx(.2)


@pytest.mark.parametrize("engine", ["daily", "minute"])
def test_hosts_use_rolled_range(engine):
    from backtest.research.csv_minute_backtest import simulate as minute
    days, frame = range_frame()
    frame.loc[days[21], ["open", "high", "low", "close"]] = [10., 10.1, 9.75, 10.]
    frame.loc[days[22], ["open", "high", "low", "close"]] = [10., 10.1, 9.5, 10.]
    # First trigger 7.9 survives day 21. Rolled day 22 trigger is 9.6.
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
    assert sells[0]["price"] == pytest.approx(10 - (19 * .2 + .35) / 20)


@pytest.mark.parametrize("missing", ["short_history", "missing_ohlc", "bad_close"])
def test_missing_range_does_not_fallback(missing):
    days, frame = range_frame()
    frame.loc[days[21], ["open", "high", "low", "close"]] = [10., 10., 9.1, 9.3]
    if missing == "short_history":
        frame = frame.iloc[19:]
    elif missing == "missing_ohlc":
        frame.loc[days[2], "high"] = float("nan")
    else:
        frame.loc[days[0], "close"] = float("nan")
        missing = "missing_ohlc"
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
    assert mean_true_range(frame, days[21]) == pytest.approx(ratio * 10)
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
    help_text = capsys.readouterr().out
    assert "--max-hold" in help_text
    assert "0.90" in help_text and "不回落固定比例" in help_text
    with pytest.raises(SystemExit, match="--max-hold.*version9"):
        main(["--strategy", "version6", "--max-hold"])


@pytest.mark.parametrize("book", ["version9", "version9_2"])
@pytest.mark.parametrize("opening,low,expected,reason", [
    (10., 9., None, None),
    (10., 8.55, 8.55, "stop_loss:touch"),
    (8.5, 8.4, 8.5, "stop_loss:gap_open"),
])
def test_mean_true_range_yuan_stop(book, opening, low, expected, reason):
    from backtest.research.strategy9_2_rules import chosen_stop
    days = pd.bdate_range("2026-03-02", periods=23)
    frame = pd.DataFrame(dict(open=10., high=11., low=10., close=10.), index=days)
    frame.loc[days[0], "close"] = 20.
    frame.loc[days[21], ["open", "high", "low", "close"]] = [opening, 100., low, 10.]
    assert mean_true_range(frame, days[21]) == pytest.approx(1.45)
    assert chosen_stop(10., frame, days[21]) == pytest.approx(8.55)
    assert mean_true_range(frame, days[22]) != pytest.approx(1.45)
    # Seed a T+1 holding so the decision window has exactly 21 prior bars.
    from backtest.research.csv_ledger import execute_buy
    from backtest.research.csv_simulate_loop import init_sim_state
    hooks = apply_csv_strategy(book)
    st = init_sim_state(hooks, total_cash=2_000_000, bars_loaded=1, pool_days={})[0]
    execute_buy(st, "600000.SH", 10., 400_000, 0, days[20], reason="pool")
    if book == "version9_2":
        from backtest.research.strategy9_2_engine import fill_stop
        row = SimpleNamespace(open=opening, low=low, close=low)
        fill_stop(st, "600000.SH", row, frame, days[21], day_i=1,
                  ds=days[21].strftime("%Y%m%d"), limits=(200., 0.))
    else:
        # Decision follows a cost-10 entry, whose close supplies the final prior TR.
        frame.loc[days[20], "high"] = 11.
        start, end = days[20].strftime("%Y%m%d"), days[21].strftime("%Y%m%d")
        # Avoid a limit-down deferral: the previous close is 10, so 8.55 lies below
        # the exchange band. Exercise the host with a broad synthetic limit band.
        from unittest.mock import patch
        with patch.object(sim, "defer_sell_at_limit", return_value=False):
            st = sim.simulate({"600000.SH": frame}, {start:["600000.SH"]}, start, end, strategy=book)
    sells = [t for t in st.trades if t["side"] == "SELL"]
    if expected is None:
        assert sells == []
    else:
        assert sells[0]["price"] == pytest.approx(expected)
        assert sells[0]["reason"] == reason


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
@pytest.mark.parametrize("column", ["high", "low", "close"])
def test_mean_true_range_invalid_ohlc(column, value):
    days, frame = range_frame()
    frame.loc[days[2], column] = value
    assert mean_true_range(frame, days[21]) is None


def test_mean_true_range_zero_previous_close_is_valid():
    days, frame = range_frame()
    frame.loc[days[0], "close"] = 0.
    assert mean_true_range(frame, days[21]) == pytest.approx((10.1 + 2.1 + 18 * .2) / 20)


@pytest.mark.parametrize("distance,low,expected", [(2., 8.9, None), (2., 7.9, 8.), (None, 1., None)])
def test_version9_no_fixed_percent_or_missing_fallback(distance, low, expected):
    from unittest.mock import patch
    days = pd.bdate_range("2026-03-02", periods=23)
    frame = pd.DataFrame(dict(open=10., high=11., low=9., close=10.), index=days)
    if distance is None:
        frame = frame.iloc[19:]
    frame.loc[days[21], ["high", "low", "close"]] = [10., low, 10.]
    start, end = days[20].strftime("%Y%m%d"), days[21].strftime("%Y%m%d")
    with patch.object(sim, "defer_sell_at_limit", return_value=False):
        st = sim.simulate({"600000.SH": frame}, {start:["600000.SH"]}, start, end, strategy="version9")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    if expected is None:
        assert sells == []
    else:
        assert sells[0]["price"] == pytest.approx(expected)
        assert sells[0]["reason"] == "stop_loss:touch"
