"""X-01 integrated dual-domain failures, repaired paths and rule invariants."""

from decimal import Decimal

import pandas as pd
import pytest
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_simulate_loop as loop
from backtest.research import strategy12_engine as engine
from backtest.research import strategy12_rules as rules
from backtest.research.ashare_exdiv_economics import ExDivEvent
from backtest.research.csv_ledger import Position, SimState
from backtest.research.csv_strategy_books import apply_csv_strategy
from scripts.research.audit_s12_price_domain import (
    CODE,
    START,
    context_for,
    fixture,
    money,
    replay,
    transformed,
)

from tests import test_strategy12_engine as legacy


def fills(st):
    return [t for t in st.trades if t["side"] in ("BUY", "SELL")]


@pytest.mark.parametrize("factor,off_first_nav,off_fills", [
    (.5, 5_000_000, 0), (.96, 4_959_000, 1), (1, 4_999_000, 1),
    (1.05, 5_049_000, 2), (1.2, 5_199_000, 1),
])
def test_constant_raw_price_off_reproduces_mixing_on_repairs_accounts(
        factor, off_first_nav, off_fills):
    data = fixture(factor=factor)
    off, _ = replay(*data, enabled=False, factor=factor)
    on, events = replay(*data, enabled=True, factor=factor)
    assert money(off.equity_curve[0][1]) == money(off_first_nav)
    assert len(fills(off)) == off_fills
    assert [(t["side"], t["price"], t["shares"]) for t in fills(on)] == [("BUY", 10., 100_000)]
    assert all(money(value) == Decimal("4999000.00") for _, value in on.equity_curve)
    assert [(t["price"], t["shares"]) for t in on.trades if t["side"] == "EOD_MARK"] == [(10., 100_000)]
    fees = sum(t["commission"] for t in fills(on))
    assert money(on.cash + 100_000 * 10 + fees) == Decimal("5000000.00")
    assert events[0]["hm"] == events[0]["decision_hm"] == events[0]["quote_hm"] == 895
    assert events[0]["cash_residual_fen"] == "0.00"
    assert events[0]["share_residual"] == events[0]["volume_residual"] == 0
    if factor == 1:
        assert off.trades == on.trades and off.equity_curve == on.equity_curve
    if factor == 1.05:
        assert [(t["reason"], t["shares"]) for t in fills(off)][-1] == (rules.REDUCE, 50_000)
    if factor == 1.2:
        assert off.stats["defer_sell_limit_down"] == 0  # the existing scan suppresses it first


def test_false_limit_chase_queue_first_day_and_two_day_terminal_state():
    one = fixture(paths=[[(895, 10.)]])
    two = fixture()
    off_one, _ = replay(*one, enabled=False)
    on_one, _ = replay(*one, enabled=True)
    off_two, _ = replay(*two, enabled=False)
    on_two, _ = replay(*two, enabled=True)
    assert off_one.stats["chase_pending_eod"] == 1
    assert off_two.stats["chase_pending_eod"] == 0
    assert off_two.stats["chase_skip_limit"] == 1 and off_two.stats["chase_buy"] == 0
    assert on_one.stats["chase_pending_eod"] == on_two.stats["chase_pending_eod"] == 0
    assert len(fills(on_two)) == 1 and on_two.stats["chase_buy"] == 0


def test_false_chase_queue_can_propagate_to_delayed_real_buy():
    data = fixture(paths=[[(895, 10.)], [(570, 5.), (585, 5.1)]])
    off, off_events = replay(*data, enabled=False)
    on, on_events = replay(*data, enabled=True)
    assert [(t["reason"], t["price"]) for t in fills(off)] == [("chase:T+1", 5.1)]
    assert off_events[0]["hm"] == 585
    assert on_events[0]["reason"] == "pool" and on_events[0]["hm"] == 895
    assert on.stats["chase_buy"] == 0


REPLAYS = [
    ("test_minute_cycle_rearms_same_day_and_new_buys_remain_t1_locked", ()),
    ("test_capacity_residual_retained_rearmed_then_merged", ("reduced", 9.9, rules.REDUCE, rules.RECLAIM5)),
    ("test_capacity_residual_retained_rearmed_then_merged", ("stopped", 8.9, rules.STOP, rules.RECLAIM10)),
    ("test_residual_below100_qualified_reclaim_without_buy", ("reduced", 9.9, rules.REDUCE)),
    ("test_residual_below100_qualified_reclaim_without_buy", ("stopped", 8.9, rules.STOP)),
    ("test_cash_retry_and_capacity_failure_do_not_rearm_early", ()),
    ("test_pool_fill_clears_both_memories_before_same_clock_buyback", ()),
    ("test_dual_channels_reclaim_independently_after_same_day_stop", ()),
    ("test_chase_and_pool_use_existing_clocks_and_chase_resets_memory", ()),
]


@pytest.mark.parametrize("name,args", REPLAYS, ids=[n[5:] + str(i) for i, (n, _) in enumerate(REPLAYS)])
def test_existing_s12_rules_replayed_on_nonunit_domain(monkeypatch, name, args):
    original = minute.simulate

    def with_context(mins, raw, *positional, **kwargs):
        front = transformed(raw, .5)
        ctx = context_for(front, raw, mins)
        return original(mins, raw, *positional, fix_s12_price_domain=True,
                        s12_price_context=ctx, **kwargs)

    monkeypatch.setattr(minute, "simulate", with_context)
    getattr(legacy, name)(*args)


@pytest.mark.parametrize("name,helper", [
    ("test_step_counter_remains_monotonic_after_step_lot_is_sold", "run_step_adds_day"),
    ("test_buyback_limit_up_preserves_whole_lot_memory", "run_buybacks_day"),
])
def test_existing_direct_helpers_replayed_with_nonunit_context(monkeypatch, name, helper):
    original = getattr(loop, helper)

    def with_reference(st, **kwargs):
        quote = kwargs["buy_quote_for"]
        code = legacy.CODE
        px, closes = quote(code)
        day = pd.Timestamp(kwargs["ds"])
        index = pd.bdate_range(end=day, periods=len(closes) + 1)
        values = [*closes, closes[-1]]
        raw = {code: pd.DataFrame({c: values for c in ("open", "high", "low", "close")}, index=index)}
        front = transformed(raw, .5)
        mins = {code: pd.DataFrame({"ymd": [kwargs["ds"]], "hm": [895],
                                   "open": [px], "high": [px], "close": [px]},
                                  index=[day + pd.Timedelta(minutes=895)])}
        ctx = context_for(front, raw, mins)
        kwargs["buy_quote_for"] = lambda c: (quote(c)[0], ctx.previous_signal_closes_in_raw_domain(c, day))
        kwargs["reference_price_for"] = ctx.reference_price_for
        return original(st, **kwargs)

    monkeypatch.setattr(legacy, helper, with_reference)
    getattr(legacy, name)()


@pytest.mark.parametrize("channel", ["pool", "chase", "step", "reclaim"])
@pytest.mark.parametrize("px,blocked", [(1.10, False), (1.11, True), (1.12, True),
                                         (.90, False), (.91, False), (.92, False)])
def test_all_buy_routes_use_separate_rounded_raw_reference(channel, px, blocked):
    mins, raw, front, days = fixture(paths=[[(895, px)]], historical=1.014)
    ctx = context_for(front, raw, mins)
    assert ctx.reference_price_for(CODE, days[0]) == 1.01
    history = ctx.previous_signal_closes_in_raw_domain(CODE, days[0])
    assert history[-1] == 1.014  # the MA input itself must not be rounded

    def run(reference):
        hooks = apply_csv_strategy("12", name_budget=1000)
        st, pending, _ = loop.init_sim_state(hooks, total_cash=10_000, bars_loaded=1, pool_days={})
        common = {"day_i": 1, "day": START, "ds": START, "names": {},
                  "reference_price_for": reference}
        quote = lambda c: (px, history)
        if channel == "pool":
            loop.run_pool_buys_day(st, pending, pool_days={START: [CODE]}, daily_quota=1000,
                                  allow_add=True, buy_gate=None, buy_quote_for=quote,
                                  sizing="per_name", name_budget=1000, **common)
        elif channel == "chase":
            pending[CODE] = (1000, 0)
            loop.run_chase_due_day(st, pending, allow_add=True, buy_gate=None,
                                  quotes_for=lambda c: (px - .01, px, history), **common)
        elif channel == "step":
            st.positions[CODE] = [Position(CODE, 100, .5, 0, .5)]
            loop.run_step_adds_day(st, buy_quote_for=quote, sizing="per_name", name_budget=1000,
                                  step_add=lambda lots, price: True, **common)
        else:
            engine.memory_for(st, CODE).reduced.sold(500)
            # Explicit plan isolates the shared fill/limit contract from reclaim threshold.
            loop.run_buybacks_day(st, codes=[CODE], buy_quote_for=quote,
                                 buyback_plan=lambda *a: [(rules.RECLAIM5, 500)],
                                 on_reclaim=hooks["on_reclaim"], **common)
        return st

    on = run(ctx.reference_price_for)
    assert bool(fills(on)) is not blocked
    if px == 1.11:
        assert fills(run(None))  # old unrounded 1.014 computes the incorrect 1.12 limit


@pytest.mark.parametrize("px,should_sell", [(.90, False), (.905, False), (.91, False), (.92, True)])
def test_sell_uses_same_rounded_reference_at_limit_down_one_cent(monkeypatch, px, should_sell):
    # 1.005 -> 1.01 -> limit down 0.91 blocks 0.905; unrounded 1.005 -> 0.90 would sell.
    data = fixture(paths=[[(600, px)]], historical=1.005)
    original = minute.init_sim_state

    def seeded(*args, **kwargs):
        st, pending, names = original(*args, **kwargs)
        st.positions[CODE] = [Position(CODE, 1000, 1.005, -1, 1.005)]
        return st, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seeded)
    st, _ = replay(*data, enabled=True, pool={})
    assert bool(fills(st)) is should_sell
    assert sum(p.shares for p in st.positions[CODE]) == (500 if should_sell else 1000)


def test_nonzero_offset_stop_reanchors_before_multiplying_point_nine(monkeypatch):
    data = fixture(paths=[[(600, 10.85)]], historical=12., daily_closes=[10.], factor=1, offset=-1)
    original = minute.init_sim_state

    def seeded(*args, **kwargs):
        st, pending, names = original(*args, **kwargs)
        st.positions[CODE] = [Position(CODE, 1000, 12., -1, 12.)]
        return st, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seeded)
    on, _ = replay(*data, enabled=True, factor=1, offset=-1, pool={})
    off, _ = replay(*data, enabled=False, factor=1, offset=-1, pool={})
    assert [(t["reason"], t["shares"]) for t in fills(on)] == [(rules.REDUCE, 500)]
    # Wrong 0.9 * front-MA then inverse gives 10.9 and would sell all shares.
    ma_raw = context_for(data[2], data[1], data[0], factor=1, offset=-1).day_signal_view(
        CODE, START).previous_signal_closes_in_raw_domain
    stop_raw = sum(ma_raw[-10:]) / 10 * .9
    assert stop_raw == pytest.approx(10.8)
    assert stop_raw < float(data[0][CODE].iloc[0]["close"]) < 10.9
    assert all(t["reason"] != rules.STOP for t in fills(on))
    assert [(t["reason"], t["shares"]) for t in fills(off)] == [(rules.REDUCE, 500)]


@pytest.mark.parametrize("factor,offset,future_scale,future_shift", [(.5, 0, .8, 0), (1, -1, .8, .3)])
def test_extended_future_common_anchor_preserves_complete_fill_prefix(factor, offset, future_scale, future_shift):
    paths = [[(895, 10.)], [(600, 9.9), (601, 10.), (602, 9.9), (603, 10.)]]
    short = fixture(paths=paths, factor=factor, offset=offset)
    extended = fixture(paths=[*paths, [(895, 10.)]],
                       factor=factor * future_scale, offset=offset * future_scale + future_shift)
    first, events_first = replay(*short, enabled=True, factor=factor, offset=offset)
    later, events_later = replay(*extended, enabled=True, factor=factor * future_scale,
                                offset=offset * future_scale + future_shift)
    assert fills(first) == [t for t in fills(later) if t["date"] <= "20251104"]
    assert first.equity_curve == later.equity_curve[:2]
    assert events_first == [e for e in events_later if e["date"] <= "20251104"]


def test_intraday_decisions_do_not_depend_on_today_close():
    first = fixture(paths=[[(895, 10.)], [(600, 9.9), (601, 10.)]])
    mins, raw, _, days = first
    changed = {code: frame.copy(deep=True) for code, frame in raw.items()}
    changed[CODE].loc[days[-1], ["high", "close"]] = 20.
    second = mins, changed, transformed(changed), days
    normal, normal_events = replay(*first, enabled=True)
    extreme, extreme_events = replay(*second, enabled=True)
    assert fills(normal) == fills(extreme) and normal_events == extreme_events
    assert money(extreme.equity_curve[-1][1] - normal.equity_curve[-1][1]) == Decimal("1000000.00")


@pytest.mark.parametrize("economic", [False, True])
def test_ten_for_ten_cash_then_second_action_do_not_implicitly_duplicate_economics(economic):
    paths = [[(895, 10.)], [(600, 5.)], [(600, 4.5)], [(600, 2.25)]]
    mins, raw, _, days = fixture(paths=paths, daily_closes=[10., 5., 4.5, 2.25])
    # Exact frozen action-adjusted history: 10 -> 5 -> 4.5 -> 2.25.
    front = transformed(raw, 1)
    front[CODE].loc[:, ["open", "high", "low", "close"]] = 2.25
    transforms = {}
    for day in raw[CODE].index:
        if day <= days[0]:
            a, b = .25, -.25
        elif day == days[1]:
            a, b = .5, -.25
        elif day == days[2]:
            a, b = .5, 0
        else:
            a, b = 1, 0
        transforms[(CODE, day.strftime("%Y%m%d"))] = {"A": str(a), "B": str(b)}
    ctx = context_for(front, raw, mins, transforms=transforms)
    for day, expected in zip(days[1:], (5., 4.5, 2.25)):
        assert ctx.previous_signal_closes_in_raw_domain(CODE, day) == [expected] * len(
            raw[CODE].loc[raw[CODE].index < day])
        assert ctx.reference_price_for(CODE, day) == expected
    kwargs = {}
    if economic:
        kwargs["exdiv_economics"] = {
            (CODE, "20251104"): ExDivEvent("bonus-1", 1, 0, "20251104", "20251104"),
            (CODE, "20251105"): ExDivEvent("cash-1", 0, .5, "20251105", "20251105"),
            (CODE, "20251106"): ExDivEvent("bonus-2", 1, 0, "20251106", "20251106"),
        }
    st, _ = replay(mins, raw, front, days, enabled=True, ctx=ctx, **kwargs)
    assert len(fills(st)) == 1
    assert sum(p.shares for p in st.positions[CODE]) == (400_000 if economic else 100_000)
    assert money(st.cash) == money(4_099_000 if economic else 3_999_000)
    assert money(st.equity_curve[-1][1]) == money(4_999_000 if economic else 4_224_000)
    assert st.stats.get("exdiv_adjusted_lots", 0) == 0
    if economic:
        assert st.stats["exdiv_econ_events"] == 3


def test_missing_market_mark_fails_before_any_equity_or_eod_append_and_off_falls_back():
    day = pd.Timestamp(START)
    st = SimState(cash=100, positions={CODE: [Position(CODE, 100, 10, -1, 10)]})
    with pytest.raises((ValueError, FileNotFoundError), match=CODE):
        loop.append_equity_and_eod_marks(st, ds=START, day=day, calendar_last=day,
                                        mark_bars={}, require_market_mark=True)
    assert st.equity_curve == [] and st.trades == []
    loop.append_equity_and_eod_marks(st, ds=START, day=day, calendar_last=day, mark_bars={})
    assert st.equity_curve == [(START, 1100)] and st.trades[0]["price"] == 10


def test_normal_suspension_uses_latest_prior_raw_mark():
    day = pd.Timestamp(START)
    raw = {CODE: pd.DataFrame({"close": [9.]}, index=[day - pd.Timedelta(days=3)])}
    st = SimState(cash=100, positions={CODE: [Position(CODE, 100, 10, -1, 10)]})
    loop.append_equity_and_eod_marks(st, ds=START, day=day, calendar_last=day,
                                    mark_bars=raw, require_market_mark=True)
    assert st.equity_curve == [(START, 1000)] and st.trades[0]["price"] == 9.


def test_on_simulation_rejects_unmarked_holding_before_writing_equity(monkeypatch):
    mins, raw, front, _days = fixture(paths=[[(895, 10.)]])
    ctx = context_for(front, raw, mins)
    original = minute.init_sim_state
    states = []
    missing_code = "600001.SH"

    def seeded(*args, **kwargs):
        st, pending, names = original(*args, **kwargs)
        st.positions[missing_code] = [Position(missing_code, 100, 10, -1, 10)]
        states.append(st)
        return st, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seeded)
    with pytest.raises(ValueError, match=f"raw mark code={missing_code}.*domain=none"):
        minute.simulate(mins, raw, {}, START, START, strategy="12",
                        fix_s12_price_domain=True, s12_price_context=ctx)
    assert states[0].trades == [] and states[0].equity_curve == []


def test_on_run_routes_raw_daily_and_uses_only_strict_uncached_loader(monkeypatch, tmp_path):
    from backtest.research import signal_price_domain as domain

    mins, raw, front, days = fixture()
    ctx = context_for(front, raw, mins)
    loads = []
    original = minute.simulate

    def load(codes, start, end, **kwargs):
        loads.append((codes, start, end, kwargs))
        return ctx, mins

    def simulate(actual_minutes, actual_daily, *args, **kwargs):
        assert actual_minutes is mins
        pd.testing.assert_frame_equal(actual_daily[CODE], raw[CODE])
        assert not actual_daily[CODE].equals(front[CODE])
        assert kwargs["s12_price_context"] is ctx and kwargs["exdiv"] is None
        return original(actual_minutes, actual_daily, *args, **kwargs)

    def no_legacy_read(*args, **kwargs):
        raise AssertionError("ON must bypass the legacy loaders and window cache")

    monkeypatch.setattr(domain, "load_s12_price_context", load)
    monkeypatch.setattr(minute, "simulate", simulate)
    monkeypatch.setattr(minute, "resolve_research_pool_dir", lambda *a, **kw: tmp_path)
    monkeypatch.setattr(minute, "load_pool_day_map", lambda *a, **kw: {START: [CODE]})
    monkeypatch.setattr(minute, "load_pool_names_by_day", lambda *a, **kw: {})
    for name in ("load_daily_ohlc", "load_minute_bars", "_load_minute_from_lake", "load_exdiv_ratios"):
        monkeypatch.setattr(minute, name, no_legacy_read)
    st = minute.run(START, days[-1].strftime("%Y%m%d"), strategy="12", total_cash=5_000_000,
                    fix_s12_price_domain=True)
    assert len(loads) == 1 and loads[0][0] == {CODE}
    assert st.stats["cache"] == "s12_price_domain_uncached"
    assert st.stats["mark_domain"] == "none"
    assert money(st.equity_curve[-1][1]) == Decimal("4999000.00")


@pytest.mark.parametrize("kwargs", [
    {"strategy": "8"}, {"dividend_type": "front"},
    {"daily_source": "qlib"}, {"minute_source": "qlib"},
])
def test_on_unsupported_cli_combinations_fail_before_loading(monkeypatch, kwargs):
    def no_load(*args, **kw):
        raise AssertionError("unsupported ON configuration must fail before any data reads")

    monkeypatch.setattr(minute, "load_pool_day_map", no_load)
    params = {"strategy": "12", "dividend_type": "none", "fix_s12_price_domain": True}
    params.update(kwargs)
    with pytest.raises((ValueError, SystemExit), match="(?i)(s12|version12|none|lake)"):
        minute.run(START, START, **params)


def test_on_library_requires_explicit_context_and_rejects_second_exdiv():
    mins, raw, front, _days = fixture()
    with pytest.raises(ValueError, match="context"):
        minute.simulate(mins, raw, {START: [CODE]}, START, "20251104", strategy="12",
                        fix_s12_price_domain=True)
    ctx = context_for(front, raw, mins)
    with pytest.raises(ValueError, match="exdiv"):
        minute.simulate(mins, raw, {START: [CODE]}, START, "20251104", strategy="12",
                        fix_s12_price_domain=True, s12_price_context=ctx, exdiv={})


def test_on_metadata_is_truthful_and_off_stats_gain_no_fix_keys():
    inputs = fixture()
    off, _ = replay(*inputs, enabled=False)
    on, _ = replay(*inputs, enabled=True)
    assert "fix_s12_price_domain" not in off.stats
    assert on.stats["fix_s12_price_domain"] is True
    assert on.stats["daily_signal_domain"] == "front"
    assert on.stats["signal_comparison_domain"] == "raw_at_session_D"
    assert on.stats["minute_fill_domain"] == on.stats["mark_domain"] == "none"
    assert on.stats["implicit_exdiv_map"] is False
    assert on.stats["nav_comparability"] == "raw_accounting_only"
    assert on.stats["total_return_complete"] is False
