"""Turtle book contract and synthetic daily/minute fill regressions."""
from types import SimpleNamespace

import pandas as pd
import pytest

from backtest.research import strategy9_2_rules as r
from backtest.research.csv_strategy_books import apply_csv_strategy, get_book, resolve_research_pool_dir
from backtest.research.csv_daily_backtest import simulate


@pytest.mark.parametrize("alias", ["9.2", "9_2", "v9.2", "v9_2", "version9_2"])
def test_strategy9_2_registration(alias):
    assert get_book(alias).name == "version9_2"
    h = apply_csv_strategy(alias)
    assert h["book"] == "v9_2" and h["allow_add"]
    assert h["sizing"] == "per_name" and h["stop_pct"] is None
    assert h.get("stop_range") is None and h["take_profit"](11, 10, 11, 1) is None


def test_strategy9_2_refusals(tmp_path):
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version9_2", None, repo=tmp_path)
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir("version9_2", tmp_path / "stock_pool", repo=tmp_path)
    assert resolve_research_pool_dir("version9_2", tmp_path / "scan", repo=tmp_path) == tmp_path / "scan"
    with pytest.raises(SystemExit, match="stop-pct"):
        apply_csv_strategy("version9_2", stop_pct=.1)
    with pytest.raises(SystemExit, match="stop-pct"):
        get_book("version9_2").run_kwargs(SimpleNamespace(stop_pct=.1))


def test_strategy9_2_sizing_and_touch():
    assert [r.lot_budget(1_000_000, n) for n in range(4)] == [400_000, 300_000, 200_000, 0]
    assert not r.add_due(10, 1, 10.39)
    assert r.add_due(10, 1, 10.4)
    assert not r.add_due(10, 2, 10.99)
    assert r.add_due(10, 2, 11)
    assert not r.add_due(10, 3, 99)


@pytest.mark.parametrize("units,factor", [(1,.96), (2,1.01), (3,1.02)])
def test_strategy9_2_stop_tiers(units, factor):
    assert r.stop_line(10, units, 9) == pytest.approx(10 * factor)
    assert r.stop_line(10, units, 12, tick=None) == pytest.approx(10 * factor)
    if units > 1:
        assert r.stop_line(10, units, 12) == pytest.approx(11.99)


def test_strategy9_2_remaining_bands():
    remaining = 10_000
    seq = 0
    for price, ratio in zip(r.SELL_BANDS, r.SELL_RATIOS):
        seq, frac = r.scale_out(price * 10, 10, seq)
        assert frac == ratio
        remaining *= 1 - frac
        assert r.scale_out(price * 10, 10, seq)[1] == 0
    assert remaining == pytest.approx(3136)
    assert r.scale_out(20, 10, 0) == (4, .6864)
    assert r.scale_out(20, 10, 1) == (4, .552)


def test_strategy9_2_time_stop():
    assert not r.time_stop(10, 10, 1, 4)
    assert r.time_stop(10, 10, 1, 5)
    assert not r.time_stop(10.4, 10, 1, 5)
    assert r.time_stop(10.9, 10, 2, 5)
    assert not r.time_stop(1, 10, 3, 99)


@pytest.mark.parametrize("high,threshold", [(12,.5), (15,.4), (16,.2)])
def test_strategy9_2_giveback(high, threshold):
    line = high - (high - 10) * threshold
    assert r.giveback(line, 10, high, 3)
    assert not r.giveback(line + .01, 10, high, 3)
    assert not r.giveback(line, 10, high, 2)


def test_strategy9_2_help_stats_and_version9():
    st = SimpleNamespace(stats={})
    r.record_strategy9_2_params(st)
    assert st.stats["turtle_add_bands"] == r.TURTLE_ADD_BANDS
    assert st.stats["stop_factors"] == r.STOP_FACTORS
    assert st.stats["sell_ratios"] == r.SELL_RATIOS
    assert st.stats["giveback_bands"] == r.GIVEBACK_BANDS
    for text in ("40%", "30%/20%", "1.04/1.10", "0.96/1.01/1.02", "remaining", "product", "5 trading", "50%", "0.01"):
        assert text in r.HELP_LOCK
    old = apply_csv_strategy("version9")
    assert not old["allow_add"]
    assert old["take_profit"](11, 10, 11, 1) == "profit_take:target"
    assert callable(old["stop_range"])


def fixture_bars():
    days = pd.bdate_range("2026-03-02", periods=10)
    frame = pd.DataFrame(dict(open=10., high=10., low=10., close=10.), index=days)
    frame.loc[days[0], ["open", "high", "low", "close"]] = 10.5
    return days, frame


def run_daily(frame, days, pool=None):
    start, end = days[1].strftime("%Y%m%d"), days[-1].strftime("%Y%m%d")
    return simulate({"600000.SH": frame}, pool or {start: ["600000.SH"]}, start, end,
                    strategy="version9_2")


def test_strategy9_2_daily_same_session_multi_add():
    days, frame = fixture_bars()
    frame.loc[days[1], ["high", "close"]] = [11., 11.]
    st = run_daily(frame, days)
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert [t["price"] for t in buys] == [10., 10.4, 11.]
    assert [t["shares"] for t in buys] == [40000, 28800, 18100]
    assert len({t["date"] for t in buys}) == 1
    mem = st.book_state["strategy9_2"]["600000.SH"]
    assert mem.units == 3 and mem.entry == 10 and mem.last_add_price == 11


def test_strategy9_2_daily_no_touch_and_hold5():
    days, frame = fixture_bars()
    st = run_daily(frame, days)
    buys = [t for t in st.trades if t["side"] == "BUY"]
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert len(buys) == len(sells) == 1
    assert sells[0]["reason"] == "force_sell:hold_days_5"
    assert sells[0]["date"] == days[7].strftime("%Y%m%d")


def test_strategy9_2_limit_down_pending():
    days, frame = fixture_bars()
    frame.loc[days[2], ["open", "high", "low", "close"]] = [9.,9.,9.,9.]
    frame.loc[days[3], ["open", "high", "low", "close"]] = [8.1,8.1,8.1,8.1]
    frame.loc[days[4]:, ["open", "high", "low", "close"]] = 8.5
    st = run_daily(frame, days)
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells[0]["date"] == days[4].strftime("%Y%m%d")
    assert st.stats["limit_down_pending"] == 1


@pytest.mark.parametrize("merged_bar", [False, True])
def test_strategy9_2_minute_same_day_and_t1_residual(merged_bar):
    from backtest.research.csv_minute_backtest import simulate as minute
    days, frame = fixture_bars()
    frame.loc[days[1], ["high", "close"]] = [11., 11.]
    rows = []
    for day in days:
        for hm in (570, 895, 896, 897, 898):
            px = 10.
            if day == days[1]:
                px = {570:10.,895:10.,896:10.4,897:11.,898:10.5}[hm]
            high = 11. if merged_bar and day == days[1] and hm == 896 else px
            rows.append(dict(time=day + pd.Timedelta(minutes=hm), hm=hm,
                             ymd=day.strftime("%Y%m%d"), open=px, high=high, low=px, close=high))
    minutes = pd.DataFrame(rows).set_index("time")
    start, end = days[1].strftime("%Y%m%d"), days[-1].strftime("%Y%m%d")
    st = minute({"600000.SH": minutes}, {"600000.SH":frame}, {start:["600000.SH"]},
                start, end, strategy="version9_2")
    buys = [t for t in st.trades if t["side"] == "BUY"]
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert [t["price"] for t in buys] == [10.,10.4,11.]
    assert len({t["date"] for t in buys}) == 1
    assert sells and all(t["date"] == days[2].strftime("%Y%m%d") for t in sells)
    assert sum(t["shares"] for t in sells) == sum(t["shares"] for t in buys)


def turtle_state():
    from backtest.research.csv_simulate_loop import init_sim_state
    return init_sim_state(apply_csv_strategy("version9_2"), total_cash=2_000_000,
                          bars_loaded=1, pool_days={})[0]


def test_strategy9_2_merged_partial_fill_and_no_refire():
    from backtest.research.csv_ledger import execute_buy
    from backtest.research.strategy9_2_engine import plan_exit, fill_pending
    st = turtle_state()
    execute_buy(st, "600000.SH", 10., 400_000, 0, pd.Timestamp("2026-03-02"), reason="pool")
    plan = plan_exit(st, "600000.SH", 20., None, [], day_i=1, ds="20260303")
    assert plan == ("profit_take:band:4", 27400)
    st.book_state["turtle_pending"] = {"600000.SH":plan}
    fill_pending(st, "600000.SH", SimpleNamespace(open=20.), pd.Timestamp("2026-03-03"),
                 day_i=1, ds="20260303", limits=(22.,18.))
    assert sum(p.shares for p in st.positions["600000.SH"]) == 12600
    assert plan_exit(st, "600000.SH", 20., None, [], day_i=1, ds="20260303") is None


def test_strategy9_2_partial_t1_residual_and_cost_memory():
    from backtest.research.csv_ledger import execute_buy
    from backtest.research.strategy9_2_engine import plan_exit, fill_pending, memory_for
    st = turtle_state()
    for idx, px, budget in [(0,10.,400_000),(1,10.4,300_000),(1,11.,200_000)]:
        execute_buy(st, "600000.SH", px, budget, idx, pd.Timestamp("2026-03-02"), reason="pool")
    mem = memory_for(st, "600000.SH")
    cost = mem.cost
    total = sum(p.shares for p in st.positions["600000.SH"])
    plan = plan_exit(st, "600000.SH", cost * 2, None, [], day_i=1, ds="20260303")
    st.book_state["turtle_pending"] = {"600000.SH":plan}
    fill_pending(st, "600000.SH", SimpleNamespace(open=cost * 2), pd.Timestamp("2026-03-03"),
                 day_i=1, ds="20260303", limits=(cost * 2.2,cost * 1.8))
    assert st.book_state["turtle_pending"]["600000.SH"][1] == plan[1] - 40000
    assert mem.cost == cost  # FIFO partial fills do not redefine the position's average.
    fill_pending(st, "600000.SH", SimpleNamespace(open=cost * 2), pd.Timestamp("2026-03-04"),
                 day_i=2, ds="20260304", limits=(cost * 2.2,cost * 1.8))
    assert "600000.SH" not in st.book_state["turtle_pending"]
    assert sum(p.shares for p in st.positions["600000.SH"]) == total - plan[1]


def test_strategy9_2_limit_up_add_skip_and_limit_down_next_day():
    from backtest.research.csv_ledger import execute_buy
    from backtest.research.strategy9_2_engine import adds, fill_pending
    st = turtle_state()
    day = pd.Timestamp("2026-03-02")
    execute_buy(st, "600000.SH", 10., 400_000, 0, day, reason="pool")
    adds(st, hooks=apply_csv_strategy("version9_2"), day_i=0, day=day, ds="20260302",
         names={}, quote=lambda c:(11., [10.], 11.), exdiv=None)
    assert len(st.trades) == 1 and st.stats["skip_limit_up"] == 1
    st.book_state["turtle_pending"] = {"600000.SH":("stop_loss:turtle_tier", 40000)}
    for px in (9., 9.5):
        fill_pending(st, "600000.SH", SimpleNamespace(open=px), day,
                     day_i=1, ds="20260303", limits=(11.,9.))
    assert len(st.trades) == 1
    fill_pending(st, "600000.SH", SimpleNamespace(open=9.5), day,
                 day_i=2, ds="20260304", limits=(11.,9.))
    assert st.trades[-1]["side"] == "SELL"


@pytest.mark.parametrize("host", ["daily", "minute"])
def test_strategy9_2_cli_stop_refused(host, tmp_path):
    from backtest.research.csv_daily_backtest import main as daily_main
    from backtest.research.csv_minute_backtest import main as minute_main
    with pytest.raises(SystemExit, match="stop-pct"):
        (daily_main if host == "daily" else minute_main)([
            "--strategy", "version9_2", "--start", "20260302", "--end", "20260303",
            "--pool-dir", str(tmp_path), "--stop-pct", ".1"])
