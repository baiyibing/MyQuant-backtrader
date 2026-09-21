"""Strategy 12 integrated paths: fills, clocks, state isolation and human cuts."""

import argparse

import numpy as np
import pandas as pd
import pytest

from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import strategy12_engine as book
from backtest.research import strategy12_rules as rules
from backtest.research.ashare_exdiv_economics import ExDivEvent
from backtest.research.ashare_volume_cap import BucketVolume
from backtest.research.csv_ledger import Position, execute_buy
from backtest.research.csv_simulate_loop import init_sim_state, run_buybacks_day, run_step_adds_day
from backtest.research.csv_strategy_books import apply_csv_strategy, get_book, add_csv_strategy_arg

CODE = "300001.SZ"


def bars_for(paths, *, daily_closes=None):
    days = pd.bdate_range("2025-11-03", periods=len(paths))
    history = pd.bdate_range(end=days[0] - pd.Timedelta(days=1), periods=12)
    closes = [10.] * len(paths) if daily_closes is None else daily_closes
    values = [10.] * len(history) + closes
    daily_frame = pd.DataFrame({key: values for key in ("open", "high", "low", "close")},
                                index=history.append(days))
    rows = []
    for day, prices in zip(days, paths):
        for hm, px in prices:
            rows.append(dict(time=day + pd.Timedelta(minutes=hm), ymd=day.strftime("%Y%m%d"),
                             hm=hm, open=px, high=px, close=px))
    frame = pd.DataFrame(rows).set_index("time")
    return {CODE: frame}, {CODE: daily_frame}, days


def minute_run(prices, *, caps=None, total_cash=100_000, extra_days=(), pool=None):
    paths = [[(895, 10.)], prices, *extra_days]
    mins, days, dates = bars_for(paths)
    kwargs = {}
    if caps is not None:
        lookup = {(CODE, "20251103", 895): BucketVolume(1000, 895, "raw_shares_incremental")}
        lookup.update({(CODE, "20251104", hm): BucketVolume(q, hm, "raw_shares_incremental")
                       for (hm, _), q in zip(prices, caps)})
        kwargs = dict(participation_rate=1, volume_for_bucket=lookup)
    return minute.simulate(mins, days, {"20251103": [CODE]} if pool is None else pool,
                           "20251103", dates[-1].strftime("%Y%m%d"), strategy="12",
                           name_budget=10000, total_cash=total_cash, **kwargs)


def fills(st):
    return [(t["reason"], t["shares"]) for t in st.trades if t["side"] in ("BUY", "SELL")]


def state():
    hooks = apply_csv_strategy("12", name_budget=10000)
    st = init_sim_state(hooks, total_cash=100_000, bars_loaded=1, pool_days={})[0]
    return st, hooks


def test_minute_cycle_rearms_same_day_and_new_buys_remain_t1_locked():
    st = minute_run([(600, 9.9), (601, 10), (602, 9.9), (603, 10),
                     (604, 8.9), (605, 10), (606, 8.9)])
    assert fills(st) == [("pool", 1000), (rules.REDUCE, 500), (rules.RECLAIM5, 500),
                         (rules.REDUCE, 200), (rules.RECLAIM5, 200),
                         (rules.STOP, 300), (rules.RECLAIM10, 300)]
    assert sum(p.shares for p in st.positions[CODE]) == 1000
    assert all(p.entry_idx == 1 for p in st.positions[CODE])
    assert book.memory_for(st, CODE).reduced == rules.Memory()
    assert book.memory_for(st, CODE).stopped == rules.Memory()


@pytest.mark.parametrize("channel,px,reason,reclaim", [
    ("reduced", 9.9, rules.REDUCE, rules.RECLAIM5),
    ("stopped", 8.9, rules.STOP, rules.RECLAIM10),
])
def test_capacity_residual_retained_rearmed_then_merged(channel, px, reason, reclaim):
    first = minute_run([(600, px), (601, 10)], caps=[150, 100])
    mem = getattr(book.memory_for(first, CODE), channel)
    assert (mem.shares, mem.latched) == (50, False)
    assert fills(first) == [("pool", 1000), (reason, 150), (reclaim, 100)]
    full = minute_run([(600, px), (601, 10), (602, px), (603, 10)], caps=[150, 100, 250, 300])
    assert fills(full) == [("pool", 1000), (reason, 150), (reclaim, 100),
                           (reason, 250), (reclaim, 300)]
    assert getattr(book.memory_for(full, CODE), channel) == rules.Memory()
    assert sum(p.shares for p in full.positions[CODE]) == 1000


@pytest.mark.parametrize("channel,px,reason", [("reduced", 9.9, rules.REDUCE),
                                              ("stopped", 8.9, rules.STOP)])
def test_residual_below100_qualified_reclaim_without_buy(channel, px, reason):
    first = minute_run([(600, px), (601, 10)], caps=[50, 1000])
    mem = getattr(book.memory_for(first, CODE), channel)
    assert (mem.shares, mem.latched) == (50, False)
    assert fills(first) == [("pool", 1000), (reason, 50)]
    full = minute_run([(600, px), (601, 10), (602, px)], caps=[50, 1000, 50])
    assert getattr(book.memory_for(full, CODE), channel).shares == 100
    assert fills(full)[-1] == (reason, 50)


def test_uninterrupted_below_cycle_does_not_reduce_again_on_later_days():
    st = minute_run([(600, 9.9)], extra_days=[[(600, 9.9)], [(600, 9.9)]])
    assert fills(st) == [("pool", 1000), (rules.REDUCE, 500)]
    assert book.memory_for(st, CODE).reduced == rules.Memory(500, True)


def test_stopped_memory_survives_flat_position_until_later_day_reclaim():
    st = minute_run([(600, 8.9)], extra_days=[[(600, 10)]])
    assert fills(st) == [("pool", 1000), (rules.STOP, 1000), (rules.RECLAIM10, 1000)]
    assert st.positions[CODE][0].entry_idx == 2


def test_insufficient_cash_keeps_memory_and_latch():
    st = minute_run([(600, 9.9), (601, 10)], total_cash=10010)
    assert fills(st) == [("pool", 1000), (rules.REDUCE, 500)]
    assert st.stats["skip_cash"] == 1
    assert st.stats["skip_cash_notional"] == 5000
    assert book.memory_for(st, CODE).reduced == rules.Memory(500, True)


def test_cash_retry_and_capacity_failure_do_not_rearm_early():
    st = minute_run([(600, 9.9), (601, 10), (602, 10)], caps=[500, 0, 200])
    assert fills(st)[-1] == (rules.RECLAIM5, 200)
    assert book.memory_for(st, CODE).reduced == rules.Memory(300, True)
    assert st.stats["skip_volume_cap"] == 1


def test_pool_fill_clears_both_memories_before_same_clock_buyback():
    st = minute_run([(600, 9.9), (601, 8.9), (895, 10)],
                    pool={"20251103": [CODE], "20251104": [CODE]})
    assert fills(st) == [("pool", 1000), (rules.REDUCE, 500), (rules.STOP, 500), ("pool", 1000)]
    assert book.memory_for(st, CODE).reduced == rules.Memory()
    assert book.memory_for(st, CODE).stopped == rules.Memory()


def test_dual_channels_reclaim_independently_after_same_day_stop():
    st = minute_run([(600, 9.9), (601, 8.9), (602, 10)])
    assert fills(st) == [("pool", 1000), (rules.REDUCE, 500), (rules.STOP, 500),
                         (rules.RECLAIM5, 500), (rules.RECLAIM10, 500)]


def test_chase_and_pool_use_existing_clocks_and_chase_resets_memory():
    paths = [[(895, 12.)], [(570, 10.), (585, 10.1), (600, 9.9), (895, 10.)]]
    mins, days, dates = bars_for(paths)
    st = minute.simulate(mins, days, {"20251103": [CODE], "20251104": [CODE]},
                          "20251103", "20251104", strategy="12", name_budget=10000)
    assert [t[0] for t in fills(st)] == ["chase:T+1", "pool"]
    assert st.stats["chase_buy"] == 1 and st.stats["chase_explained"] == 1
    assert all(p.entry_idx == 1 for p in st.positions[CODE])
    # Callback contract: a successful chase clears pre-existing dual memory.
    mem = book.memory_for(st, CODE)
    mem.reduced.sold(500)
    mem.stopped.sold(500)
    assert execute_buy(st, CODE, 10, 10000, 2, "20251105", reason="chase:T+1")
    assert mem.reduced == mem.stopped == rules.Memory()


def test_step_counter_remains_monotonic_after_step_lot_is_sold():
    st, hooks = state()
    assert execute_buy(st, CODE, 10, 10000, 0, "20251103")
    kwargs = dict(day_i=1, day="20251104", ds="20251104", names={}, sizing="per_name",
                  name_budget=10000, buy_quote_for=lambda code: (12.01, [11.] * 10),
                  step_add=lambda lots, px: rules.step_add_due(lots, px, memory=book.memory_for(st, CODE)))
    run_step_adds_day(st, **kwargs)
    assert book.memory_for(st, CODE).steps == 1
    step = st.positions[CODE][-1]
    assert step.is_step
    plan = book.plan_exit(st, CODE, 9.9, "20251105", [10.] * 10, day_i=2, ds="20251105")
    assert plan == (rules.REDUCE, 900)
    assert book.fill_exit(st, CODE, 9.9, "20251105", day_i=2, ds="20251105", plan=plan,
                          limits=(12., 8.), open_px=9.9) == 900
    assert step not in st.positions[CODE]
    run_step_adds_day(st, **kwargs)
    assert len([t for t in st.trades if t["side"] == "BUY"]) == 2
    assert book.memory_for(st, CODE).steps == 1


@pytest.mark.parametrize("engine", [daily, minute])
@pytest.mark.parametrize("held", [False, True])
def test_exdiv_scaling_is_explicit_deduplicated_and_covers_flat_memory(monkeypatch, engine, held):
    real_init = engine.init_sim_state

    def seeded(*args, **kwargs):
        st, pending, names = real_init(*args, **kwargs)
        if held:
            st.positions[CODE] = [Position(CODE, 1000, 10, -1, 10)]
        mem = book.memory_for(st, CODE)
        mem.reduced = rules.Memory(150, True)
        mem.stopped = rules.Memory(250, True)
        return st, pending, names

    monkeypatch.setattr(engine, "init_sim_state", seeded)
    mins, days, dates = bars_for([[(600, 9.8), (601, 9.8)]], daily_closes=[9.8])
    event = ExDivEvent("s12-bonus", .5, 0, "20251103", "20251103", "20251105")
    args = (days, {}, "20251103", "20251103") if engine is daily else (mins, days, {}, "20251103", "20251103")
    baseline = engine.simulate(*args, strategy="12")
    assert book.memory_for(baseline, CODE).reduced.shares == 150
    st = engine.simulate(*args, strategy="12", exdiv_economics={(CODE, "20251103"): event})
    assert book.memory_for(st, CODE).reduced.shares == 200
    assert book.memory_for(st, CODE).stopped.shares == 300
    assert st.stats["strategy12_exdiv_reduced_residual"] == 25
    assert st.stats["strategy12_exdiv_stopped_residual"] == 75
    assert st.stats["exdiv_econ_events"] == 1
    if held:
        assert st.positions[CODE][0].shares == 1500
        assert book.sell_lots(st, CODE, 0, "20251103")[0].sellable == 1000


def test_buyback_limit_up_preserves_whole_lot_memory():
    st, hooks = state()
    book.memory_for(st, CODE).reduced.sold(500)
    run_buybacks_day(st, day_i=1, day="20251104", ds="20251104", names={}, codes=[CODE],
                     buy_quote_for=lambda code: (12, [10.] * 10),
                     buyback_plan=hooks["buyback_plan"], on_reclaim=hooks["on_reclaim"])
    assert not st.trades and st.stats["skip_limit_up"] == 1
    assert book.memory_for(st, CODE).reduced == rules.Memory(500, True)


def test_daily_signal_uses_next_open_and_reclaims_at_close():
    _, bars, dates = bars_for([[(895, 10)], [(895, 9.9)], [(895, 10)]], daily_closes=[10, 9.9, 10])
    bars[CODE].loc[dates[2], "open"] = 9.8
    st = daily.simulate(bars, {"20251103": [CODE]}, "20251103", "20251105",
                        strategy="12", name_budget=10000)
    assert fills(st) == [("pool", 1000), (rules.REDUCE, 500), (rules.RECLAIM5, 500)]
    sale = next(t for t in st.trades if t["side"] == "SELL")
    assert (sale["date"], sale["price"], sale["price_rule"]) == ("20251105", 9.8, "daily_pending_next_open")
    assert all(not p.pending_exit for p in st.positions[CODE])


def test_daily_limit_down_defers_independent_partial_queue():
    _, bars, dates = bars_for([[(895, 10)], [(895, 9.9)], [(895, 9.9)], [(895, 10)]],
                              daily_closes=[10, 9.9, 9.9, 10])
    bars[CODE].loc[dates[2], "open"] = 7.92
    bars[CODE].loc[dates[3], "open"] = 9.8
    st = daily.simulate(bars, {"20251103": [CODE]}, "20251103", "20251106",
                        strategy="12", name_budget=10000)
    assert fills(st) == [("pool", 1000), (rules.REDUCE, 500), (rules.RECLAIM5, 500)]
    sale = next(t for t in st.trades if t["side"] == "SELL")
    assert sale["date"] == "20251106" and st.stats["defer_sell_limit_down"] == 1


def test_scanner_keeps_five_tuple_and_reports_partial_size_out_param():
    out = {}
    result = minute.scan_held_day(np.array([9.9]), np.array([9.9]), np.array([9.9]),
                                  cost=10, peak=10, n_days=1, can_sell=True, stop_pct=None,
                                  profit_base=0, trail_ratio=0, use_numba=True,
                                  exit_plan=lambda *args: (rules.REDUCE, 500), exit_state=out)
    assert len(result) == 5 and result[2] == rules.REDUCE
    assert out == {"shares": 500}


def test_memory_is_per_run_and_wiring_does_not_inherit_v8_exits():
    st1 = minute_run([(600, 9.9)])
    st2 = minute_run([(600, 10)])
    assert book.memory_for(st1, CODE).reduced.shares == 500
    assert book.memory_for(st2, CODE).reduced.shares == 0
    hooks = apply_csv_strategy("version12")
    assert hooks["take_profit"](1, 2, 3, 4) is None
    assert hooks["stop_pct"] is None
    assert hooks["reserve_limit_up"] is hooks["defer_limit_up"] is False
    assert hooks["daily_same_bar_prefixes"] == ()
    assert hooks["peak_gap_min"] == 0
    assert hooks["allow_new_name"] is None
    assert (hooks["sizing"], hooks["name_budget"]) == ("per_name", 1_000_000)


@pytest.mark.parametrize("alias", ["12", "v12", "version12"])
def test_cli_alias_registration(alias):
    parser = argparse.ArgumentParser()
    add_csv_strategy_arg(parser)
    assert parser.parse_args(["--strategy", alias]).strategy == "version12"
    assert get_book(alias).tag == "v12"


def test_new_cli_aliases_do_not_expand_existing_book_cli_contract():
    parser = argparse.ArgumentParser()
    add_csv_strategy_arg(parser)
    with pytest.raises(SystemExit):
        parser.parse_args(["--strategy", "v8"])


@pytest.mark.parametrize("engine", [daily, minute])
def test_run_rejects_wrong_price_domain_before_data_reads(engine):
    with pytest.raises(ValueError, match="front"):
        engine.run("20251103", "20251104", strategy="12")


@pytest.mark.parametrize("engine", [daily, minute])
def test_front_loader_uses_matching_partitions_and_disables_er6(monkeypatch, tmp_path, engine):
    from common.infra import data_root

    mins, days, dates = bars_for([[(895, 10)]])
    for period in ("1d", "1m"):
        (tmp_path / period / "dividend_type=front").mkdir(parents=True)
    monkeypatch.setattr(data_root, "resolve_period_root", lambda period: tmp_path / period)
    if engine is daily:
        monkeypatch.setattr(engine, "resolve_period_root", data_root.resolve_period_root)
    monkeypatch.setattr(engine, "load_pool_day_map", lambda *a, **kw: {"20251103": [CODE]})
    monkeypatch.setattr(engine, "load_pool_names_by_day", lambda *a, **kw: {})
    captured = {}

    def daily_load(codes, start, end, **kwargs):
        assert kwargs["dividend_type"] == "front"
        assert start <= "20251012"  # 22 calendar days, enough MA10 warmup slack.
        return days

    def minute_load(codes, start, end, **kwargs):
        assert kwargs["lake_root"] == tmp_path / "1m/dividend_type=front"
        return mins

    def no_er6(*args, **kwargs):
        raise AssertionError("front must not load E-R6 raw reference ratios")

    real_simulate = engine.simulate

    def simulate(*args, **kwargs):
        captured.update(kwargs)
        return real_simulate(*args, **kwargs)

    monkeypatch.setattr(engine, "load_daily_ohlc", daily_load)
    monkeypatch.setattr(engine, "load_exdiv_ratios", no_er6)
    monkeypatch.setattr(engine, "simulate", simulate)
    if engine is minute:
        monkeypatch.setattr(engine, "_load_minute_from_lake", minute_load)
    st = engine.run("20251103", "20251103", strategy="12", dividend_type="front")
    assert captured["exdiv"] is None
    assert st.stats["price_domain"] == "front"
    assert fills(st)[0] == ("pool", 100000)


@pytest.mark.parametrize("engine", [daily, minute])
def test_front_missing_partition_fails_instead_of_empty_data(monkeypatch, tmp_path, engine):
    from common.infra import data_root

    monkeypatch.setattr(data_root, "resolve_period_root", lambda period: tmp_path / period)
    if engine is daily:
        monkeypatch.setattr(engine, "resolve_period_root", data_root.resolve_period_root)
    monkeypatch.setattr(engine, "load_pool_day_map", lambda *a, **kw: {"20251103": [CODE]})
    monkeypatch.setattr(engine, "load_pool_names_by_day", lambda *a, **kw: {})
    with pytest.raises(FileNotFoundError, match="front daily partition"):
        engine.run("20251103", "20251103", strategy="12", dividend_type="front")


def test_locked_bonus_is_excluded_from_reduction_base_and_fill_memory():
    from backtest.research.ashare_exdiv_economics import ExDivEconomics

    st, _ = state()
    pos = Position(CODE, 1500, 10, 0, 10)
    st.positions[CODE] = [pos]
    st.exdiv_economics = ExDivEconomics({})
    st.exdiv_economics.bonus_locks[id(pos)] = {"20251105": 500}
    plan = book.plan_exit(st, CODE, 9.9, "20251104", [10.] * 10, day_i=1, ds="20251104")
    assert plan == (rules.REDUCE, 500)
    assert book.fill_exit(st, CODE, 9.9, "20251104", day_i=1, ds="20251104", plan=plan,
                          limits=(12., 8.), open_px=9.9) == 500
    assert book.memory_for(st, CODE).reduced.shares == 500
    assert pos.shares == 1000


@pytest.mark.parametrize("channel", ["reduced", "stopped"])
def test_daily_sub100_no_buy_qualified_reclaim_rearms_without_clearing(monkeypatch, channel):
    real_init = daily.init_sim_state

    def seeded(*args, **kwargs):
        st, pending, names = real_init(*args, **kwargs)
        getattr(book.memory_for(st, CODE), channel).sold(50)
        return st, pending, names

    monkeypatch.setattr(daily, "init_sim_state", seeded)
    _, bars, _ = bars_for([[(895, 10)]])
    st = daily.simulate(bars, {}, "20251103", "20251103", strategy="12")
    assert getattr(book.memory_for(st, CODE), channel) == rules.Memory(50, False)
    assert fills(st) == []


def test_daily_stop_keeps_odd_residual_and_merges_next_stop(monkeypatch):
    real_init = daily.init_sim_state

    def seeded(*args, **kwargs):
        st, pending, names = real_init(*args, **kwargs)
        st.positions[CODE] = [Position(CODE, 1050, 10, -1, 10)]
        return st, pending, names

    monkeypatch.setattr(daily, "init_sim_state", seeded)
    _, bars, dates = bars_for([[(895, px)] for px in (8.8, 10, 8.8, 10)],
                              daily_closes=[8.8, 10, 8.8, 10])
    bars[CODE].loc[dates[1], "open"] = 8.8
    bars[CODE].loc[dates[3], "open"] = 8.8
    st = daily.simulate(bars, {}, "20251103", "20251106", strategy="12")
    assert fills(st) == [(rules.STOP, 1050), (rules.RECLAIM10, 1000),
                         (rules.STOP, 1000), (rules.RECLAIM10, 1000)]
    assert book.memory_for(st, CODE).stopped == rules.Memory(50, False)
