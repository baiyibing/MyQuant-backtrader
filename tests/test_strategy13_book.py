from types import SimpleNamespace

import pandas as pd
import pytest

from backtest.research import strategy13_engine as engine, strategy13_rules as rules
from backtest.research.csv_simulate_loop import init_sim_state, run_profit_skim_day
from backtest.research.csv_strategy_books import apply_csv_strategy, resolve_research_pool_dir
from backtest.research.csv_ledger import execute_buy

CODE = "600000.SH"
DAY = pd.Timestamp("20260105")


def state(capital=21e6, **kwargs):
    hooks = apply_csv_strategy("v13", **kwargs)
    st = init_sim_state(hooks, total_cash=capital, bars_loaded=1, pool_days={})[0]
    return st, hooks


def open_base(st, hooks, px=10):
    return engine.buy(st, CODE, px, [px]*120, hooks=hooks, day_i=0, day=DAY,
                      ds="20260105", names={}, exdiv=None)


def test_registration_and_pool(tmp_path):
    st, hooks = state()
    assert hooks["sizing"] == "per_name"
    assert hooks["book"] == "v13"
    assert hooks["div_to_parking"]
    with pytest.raises(SystemExit, match="export_beidou_pool"):
        resolve_research_pool_dir("v13", None, repo=tmp_path)


def test_tp_current_shares_once_floor_and_clear():
    st, h = state()
    assert open_base(st, h)
    mem = engine.memory(st, CODE)
    assert mem.base_shares == 1000
    pending = st.book_state.setdefault("beidou_pending", {})
    for tier, (level, fraction) in enumerate(zip(rules.TP_LEVELS, rules.TP_FRACTIONS)):
        held = sum(p.shares for p in st.positions[CODE])
        px = 10*(1+level)
        plan = engine.plan_exit(st, CODE, px, DAY, [10]*120, day_i=1,
                                ds="20260106", params=h["beidou_params"])
        if plan:
            assert plan == (f"profit_take:beidou:{tier}", rules.tp_shares(held, 1000, fraction))
            pending[CODE] = plan
            engine.fill_pending(st, CODE, SimpleNamespace(open=px), DAY,
                                day_i=1, ds="20260106", limits=(100, 1))
        assert mem.tier == tier + 1
        assert sum(p.shares for p in st.positions[CODE]) >= 100
    mem.peak = 40
    plan = engine.plan_exit(st, CODE, 30, DAY, [30]*120, day_i=2, ds="20260107", params=h["beidou_params"])
    assert plan[0] == "trail:beidou_clear"
    assert plan[1] == sum(p.shares for p in st.positions[CODE])


def test_add_multipliers_cap_and_failed_fill_does_not_advance():
    st, h = state(capital=1e6)
    open_base(st, h)
    kwargs = dict(hooks=h, day_i=1, day=DAY, ds="20260106", names={}, exdiv=None, adding=True)
    assert not engine.buy(st, CODE, 16, [15]*120, **kwargs)  # 672k > 200k cap
    assert engine.memory(st, CODE).adds == 0
    st2, h2 = state()
    open_base(st2, h2)
    kwargs["hooks"] = h2
    assert engine.buy(st2, CODE, 16, [15]*120, **kwargs)
    mem = engine.memory(st2, CODE)
    assert mem.adds == 1
    assert st2.trades[-1]["shares"] == 42000
    assert not engine.buy(st2, CODE, 17.59, [17]*120, **kwargs)
    assert engine.buy(st2, CODE, 17.6, [17]*120, **kwargs)
    assert st2.trades[-1]["shares"] == 35000
    mem.adds = 10
    assert not engine.buy(st2, CODE, 100, [99]*120, **kwargs)
    assert mem.adds == 10


def test_short_cash_and_name_override_cannot_relax_cap():
    st, h = state(10000, name_budget=1e12)
    assert not open_base(st, h)
    assert st.stats["skip_cash"] == 1
    st, h = state()
    open_base(st, h)
    st.cash = 100
    assert not engine.buy(st, CODE, 16, [15]*120, hooks=h, day_i=1, day=DAY,
                          ds="20260106", names={}, exdiv=None, adding=True)
    assert engine.memory(st, CODE).adds == 0


def test_t1_pending_tier_advances_only_after_fill():
    st, h = state()
    open_base(st, h)
    st.book_state["beidou_pending"] = {CODE: ("profit_take:beidou:0", 100)}
    engine.fill_pending(st, CODE, SimpleNamespace(open=12), DAY, day_i=0, ds="20260105", limits=(20, 1))
    assert engine.memory(st, CODE).tier == 0
    engine.fill_pending(st, CODE, SimpleNamespace(open=12), DAY, day_i=1, ds="20260106", limits=(20, 1))
    assert engine.memory(st, CODE).tier == 1
    assert st.stats["beidou_realized"] > 190


@pytest.mark.parametrize("prices,age,reason", [([10]*19+[8.49], 40, "hard"),
                                               ([10]*19+[9.5], 30, "early")])
def test_close_stops(prices, age, reason):
    st, h = state()
    open_base(st, h)
    plan = engine.plan_exit(st, CODE, prices[-1], DAY, prices[:-1], day_i=age,
                            ds="20260106", params=h["beidou_params"], daily_close=True)
    assert plan[0] == f"stop_loss:beidou_{reason}"


def test_ma20_counts_sessions_not_bars_and_reclaim_resets():
    st, h = state()
    open_base(st, h)
    for ds in ("20260106", "20260107"):
        for _ in range(3):
            assert engine.plan_exit(st, CODE, 9.8, DAY, [10]*120, day_i=40, ds=ds,
                                    params=h["beidou_params"], daily_close=True) is None
    assert engine.memory(st, CODE).below_days == 2
    plan = engine.plan_exit(st, CODE, 9.8, DAY, [10]*120, day_i=42, ds="20260108",
                            params=h["beidou_params"], daily_close=True)
    assert plan[0] == "stop_loss:beidou_ma20"


def test_realized_skim_cumulative_full_increment_and_no_unrealized_trigger():
    st, h = state(1e6)
    # Isolated synthetic books may supply explicit economics; no lake access.
    dates = pd.bdate_range("20251201", "20260105")
    bars = {rules.PARKING_SYMBOL: pd.DataFrame({"open": 10., "high": 10., "low": 10., "close": 10.}, index=dates)}
    args = dict(day_i=1, day=DAY, ds="20260105", names={}, daily_bars=bars)
    run_profit_skim_day(st, h, **args)
    assert not st.trades
    st.stats["beidou_realized"] = 199999
    run_profit_skim_day(st, h, **args)
    assert not st.trades
    st.stats["beidou_realized"] = 400000
    run_profit_skim_day(st, h, **args)
    assert st.stats["beidou_skim_entitled"] == 400000
    assert st.stats["profit_skim_parked"] == pytest.approx(400000, abs=1000)
    count = len(st.trades)
    run_profit_skim_day(st, h, **args)
    assert len(st.trades) == count
    st.stats["beidou_realized"] = -100
    run_profit_skim_day(st, h, **args)
    assert st.stats["beidou_skim_entitled"] == 400000


@pytest.mark.parametrize("params", [{"max_adds": 11}, {"base_budget": float("nan")},
                                     {"next_add": 1}, {"tp_fractions": [1]}, {"ma_sessions": 1.5}])
def test_bad_overrides(params):
    with pytest.raises(ValueError):
        rules.Params(**params)


@pytest.mark.parametrize("profile", ["legacy", "industry"])
@pytest.mark.parametrize("minute", [False, True])
def test_daily_minute_end_to_end(profile, minute):
    from backtest.research.csv_daily_backtest import simulate as daily
    from backtest.research.csv_minute_backtest import simulate as intraday
    dates = pd.bdate_range("20250101", periods=127)
    prices = [10.]*121 + [10.5, 11., 12., 12., 11.5, 11.5]
    frame = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices}, index=dates)
    start, end = dates[120].strftime("%Y%m%d"), dates[-1].strftime("%Y%m%d")
    pool = {start: [CODE]}
    kwargs = dict(strategy="version13", rule_profile=profile, total_cash=21e6,
                  index_block_new={d.date(): 1. for d in dates})
    if minute:
        rows = [dict(time=d+pd.Timedelta(minutes=hm), ymd=d.strftime("%Y%m%d"), hm=hm,
                     open=p, high=p, low=p, close=p) for d, p in zip(dates, prices) for hm in (570, 895, 900)]
        minutes = pd.DataFrame(rows).set_index("time")
        st = intraday({CODE: minutes}, {CODE: frame}, pool, start, end, **kwargs)
    else:
        st = daily({CODE: frame}, pool, start, end, **kwargs)
    buys = [t for t in st.trades if t["side"] == "BUY"]
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert len(buys) == 1 and buys[0]["shares"] == 1000
    assert sells and sells[0]["reason"] == "profit_take:beidou:0"
    assert sum(p.shares for p in st.positions[CODE]) >= 100
    assert st.stats["beidou_realized"] > 0


def test_parking_dividends_reinvest_without_beidou_adds():
    from backtest.research.ashare_exdiv_economics import ExDivEconomics, ExDivEvent
    from backtest.research.csv_simulate_loop import accrue_overnight_cash_div, bind_parking_session, run_div_to_parking_day
    st, h = state(1e6)
    assert execute_buy(st, rules.PARKING_SYMBOL, 10., 100000., 0, DAY, reason="parking:profit_skim")
    held = sum(p.shares for p in st.positions[rules.PARKING_SYMBOL])
    st.exdiv_economics = ExDivEconomics({(rules.PARKING_SYMBOL, "20260106"):
                                      ExDivEvent("test-div", 0, 1., "20260106", "20260106")}, st.stats)
    posted = accrue_overnight_cash_div(st, "20260106")
    assert posted == held
    st.stats["div_to_parking_pending"] = posted
    dates = pd.bdate_range("20251201", "20260106")
    bars = {rules.PARKING_SYMBOL: pd.DataFrame({"open": 10., "high": 10., "low": 10., "close": 10.}, index=dates)}
    args = dict(day_i=1, day=pd.Timestamp("20260106"), ds="20260106", names={}, daily_bars=bars)
    bind_parking_session(st, h, **args)
    assert run_div_to_parking_day(st, h, **args) > 0
    assert sum(p.shares for p in st.positions[rules.PARKING_SYMBOL]) > held
    assert st.trades[-1]["reason"] == "parking:cash_div"
    assert not st.book_state.get("beidou")


def test_fee_shortfall_is_whole_order_skip_under_industry():
    from backtest.research.csv_daily_backtest import simulate
    dates = pd.bdate_range("20250101", periods=3)
    f = pd.DataFrame({"open": 10., "high": 10., "low": 10., "close": 10.}, index=dates)
    start, end = dates[1].strftime("%Y%m%d"), dates[-1].strftime("%Y%m%d")
    # Eleven 2k declarations: fees exhaust cash before the tenth; never shrink.
    codes = [f"{600000+i}.SH" for i in range(11)]
    st = simulate({code: f for code in codes}, {start: codes}, start, end,
                  strategy="version13", total_cash=20005., beidou_params={"base_budget": 2000.})
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert len(buys) == 9
    assert all(t["shares"] == 200 for t in buys)
    assert st.stats["skip_cash"] == 2


def test_help_lock_digest_and_override_plumbing():
    import argparse
    import hashlib
    from backtest.research.csv_strategy_books import add_csv_backtest_common_args, csv_run_kwargs_from_args
    parser = argparse.ArgumentParser()
    add_csv_backtest_common_args(parser, repo=".", end_default="20261017", cash_total_default=21000000, daily_quota_default=1000000)
    args = parser.parse_args(["--strategy", "v13", "--beidou-params", '{"base_budget": 20000, "max_adds": 5}'])
    kwargs = csv_run_kwargs_from_args(args)
    assert kwargs["name_budget"] == 4200000
    assert kwargs["beidou_params"] == {"base_budget": 20000, "max_adds": 5}
    # Freeze this book's user-visible contract without editing earlier HELP_LOCKs.
    assert hashlib.sha256(rules.HELP_LOCK.encode()).hexdigest() == "1d7ef0ab0085b9e9dbc8d9dffd43750699ec97c7c37cf53fab36e2c69eec29d5"


def test_cmb_a_signal_and_parking_principal_remain_separate():
    from backtest.research.csv_ledger import is_parking_lot
    st, h = state(1e6)
    dates = pd.bdate_range("20251201", "20260105")
    bars = {rules.PARKING_SYMBOL: pd.DataFrame({"open": 10., "high": 10., "low": 10., "close": 10.}, index=dates)}
    st.stats["beidou_realized"] = 200000
    run_profit_skim_day(st, h, day_i=0, day=DAY, ds="20260105", names={}, daily_bars=bars)
    principal = sum(p.shares for p in st.positions[rules.PARKING_SYMBOL] if is_parking_lot(st, p))
    assert principal > 0
    assert engine.buy(st, rules.PARKING_SYMBOL, 10., [10.]*120, hooks=h, day_i=1,
                      day=DAY, ds="20260105", names={}, exdiv=None)
    plan = engine.plan_exit(st, rules.PARKING_SYMBOL, 8., DAY, [10.]*120,
                            day_i=2, ds="20260106", params=h["beidou_params"], daily_close=True)
    assert plan[1] == 1000
    st.book_state["beidou_pending"] = {rules.PARKING_SYMBOL: plan}
    engine.fill_pending(st, rules.PARKING_SYMBOL, SimpleNamespace(open=8.), DAY,
                        day_i=2, ds="20260106", limits=(20., 1.))
    assert sum(p.shares for p in st.positions[rules.PARKING_SYMBOL]) == principal
    assert not engine.strategy_lots(st, rules.PARKING_SYMBOL)
