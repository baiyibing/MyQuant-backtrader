"""Delayed-entry strategy9_3 contract on the shared daily/minute engines."""

from __future__ import annotations

import argparse
from types import SimpleNamespace

import pandas as pd
import pytest
from backtest.research import csv_artifacts
from backtest.research.csv_ledger import SimState
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import strategy9_3_rules as rules
from backtest.research.csv_strategy_books import (
    add_csv_backtest_common_args,
    apply_csv_strategy,
    csv_run_kwargs_from_args,
    engine_book,
    get_book,
    resolve_research_pool_dir,
)

CODE = "600000.SH"


def daily_frame(periods=30):
    days = pd.bdate_range("2026-03-02", periods=periods)
    pre = days[0] - pd.offsets.BDay()
    index = pd.DatetimeIndex([pre, *days])
    frame = pd.DataFrame(
        {"open": 10.0, "high": 10.2, "low": 9.5, "close": 10.0},
        index=index,
    )
    return days, frame


def run_daily(frame, days, pool, *, end=None, hold_days=20):
    return daily.simulate(
        {CODE: frame},
        pool,
        days[0].strftime("%Y%m%d"),
        (days[-1] if end is None else end).strftime("%Y%m%d"),
        strategy="version9_3",
        hold_days=hold_days,
    )


@pytest.mark.parametrize("alias", ["9.3", "9_3", "v9.3", "v9_3", "version9_3"])
def test_aliases_and_hooks(alias):
    assert get_book(alias).tag == "v9_3"
    hooks = apply_csv_strategy(alias)
    assert hooks["book"] == "v9_3"
    assert hooks["allow_add"] is False
    assert hooks["limit_up_chase"] is False
    assert hooks["pool_buy_at_open"] is True
    assert callable(hooks["bind_absolute_exit"])
    assert hooks["take_profit"](11.0, 10.0, 11.0, 1) == "profit_take:target"
    assert hooks["take_profit"](10.99, 10.0, 11.0, 1) is None
    assert hooks["take_profit"](11.0, 10.0, 11.0, 0) is None


def test_hold_day_hooks_keep_profit_priority_and_parameterize_max_hold():
    hooks20 = apply_csv_strategy("version9_3")
    hooks30 = apply_csv_strategy("version9_3", hold_days=30)
    assert hooks20["take_profit"](10.0, 10.0, 10.0, 19) is None
    assert hooks20["take_profit"](10.0, 10.0, 10.0, 20) == "force_sell:max_hold"
    assert hooks30["take_profit"](10.0, 10.0, 10.0, 20) is None
    assert hooks30["take_profit"](10.0, 10.0, 10.0, 30) == "force_sell:max_hold"
    assert hooks30["take_profit"](11.0, 10.0, 11.0, 30) == "profit_take:target"
    assert hooks30["minute_take_profit"](10.0, 10.0, 10.0, 30) is None
    assert hooks30["minute_next_open_exit"](10.0, 10.0, 10.0, 30) == "force_sell:max_hold"


def test_help_lock_and_recorded_take_profit_contract():
    assert "cost ×1.10" in rules.HELP_LOCK
    assert "profit_take:target" in rules.HELP_LOCK
    assert "no 10% take-profit" not in rules.HELP_LOCK
    assert "--hold-days {20,30} (default 20)" in rules.HELP_LOCK
    assert "n_days>=hold_days" in rules.HELP_LOCK
    assert "_h30_" in rules.HELP_LOCK
    st = SimpleNamespace(stats={})
    rules.record_strategy9_3_params(st)
    assert st.stats["profit_target"] == pytest.approx(0.10)
    assert st.stats["max_hold"] == 20
    rules.record_strategy9_3_params(st, hold_days=30)
    assert st.stats["max_hold"] == 30


def test_t_plus_three_daily_open_and_no_early_buy():
    days, frame = daily_frame(8)
    target = days[rules.DELAY_DAYS]
    frame.loc[target, ["open", "high", "low", "close"]] = [10.1, 10.4, 9.8, 10.3]
    signal = days[0].strftime("%Y%m%d")
    st = run_daily(frame, days, {signal: [CODE]})
    buys = [trade for trade in st.trades if trade["side"] == "BUY"]
    assert len(buys) == 1
    assert buys[0]["date"] == target.strftime("%Y%m%d")
    assert buys[0]["price"] == pytest.approx(10.1)
    assert not any(
        trade["side"] == "BUY" and trade["date"] in {day.strftime("%Y%m%d") for day in days[:3]}
        for trade in st.trades
    )


def test_shift_union_and_skip_counts_reach_state():
    days, full = daily_frame(8)
    missing = full.drop(days[3])
    signal0 = days[0].strftime("%Y%m%d")
    late = days[-2].strftime("%Y%m%d")
    shifted = rules.shift_pool_days(
        {signal0: [CODE, CODE], days[1].strftime("%Y%m%d"): [CODE]},
        days,
        {CODE: full},
    )
    assert shifted.pool_days == {
        days[3].strftime("%Y%m%d"): [CODE],
        days[4].strftime("%Y%m%d"): [CODE],
    }

    st = daily.simulate(
        {CODE: missing, "600001.SH": full},
        {signal0: [CODE], late: [CODE]},
        days[0].strftime("%Y%m%d"),
        days[-1].strftime("%Y%m%d"),
        strategy="version9_3",
    )
    assert st.stats["skip_v9_3_no_bar"] == 1
    assert st.stats["skip_v9_3_delay_out_of_window"] == 1
    assert st.stats["buys"] == 0


def test_limit_up_skip_without_retry_and_held_name_skip():
    days, frame = daily_frame(9)
    frame.loc[days[3], ["open", "high", "low", "close"]] = [11.0, 11.0, 10.5, 11.0]
    signal = days[0].strftime("%Y%m%d")
    st = run_daily(frame, days, {signal: [CODE]})
    assert st.stats["skip_limit_up"] == 1
    assert st.stats["buys"] == 0
    assert not st.positions

    days, frame = daily_frame(9)
    pool = {
        days[0].strftime("%Y%m%d"): [CODE],
        days[1].strftime("%Y%m%d"): [CODE],
    }
    st = run_daily(frame, days, pool)
    assert st.stats["buys"] == 1
    assert st.stats["skip_held"] == 1


def test_twenty_day_exit_marks_at_close_and_fills_next_open():
    days, frame = daily_frame(27)
    frame.loc[:, ["high", "low"]] = [10.1, 9.5]
    st = run_daily(frame, days, {days[0].strftime("%Y%m%d"): [CODE]})
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == "force_sell:max_hold"
    assert sells[0]["date"] == days[rules.DELAY_DAYS + rules.MAX_HOLD + 1].strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(10.0)


def test_thirty_day_exit_marks_at_close_and_fills_next_open():
    days, frame = daily_frame(37)
    frame.loc[:, ["high", "low"]] = [10.1, 9.5]
    st = run_daily(
        frame,
        days,
        {days[0].strftime("%Y%m%d"): [CODE]},
        hold_days=30,
    )
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == "force_sell:max_hold"
    assert sells[0]["date"] == days[rules.DELAY_DAYS + 31].strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(10.0)
    assert st.stats["max_hold"] == 30


def test_daily_take_profit_marks_at_close_and_fills_next_open():
    days, frame = daily_frame(8)
    trigger_day = days[rules.DELAY_DAYS + 1]
    fill_day = days[rules.DELAY_DAYS + 2]
    frame.loc[trigger_day, ["open", "high", "low", "close"]] = [10.0, 11.1, 9.5, 11.0]
    st = run_daily(frame, days, {days[0].strftime("%Y%m%d"): [CODE]})
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == "profit_take:target"
    assert sells[0]["date"] == fill_day.strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(10.0)
    assert sells[0]["price_rule"] == "daily_pending_next_open"


@pytest.mark.parametrize(
    "opening,low,expected_price,reason",
    [
        (8.9, 8.8, 8.9, "stop_loss:gap_open"),
        (9.4, 8.9, 9.0, "stop_loss:touch"),
    ],
)
def test_fixed_stop_gap_and_touch(opening, low, expected_price, reason):
    days, frame = daily_frame(8)
    buy = days[3]
    stop = days[4]
    frame.loc[buy, "close"] = 9.5
    frame.loc[stop, ["open", "high", "low", "close"]] = [
        opening,
        max(opening, 9.4),
        low,
        9.1,
    ]
    st = run_daily(frame, days, {days[0].strftime("%Y%m%d"): [CODE]})
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == reason
    assert sells[0]["price"] == pytest.approx(expected_price)


def test_t1_same_day_stop_is_ignored_and_limit_down_defers():
    days, frame = daily_frame(8)
    buy = days[3]
    frame.loc[buy, ["open", "high", "low", "close"]] = [10.0, 10.1, 8.0, 10.0]
    same_day = run_daily(frame, days[:4], {days[0].strftime("%Y%m%d"): [CODE]})
    assert same_day.stats["buys"] == 1
    assert not [trade for trade in same_day.trades if trade["side"] == "SELL"]

    frame.loc[days[4], ["open", "high", "low", "close"]] = [9.0, 9.0, 9.0, 9.0]
    frame.loc[days[5], ["open", "high", "low", "close"]] = [9.2, 9.3, 9.1, 9.2]
    st = run_daily(frame, days, {days[0].strftime("%Y%m%d"): [CODE]})
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert st.stats["defer_sell_limit_down"] >= 1
    assert sells[0]["date"] == days[5].strftime("%Y%m%d")
    assert sells[0]["reason"] == "stop_loss:gap_open"


def test_stop_override_and_stock_pool_refused(tmp_path):
    with pytest.raises(SystemExit, match="stop-pct"):
        apply_csv_strategy("version9_3", stop_pct=0.10)
    with pytest.raises(SystemExit, match="stop-pct"):
        get_book("version9_3").run_kwargs(SimpleNamespace(stop_pct=0.10))
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version9_3", None, repo=tmp_path)


def test_hold_days_cli_and_apply_validation(tmp_path):
    parser = argparse.ArgumentParser()
    add_csv_backtest_common_args(
        parser,
        repo=tmp_path,
        end_default="20261006",
        cash_total_default=21_000_000,
        daily_quota_default=1_000_000,
    )
    default = parser.parse_args(["--strategy", "version9_3"])
    assert default.hold_days == 20
    assert csv_run_kwargs_from_args(default)["hold_days"] == 20
    selected = parser.parse_args(
        ["--strategy", "version9_3", "--hold-days", "30"]
    )
    assert csv_run_kwargs_from_args(selected)["hold_days"] == 30
    with pytest.raises(SystemExit, match="--hold-days is supported only by version9_3"):
        csv_run_kwargs_from_args(
            parser.parse_args(["--strategy", "version9", "--hold-days", "30"])
        )
    with pytest.raises(SystemExit):
        parser.parse_args(["--strategy", "version9_3", "--hold-days", "25"])

    assert apply_csv_strategy("version9_3", hold_days=20)["book"] == "v9_3"
    assert apply_csv_strategy("version9_3", hold_days=30)["book"] == "v9_3"
    with pytest.raises(ValueError, match="supported only by version9_3"):
        apply_csv_strategy("version9", hold_days=30)
    with pytest.raises(ValueError, match="must be 20 or 30"):
        apply_csv_strategy("version9_3", hold_days=25)


@pytest.mark.parametrize("host", [daily, minute])
def test_simulate_refuses_nondefault_hold_for_other_books_and_invalid_value(host):
    args = ({}, {}, "20260302", "20260303")
    if host is minute:
        args = ({}, {}, {}, "20260302", "20260303")
    with pytest.raises(ValueError, match="supported only by version9_3"):
        host.simulate(*args, strategy="version9", hold_days=30)
    with pytest.raises(ValueError, match="must be 20 or 30"):
        host.simulate(*args, strategy="version9_3", hold_days=25)


def test_hold_days_output_tag_and_daily_path():
    assert engine_book("version9_3") == "v9_3"
    assert engine_book("version9_3", hold_days=20) == "v9_3"
    assert engine_book("version9_3", hold_days=30) == "v9_3_h30"
    assert daily.resolve_csv_daily_out_dir(
        None,
        book=engine_book("version9_3", hold_days=30),
        start="20260302",
        end="20260430",
    ).name == "csv_daily_v9_3_h30_20260302_20260430"


def test_weighted_stop_line():
    lots = [
        SimpleNamespace(cost=10.0, shares=100),
        SimpleNamespace(cost=12.0, shares=300),
    ]
    assert rules.stop_line(lots) == pytest.approx(11.5 * rules.STOP_FRAC)


def test_minute_mode_delayed_buy_smoke():
    days, frame = daily_frame(8)
    rows = []
    for day in days:
        for hm, px in ((570, 9.9), (895, 10.2), (900, 10.1)):
            rows.append(
                {
                    "time": day + pd.Timedelta(minutes=hm),
                    "ymd": day.strftime("%Y%m%d"),
                    "hm": hm,
                    "open": px,
                    "high": px + 0.05,
                    "low": px - 0.05,
                    "close": px,
                }
            )
    minutes = pd.DataFrame(rows).set_index("time")
    st = minute.simulate(
        {CODE: minutes},
        {CODE: frame},
        {days[0].strftime("%Y%m%d"): [CODE]},
        days[0].strftime("%Y%m%d"),
        days[-1].strftime("%Y%m%d"),
        strategy="version9_3",
    )
    buys = [trade for trade in st.trades if trade["side"] == "BUY"]
    assert len(buys) == 1
    assert buys[0]["date"] == days[3].strftime("%Y%m%d")
    assert buys[0]["price"] == pytest.approx(10.2)
    assert not [trade for trade in st.trades if trade["side"] == "SELL"]


def test_minute_take_profit_fills_intraday_at_target():
    days, frame = daily_frame(8)
    rows = []
    for day in days:
        for hm in (570, 895, 900):
            rows.append(
                {
                    "time": day + pd.Timedelta(minutes=hm),
                    "ymd": day.strftime("%Y%m%d"),
                    "hm": hm,
                    "open": 10.0,
                    "high": 10.05,
                    "low": 9.95,
                    "close": 10.0,
                }
            )
    minutes = pd.DataFrame(rows).set_index("time")
    trigger_day = days[rules.DELAY_DAYS + 1]
    trigger_time = trigger_day + pd.Timedelta(minutes=895)
    minutes.loc[trigger_time, ["open", "high", "low", "close"]] = [10.0, 11.0, 10.0, 11.0]
    st = minute.simulate(
        {CODE: minutes},
        {CODE: frame},
        {days[0].strftime("%Y%m%d"): [CODE]},
        days[0].strftime("%Y%m%d"),
        days[-1].strftime("%Y%m%d"),
        strategy="version9_3",
    )
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == "profit_take:target"
    assert sells[0]["date"] == trigger_day.strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(11.0)


@pytest.mark.parametrize("hold_days,periods", [(20, 28), (30, 38)])
def test_minute_max_hold_limit_down_open_defers_once(hold_days, periods):
    days, frame = daily_frame(periods)
    deferred_day = days[rules.DELAY_DAYS + hold_days + 1]
    rows = []
    for day in days:
        for hm in (570, 895, 900):
            px = 9.0 if day == deferred_day else 10.0
            rows.append(
                {
                    "time": day + pd.Timedelta(minutes=hm),
                    "ymd": day.strftime("%Y%m%d"),
                    "hm": hm,
                    "open": px,
                    "high": px if day == deferred_day else 10.1,
                    "low": px if day == deferred_day else 9.5,
                    "close": px,
                }
            )
    minutes = pd.DataFrame(rows).set_index("time")
    st = minute.simulate(
        {CODE: minutes},
        {CODE: frame},
        {days[0].strftime("%Y%m%d"): [CODE]},
        days[0].strftime("%Y%m%d"),
        days[-1].strftime("%Y%m%d"),
        strategy="version9_3",
        hold_days=hold_days,
    )
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["reason"] == "force_sell:max_hold"
    assert sells[0]["date"] == days[rules.DELAY_DAYS + hold_days + 2].strftime("%Y%m%d")
    assert sells[0]["price"] == pytest.approx(10.0)
    assert st.stats["defer_sell_limit_down"] == 1
    assert st.stats["max_hold"] == hold_days

def test_summary_params_reflect_hold_days():
    """summary.txt hold label follows stats max_hold; default 20 stays byte-identical."""
    default_line = (
        "  参数: SCAN T+3 买入 | 固定止损 weighted cost ×0.90 | "
        "满持有 20 日收盘决定、次开 force_sell:max_hold | 不加仓"
    )
    st20 = SimState(cash=21_000_000.0)
    st20.equity_curve = [("20260302", 21_000_000.0)]
    st20.stats.update(sell_book="v9_3", max_hold=20)
    text20 = csv_artifacts.summarize(st20, 21_000_000.0, "20260302", "20260303")
    assert default_line in text20.splitlines()

    st30 = SimState(cash=21_000_000.0)
    st30.equity_curve = [("20260302", 21_000_000.0)]
    st30.stats.update(sell_book="v9_3", max_hold=30)
    text30 = csv_artifacts.summarize(st30, 21_000_000.0, "20260302", "20260303")
    assert default_line not in text30.splitlines()
    assert (
        "  参数: SCAN T+3 买入 | 固定止损 weighted cost ×0.90 | "
        "满持有 30 日收盘决定、次开 force_sell:max_hold | 不加仓"
    ) in text30.splitlines()

